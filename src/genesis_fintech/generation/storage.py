"""Read public records explicitly; write clean public/private artifacts separately."""

import csv
from dataclasses import fields
import io
import json
from pathlib import Path
import re

from genesis_fintech.domain.models import (
    DataError, FxRate, Invoice, LedgerRow, Manifest, Payment, Policy, PublicEpisode,
)
from genesis_fintech.evaluation.clean import check_clean
from .clean import GeneratedEpisode

MAX_FILE_BYTES = 4 * 1024 * 1024


def json_text(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n"


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise DataError("JSON: duplicate object key")
        result[key] = value
    return result


def _invalid_constant(value):
    raise DataError("JSON: non-finite constant")


def parse_json(value: str):
    try:
        return json.loads(value, object_pairs_hook=_pairs, parse_constant=_invalid_constant)
    except DataError:
        raise
    except (ValueError, RecursionError) as exc:
        raise DataError("JSON: invalid or excessively nested input") from exc


def _read(path: Path) -> str:
    with path.open("rb") as file:
        data = file.read(MAX_FILE_BYTES + 1)
    if len(data) > MAX_FILE_BYTES:
        raise DataError("record file exceeds 4 MiB limit")
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise DataError("record file must be UTF-8") from exc


def read_json(path: Path):
    return parse_json(_read(path))


def _csv_text(records, model) -> str:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=[f.name for f in fields(model)], lineterminator="\n")
    writer.writeheader()
    for record in records:
        writer.writerow({k: "null" if value is None else value for k, value in record.to_dict().items()})
    return stream.getvalue()


def _csv_records(path: Path, model):
    reader = csv.DictReader(io.StringIO(_read(path), newline=""))
    headers = [f.name for f in fields(model)]
    result = []
    try:
        if reader.fieldnames != headers:
            raise DataError("CSV: incorrect or duplicate column headers")
        for row in reader:
            if len(result) >= 10000 or set(row) != set(headers) or any(value is None for value in row.values()):
                raise DataError("CSV: invalid row shape or too many rows")
            if model is LedgerRow:
                for key in ("debit_minor", "credit_minor"):
                    if not re.fullmatch(r"0|[1-9]\d{0,15}", row[key]):
                        raise DataError("CSV: amount must be a canonical nonnegative integer")
                    row[key] = int(row[key])
                for key in ("invoice_id", "payment_id"):
                    if row[key] == "null":
                        row[key] = None
            result.append(model.from_dict(row))
    except csv.Error as exc:
        raise DataError("CSV: invalid input") from exc
    return tuple(result)


def _jsonl_records(path: Path, model):
    lines = _read(path).splitlines()
    if len(lines) > 10000:
        raise DataError("JSONL: too many records")
    return tuple(model.from_dict(parse_json(line)) for line in lines)


def load_public(directory: Path) -> PublicEpisode:
    """Only these six public files are read; no discovery of private siblings."""
    directory = Path(directory)
    return PublicEpisode(
        Manifest.from_dict(read_json(directory / "manifest.json")),
        Policy.from_dict(read_json(directory / "policy.json")),
        _csv_records(directory / "ledger.csv", LedgerRow),
        _jsonl_records(directory / "invoices.jsonl", Invoice),
        _jsonl_records(directory / "payments.jsonl", Payment),
        _csv_records(directory / "fx.csv", FxRate),
    )


def write_clean(generated: GeneratedEpisode, directory: Path) -> None:
    """Create a new local artifact directory; never overwrite an existing one."""
    public = generated.public
    report = check_clean(public)
    if not report.ok or generated.provenance.get("changes") != []:
        raise DataError("refusing to export records that do not pass clean validation")
    _write_episode(public, {"episode_id": public.manifest.episode_id, "issues": []},
                   generated.provenance, directory)


def write_scenario(generated, directory: Path) -> None:
    from genesis_fintech.evaluation.truth import validate_truth
    validate_truth(generated.public, generated.truth)
    _write_episode(generated.public, generated.truth.to_dict(), generated.provenance, directory)


def load_scenario(directory: Path):
    from genesis_fintech.domain.findings import Truth
    from genesis_fintech.evaluation.truth import validate_truth
    directory = Path(directory)
    public = load_public(directory / "public")
    truth = Truth.from_dict(read_json(directory / "private" / "truth.json"))
    validate_truth(public, truth)
    return public, truth


def _write_episode(public, truth, provenance, directory):
    # Serialize and validate before reserving the output folder.
    files = {
        "public/manifest.json": json_text(public.manifest.to_dict()),
        "public/policy.json": json_text(public.policy.to_dict()),
        "public/ledger.csv": _csv_text(public.ledger, LedgerRow),
        "public/invoices.jsonl": "".join(json.dumps(i.to_dict(), ensure_ascii=False, sort_keys=True,
                                                    allow_nan=False) + "\n" for i in public.invoices),
        "public/payments.jsonl": "".join(json.dumps(p.to_dict(), ensure_ascii=False, sort_keys=True,
                                                    allow_nan=False) + "\n" for p in public.payments),
        "public/fx.csv": _csv_text(public.fx, FxRate),
        "private/truth.json": json_text(truth),
        "private/provenance.json": json_text(provenance),
    }
    directory = Path(directory)
    directory.parent.mkdir(parents=True, exist_ok=True)
    directory.mkdir(exist_ok=False)
    (directory / "public").mkdir()
    (directory / "private").mkdir(mode=0o700)
    for name, content in files.items():
        path = directory / name
        with path.open("x", encoding="utf-8", newline="") as stream:
            stream.write(content)
        if name.startswith("private/"):
            path.chmod(0o600)
