"""Frozen public train/dev corpus, evaluator metadata and a public-only archive."""

from collections import Counter
import gzip
import hashlib
import io
from pathlib import Path
import re
import tarfile

from genesis_fintech.domain.models import DataError, identifier, integer, object_fields
from genesis_fintech.domain.findings import ISSUE_TYPES
from .scenario import ScenarioConfig, generate_scenario
from .storage import MAX_FILE_BYTES, json_text, load_scenario, read_json, write_scenario

FORMAT_VERSION = "1.0"
PUBLIC_FILES = ("manifest.json", "policy.json", "ledger.csv", "invoices.jsonl", "payments.jsonl", "fx.csv")
EPISODE_FILES = tuple("public/" + name for name in PUBLIC_FILES) + ("private/truth.json", "private/provenance.json")
FAMILY_FIELDS = {"duplicate_invoice": "duplicate_invoices", "payment_allocation": "allocation_errors",
                 "fx_mismatch": "fx_errors", "period_cutoff": "cutoff_errors"}


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def _read_bytes(path):
    if path.is_symlink() or not path.is_file():
        raise DataError("dataset: missing file or symbolic link")
    with path.open("rb") as stream:
        value = stream.read(MAX_FILE_BYTES + 1)
    if len(value) > MAX_FILE_BYTES:
        raise DataError("dataset: oversized file")
    return value


def validate_spec(spec):
    object_fields(spec, {"dataset_version", "dataset_id", "generator_version", "scenario_generator_version", "splits"})
    if (spec["dataset_version"] != FORMAT_VERSION or type(spec["dataset_id"]) is not str
            or not re.fullmatch(r"[a-z][a-z0-9-]{0,63}", spec["dataset_id"])):
        raise DataError("dataset: unsupported format or identifier")
    if spec["generator_version"] != "0.2.0" or spec["scenario_generator_version"] != "0.2.0":
        raise DataError("dataset: unsupported generator versions")
    object_fields(spec["splits"], {"train", "dev"})
    seeds, entries = set(), []
    for split in ("train", "dev"):
        items = spec["splits"][split]
        if type(items) is not list or len(items) != 10:
            raise DataError("dataset: exactly 10 train and 10 dev entries required")
        clean, interactions, families = 0, set(), Counter()
        for item in items:
            object_fields(item, {"seed", "config"})
            seed = integer(item["seed"], "seed", 0, 2**63 - 1)
            if seed in seeds:
                raise DataError("dataset: overlapping episode seeds")
            seeds.add(seed)
            config = ScenarioConfig.from_dict(item["config"])
            counts = {kind: getattr(config, field) for kind, field in FAMILY_FIELDS.items()}
            clean += not any(counts.values())
            families.update(counts)
            interactions.update(config.interaction_scenarios)
            entries.append((split, seed, config))
        if not clean or set(families) != ISSUE_TYPES or not all(families.values()) or interactions != {"fx_allocation", "duplicate_cutoff"}:
            raise DataError("dataset: each split requires clean cases, four families and both interactions")
    return entries


def _episode_path(root, split, episode_id):
    if split not in ("train", "dev"):
        raise DataError("dataset: unknown split")
    identifier(episode_id, "episode_id")
    if not episode_id.startswith("episode_"):
        raise DataError("dataset: invalid episode directory")
    path = root / "episodes" / split / episode_id
    for part in (root, root/"episodes", root/"episodes"/split, path, path/"public", path/"private"):
        if part.is_symlink() or not part.is_dir():
            raise DataError("dataset: missing directory or symbolic link")
    return path


def _public_index(dataset_id, entries):
    return {"dataset_version": FORMAT_VERSION, "dataset_id": dataset_id,
            "splits": {split: [{"episode_id": item["episode_id"],
                                "files": {name: item["files"]["public/"+name] for name in PUBLIC_FILES}}
                               for item in entries if item["split"] == split] for split in ("train", "dev")}}


def _archive_bytes(root, public_index):
    output = io.BytesIO()
    with gzip.GzipFile(filename="", fileobj=output, mode="wb", mtime=0) as compressed:
        with tarfile.open(fileobj=compressed, mode="w", format=tarfile.USTAR_FORMAT) as archive:
            files = {"index.json": json_text(public_index).encode()}
            for split in ("train", "dev"):
                for entry in public_index["splits"][split]:
                    path = _episode_path(root, split, entry["episode_id"])
                    for name in PUBLIC_FILES:
                        files[f"{split}/{entry['episode_id']}/{name}"] = _read_bytes(path/"public"/name)
            for name, content in sorted(files.items()):
                info = tarfile.TarInfo(name)
                info.size, info.mode, info.mtime = len(content), 0o644, 0
                archive.addfile(info, io.BytesIO(content))
    return output.getvalue()


