"""Causal, recorded mutations of a previously verified clean company."""

from dataclasses import dataclass, field, replace
import random

from genesis_fintech.domain.findings import Issue, Truth
from genesis_fintech.domain.models import DataError, PublicEpisode, Record, integer, object_fields
from genesis_fintech.evaluation.clean import check_clean
from .clean import CleanConfig, generate_clean


@dataclass(frozen=True)
class ScenarioConfig(Record):
    config_version: str = "0.1"
    clean: CleanConfig = field(default_factory=CleanConfig)
    duplicate_invoices: int = 1
    allocation_errors: int = 1
    allocation_mode: str = "partial"

    def __post_init__(self):
        if self.config_version != "0.1" or type(self.clean) is not CleanConfig:
            raise DataError("scenario config: unsupported version or clean config")
        integer(self.duplicate_invoices, "duplicate_invoices", 0, 12)
        integer(self.allocation_errors, "allocation_errors", 0, 12)
        if self.allocation_mode not in ("partial", "missing"):
            raise DataError("allocation_mode: expected partial or missing")
        if self.duplicate_invoices + self.allocation_errors > min(12, self.clean.invoice_count):
            raise DataError("scenario: need distinct invoices for at most 12 issues")

    @classmethod
    def from_dict(cls, data):
        object_fields(data, set(cls.__dataclass_fields__))
        return cls(**{**data, "clean": CleanConfig.from_dict(data["clean"])})


@dataclass(frozen=True)
class GeneratedScenario:
    public: PublicEpisode
    truth: Truth
    provenance: dict


def generate_scenario(seed: int, config: ScenarioConfig | None = None) -> GeneratedScenario:
    config = config or ScenarioConfig()
    clean = generate_clean(seed, config.clean)
    if not check_clean(clean.public).ok:
        raise DataError("refusing to inject into inconsistent source history")
    rng = random.Random("injections-v1:" + str(seed))
    rows = {row.row_id: row for row in clean.public.ledger}
    existing = set(rows)

    def new_id(prefix):
        while True:
            value = f"{prefix}_{rng.getrandbits(128):032x}"
            if value not in existing:
                existing.add(value)
                return value

    candidates = sorted(clean.public.invoices, key=lambda invoice: invoice.invoice_id)
    rng.shuffle(candidates)
    issues, changes = [], []
    for invoice in candidates[:config.duplicate_invoices]:
        original = [row for row in clean.public.ledger if row.invoice_id == invoice.invoice_id
                    and row.payment_id is None]
        added = [replace(row, row_id=new_id("row")) for row in original]
        rows.update({row.row_id: row for row in added})
        evidence = tuple(sorted([invoice.doc_id] + [row.row_id for row in original + added]))
        issues.append(Issue(new_id("issue"), "duplicate_invoice", (invoice.invoice_id,), invoice.total_minor,
                            invoice.currency, (evidence,)))
        changes.append({"type": "duplicate_invoice", "before": [], "after": [row.to_dict() for row in added]})
    for invoice in candidates[config.duplicate_invoices:config.duplicate_invoices + config.allocation_errors]:
        payments = sorted((payment for payment in clean.public.payments
                           if payment.invoice_refs[0].invoice_id == invoice.invoice_id), key=lambda p: p.payment_id)
        payment = rng.choice(payments)
        original = next(row for row in clean.public.ledger if row.payment_id == payment.payment_id
                        and row.account == "receivable")
        delta = (original.credit_minor if config.allocation_mode == "missing" or original.credit_minor == 1
                 else rng.randint(1, original.credit_minor - 1))
        del rows[original.row_id]
        added = []
        if delta < original.credit_minor:
            added.append(replace(original, credit_minor=original.credit_minor - delta))
        added.append(replace(original, row_id=new_id("row"), account="revenue", credit_minor=delta))
        rows.update({row.row_id: row for row in added})
        linked = [row for row in rows.values() if row.payment_id == payment.payment_id]
        evidence = tuple(sorted([invoice.doc_id, payment.doc_id] + [row.row_id for row in linked]))
        issues.append(Issue(new_id("issue"), "payment_allocation", tuple(sorted([invoice.invoice_id, payment.payment_id])),
                            delta, payment.currency, (evidence,)))
        changes.append({"type": "payment_allocation", "before": [original.to_dict()],
                        "after": [row.to_dict() for row in added]})
    ledger = list(rows.values())
    if changes:
        rng.shuffle(ledger)
    public = replace(clean.public, ledger=tuple(ledger), manifest=replace(clean.public.manifest, row_count=len(ledger)))
    provenance = {**clean.provenance, "scenario_config": config.to_dict(), "changes": changes}
    truth = Truth.from_dict(Truth(public.manifest.episode_id, tuple(issues)).to_dict())
    return GeneratedScenario(public, truth, provenance)