def generate_dataset(spec, output):
    descriptors = validate_spec(spec)
    # Fail on inconsistent data before creating a partial corpus.
    generated = [(split, seed, config, generate_scenario(seed, config)) for split, seed, config in descriptors]
    root = Path(output)
    root.mkdir(parents=True, exist_ok=False)
    entries = []
    seen_ids = set()
    for split, seed, config, scenario in generated:
        eid = scenario.public.manifest.episode_id
        if eid in seen_ids:
            raise DataError("dataset: repeated episode ID")
        seen_ids.add(eid)
        path = root / "episodes" / split / eid
        write_scenario(scenario, path)
        entries.append({"split": split, "episode_id": eid,
                        "files": {name: sha256(_read_bytes(path/name)) for name in EPISODE_FILES}})
    public_index = _public_index(spec["dataset_id"], entries)
    public_data = json_text(public_index).encode()
    archive_data = _archive_bytes(root, public_index)
    (root/"public-index.json").write_bytes(public_data)
    (root/"public-train-dev.tar.gz").write_bytes(archive_data)
    index = {"dataset_version": FORMAT_VERSION, "source_spec": spec, "episodes": entries,
             "public_index_sha256": sha256(public_data), "public_archive_sha256": sha256(archive_data)}
    (root/"dataset.json").write_text(json_text(index), encoding="utf-8")
    (root/"dataset.json").chmod(0o600)
    return validate_dataset(root, replay=True)


def validate_dataset(directory, *, replay=False):
    """Verify bytes + independent public-record truth validation; optional generation replay."""
    root = Path(directory)
    _read_bytes(root/"dataset.json")
    index = read_json(root/"dataset.json")
    object_fields(index, {"dataset_version", "source_spec", "episodes", "public_index_sha256", "public_archive_sha256"})
    if index["dataset_version"] != FORMAT_VERSION:
        raise DataError("dataset: unsupported index version")
    descriptors = validate_spec(index["source_spec"])
    if type(index["episodes"]) is not list or len(index["episodes"]) != 20:
        raise DataError("dataset: expected 20 episode descriptors")
    seen_ids, stats = set(), {split: {"episodes": 0, "clean": 0, "issues": 0, "families": Counter()} for split in ("train", "dev")}
    sizes = []
    for (split, seed, config), item in zip(descriptors, index["episodes"]):
        object_fields(item, {"split", "episode_id", "files"})
        identifier(item["episode_id"], "episode_id")
        if item["split"] != split or item["episode_id"] in seen_ids:
            raise DataError("dataset: duplicate ID or split mismatch")
        seen_ids.add(item["episode_id"])
        object_fields(item["files"], set(EPISODE_FILES))
        path = _episode_path(root, split, item["episode_id"])
        for name in EPISODE_FILES:
            if sha256(_read_bytes(path/name)) != item["files"][name]:
                raise DataError("dataset: file checksum mismatch")
        public, truth = load_scenario(path)  # independently validates all labels/evidence
        provenance = read_json(path/"private/provenance.json")
        if (public.manifest.episode_id != item["episode_id"] or provenance.get("seed") != seed
                or provenance.get("scenario_config") != config.to_dict()
                or provenance.get("generator_version") != index["source_spec"]["generator_version"]
                or provenance.get("scenario_generator_version") != index["source_spec"]["scenario_generator_version"]):
            raise DataError("dataset: identity, configuration or generator mismatch")
        counts = Counter(issue.type for issue in truth.issues)
        if any(counts[family] != getattr(config, field) for family, field in FAMILY_FIELDS.items()):
            raise DataError("dataset: issue counts disagree with declared configuration")
        if not 200 <= public.manifest.row_count <= 2000 or not 20 <= public.manifest.document_count <= 200:
            raise DataError("dataset: episode outside declared size envelope")
        if replay:
            again = generate_scenario(seed, config)
            if (again.public.to_dict() != public.to_dict() or again.truth.to_dict() != truth.to_dict()
                    or json_text(again.provenance) != json_text(provenance)):
                raise DataError("dataset: replay mismatch")
        stats[split]["episodes"] += 1
        stats[split]["clean"] += not truth.issues
        stats[split]["issues"] += len(truth.issues)
        stats[split]["families"].update(counts)
        sizes.append((public.manifest.row_count, public.manifest.document_count))
    public_data = _read_bytes(root/"public-index.json")
    if public_data != json_text(_public_index(index["source_spec"]["dataset_id"], index["episodes"])).encode() or sha256(public_data) != index["public_index_sha256"]:
        raise DataError("dataset: public index mismatch")
    archive_data = _read_bytes(root/"public-train-dev.tar.gz")
    if sha256(archive_data) != index["public_archive_sha256"] or archive_data != _archive_bytes(root, _public_index(index["source_spec"]["dataset_id"], index["episodes"])):
        raise DataError("dataset: public archive mismatch")
    return {"ok": True, "dataset_id": index["source_spec"]["dataset_id"], "splits": stats,
            "replayed": replay, "public_archive_sha256": index["public_archive_sha256"],
            "row_range": [min(n[0] for n in sizes), max(n[0] for n in sizes)],
            "document_range": [min(n[1] for n in sizes), max(n[1] for n in sizes)]}
