"""Four causal error families and two composed scenarios over verified history."""

from dataclasses import dataclass, field, replace
from datetime import date, timedelta
from decimal import Context, Decimal, localcontext
import random

from genesis_fintech.domain.findings import Issue, Truth
from genesis_fintech.domain.fx import in_period, payment_quote, payment_value_minor
from genesis_fintech.domain.models import DataError, PublicEpisode, Record, array, integer, object_fields
from genesis_fintech.domain.money import convert_minor
from genesis_fintech.evaluation.clean import check_clean
from .clean import CleanConfig, generate_clean

NEW_CONFIG_FIELDS = {"fx_errors", "cutoff_errors", "fx_error_mode", "interaction_scenarios"}


@dataclass(frozen=True)
class ScenarioConfig(Record):
    config_version: str = "0.2"
    clean: CleanConfig = field(default_factory=CleanConfig)
    duplicate_invoices: int = 1
    allocation_errors: int = 1
    allocation_mode: str = "partial"
    fx_errors: int = 0
    cutoff_errors: int = 0
    fx_error_mode: str = "rate"
    interaction_scenarios: tuple[str, ...] = ()

    def __post_init__(self):
        if self.config_version not in ("0.1", "0.2") or type(self.clean) is not CleanConfig:
            raise DataError("scenario config: unsupported version or clean config")
        for name in ("duplicate_invoices", "allocation_errors", "fx_errors", "cutoff_errors"):
            integer(getattr(self, name), name, 0, 12)
        if self.allocation_mode not in ("partial", "missing") or self.fx_error_mode not in ("rate", "date"):
            raise DataError("scenario config: unsupported injection mode")
        allowed = {"fx_allocation", "duplicate_cutoff"}
        if type(self.interaction_scenarios) is not tuple or any(type(x) is not str or x not in allowed for x in self.interaction_scenarios):
            raise DataError("interaction_scenarios: unsupported")
        if len(set(self.interaction_scenarios)) != len(self.interaction_scenarios):
            raise DataError("interaction_scenarios: duplicates")
        if self.config_version == "0.1" and (self.fx_errors or self.cutoff_errors or self.interaction_scenarios):
            raise DataError("new error families require config_version 0.2")
        if "fx_allocation" in self.interaction_scenarios and not (self.fx_errors and self.allocation_errors):
            raise DataError("fx_allocation requires both family counts")
        if "duplicate_cutoff" in self.interaction_scenarios and not (self.duplicate_invoices and self.cutoff_errors):
            raise DataError("duplicate_cutoff requires both family counts")
        total = self.duplicate_invoices + self.allocation_errors + self.fx_errors + self.cutoff_errors
        if total > 12 or total - len(self.interaction_scenarios) > self.clean.invoice_count:
            raise DataError("scenario: at most 12 issues and enough distinct invoices required")
        if self.fx_errors > self.clean.foreign_payment_invoices:
            raise DataError("scenario: not enough foreign-payment invoices for FX errors")

    @classmethod
    def from_dict(cls, data):
        required = set(cls.__dataclass_fields__)
        legacy = type(data) is dict and data.get("config_version") == "0.1"
        if legacy:
            required -= NEW_CONFIG_FIELDS
        object_fields(data, required)
        normalized = {**data, "clean": CleanConfig.from_dict(data["clean"])}
        if not legacy:
            normalized["interaction_scenarios"] = tuple(array(data["interaction_scenarios"]))
        return cls(**normalized)

    def to_dict(self):
        data = super().to_dict()
        data["clean"] = self.clean.to_dict()
        if self.config_version == "0.1":
            for key in NEW_CONFIG_FIELDS:
                del data[key]
        return data


@dataclass(frozen=True)
class GeneratedScenario:
    public: PublicEpisode
    truth: Truth
    provenance: dict


def _wrong_fx(public, payment, mode):
    correct = payment_quote(public, payment)
    if correct is None:
        raise DataError("FX target must have a foreign payment")
    expected = payment_value_minor(public, payment)
    if mode == "date":
        previous = (date.fromisoformat(correct.date) - timedelta(days=1)).isoformat()
        candidates = [q for q in public.fx if (q.date, q.source_currency, q.target_currency)
                      == (previous, payment.currency, public.manifest.base_currency)]
        if len(candidates) != 1:
            raise DataError("wrong-date FX scenario requires a prior-day quote")
        rates = [candidates[0].rate]
    else:
        with localcontext(Context(prec=80)):
            rates = [format((Decimal(correct.rate) * factor).quantize(Decimal('0.000000000000000001')), 'f')
                     for factor in (Decimal('1.1'), Decimal('3'))]
    exponents = public.manifest.currency_exponents
    for rate in rates:
        booked = convert_minor(payment.amount_minor, exponents[payment.currency],
                               exponents[public.manifest.base_currency], rate, public.policy.rounding)
        if booked > 0 and booked != expected:
            return rate, booked
    raise DataError("FX difference disappears under declared minor-unit rounding")


def generate_scenario(seed: int, config: ScenarioConfig | None = None) -> GeneratedScenario:
    config = config or ScenarioConfig()
    source = generate_clean(seed, config.clean)
    public = source.public
    if not check_clean(public).ok:
        raise DataError("refusing to inject into inconsistent source history")
    rng = random.Random("injections-v2:" + str(seed))
    rows = {row.row_id: row for row in public.ledger}
    existing = set(rows)

    def new_id(prefix):
        while True:
            value = f"{prefix}_{rng.getrandbits(128):032x}"
            if value not in existing:
                existing.add(value)
                return value

    invoices = sorted(public.invoices, key=lambda item: item.invoice_id)
    sale_candidates = [i for i in invoices if in_period(public.manifest, i.issued_at)]
    payments = {i.invoice_id: sorted((p for p in public.payments if p.invoice_refs[0].invoice_id == i.invoice_id
                                     and p.amount_minor > 0 and in_period(public.manifest, p.timestamp)), key=lambda p: p.payment_id)
                for i in invoices}
    foreign = {}
    for invoice in invoices:
        options = []
        for payment in payments[invoice.invoice_id]:
            if payment.currency != public.manifest.base_currency:
                try:
                    _wrong_fx(public, payment, config.fx_error_mode)
                    options.append(payment)
                except DataError:
                    pass
        if options:
            foreign[invoice.invoice_id] = options
    targets = {name: [] for name in ("duplicate_invoice", "payment_allocation", "fx_mismatch", "period_cutoff")}
    used = set()

    def choose(candidates):
        eligible = [invoice for invoice in candidates if invoice.invoice_id not in used]
        if not eligible:
            raise DataError("scenario configuration has insufficient observable eligible targets")
        invoice = rng.choice(eligible)
        used.add(invoice.invoice_id)
        return invoice

    if "fx_allocation" in config.interaction_scenarios:
        invoice = choose([i for i in invoices if i.invoice_id in foreign])
        payment = rng.choice(foreign[invoice.invoice_id])
        targets["fx_mismatch"].append((invoice, payment))
        targets["payment_allocation"].append((invoice, payment))
    if "duplicate_cutoff" in config.interaction_scenarios:
        invoice = choose(sale_candidates)
        targets["duplicate_invoice"].append((invoice, None))
        targets["period_cutoff"].append((invoice, None))
    for _ in range(config.fx_errors - len(targets["fx_mismatch"])):
        invoice = choose([i for i in invoices if i.invoice_id in foreign])
        targets["fx_mismatch"].append((invoice, rng.choice(foreign[invoice.invoice_id])))
    for _ in range(config.allocation_errors - len(targets["payment_allocation"])):
        invoice = choose([i for i in invoices if payments[i.invoice_id]])
        targets["payment_allocation"].append((invoice, rng.choice(payments[invoice.invoice_id])))
    for name, count in [("duplicate_invoice", config.duplicate_invoices), ("period_cutoff", config.cutoff_errors)]:
        for _ in range(count - len(targets[name])):
            targets[name].append((choose(sale_candidates), None))

    changes, specifications = [], []

    def mutate(kind, before, after, **details):
        for row in before:
            del rows[row.row_id]
        rows.update({row.row_id: row for row in after})
        changes.append({"type": kind, "before": [r.to_dict() for r in before],
                        "after": [r.to_dict() for r in after], **details})

    for invoice, _ in targets["duplicate_invoice"]:
        originals = [r for r in rows.values() if r.invoice_id == invoice.invoice_id and r.payment_id is None]
        added = [replace(r, row_id=new_id('row')) for r in originals]
        mutate('duplicate_invoice', [], added)
        specifications.append(('duplicate_invoice', invoice, None, invoice.total_minor))
    for invoice, payment in targets["fx_mismatch"]:
        rate, booked = _wrong_fx(public, payment, config.fx_error_mode)
        before = [r for r in rows.values() if r.payment_id == payment.payment_id]
        after = [replace(r, debit_minor=booked) if r.account == 'bank' else replace(r, credit_minor=booked) for r in before]
        mutate('fx_mismatch', before, after, applied_rate=rate, fx_error_mode=config.fx_error_mode)
        specifications.append(('fx_mismatch', invoice, payment, abs(payment_value_minor(public, payment) - booked)))
    for invoice, payment in targets["payment_allocation"]:
        original = next(r for r in rows.values() if r.payment_id == payment.payment_id and r.account == 'receivable')
        delta = (original.credit_minor if config.allocation_mode == 'missing' or original.credit_minor == 1
                 else rng.randint(1, original.credit_minor - 1))
        added = [] if delta == original.credit_minor else [replace(original, credit_minor=original.credit_minor - delta)]
        added.append(replace(original, row_id=new_id('row'), account='revenue', credit_minor=delta))
        mutate('payment_allocation', [original], added)
        specifications.append(('payment_allocation', invoice, payment, delta))
    for invoice, _ in targets["period_cutoff"]:
        before = [r for r in rows.values() if r.invoice_id == invoice.invoice_id and r.payment_id is None]
        after = [replace(r, timestamp=public.manifest.period_end) for r in before]
        mutate('period_cutoff', before, after)
        specifications.append(('period_cutoff', invoice, None, invoice.total_minor))
    ledger = list(rows.values())
    if changes:
        rng.shuffle(ledger)
    public = replace(public, ledger=tuple(ledger), manifest=replace(public.manifest, row_count=len(ledger)))
    issues = []
    for kind, invoice, payment, amount in specifications:
        if payment is None:
            affected = (invoice.invoice_id,)
            witness = [invoice.doc_id] + [r.row_id for r in public.ledger
                                         if r.invoice_id == invoice.invoice_id and r.payment_id is None]
        else:
            affected = tuple(sorted([invoice.invoice_id, payment.payment_id]))
            witness = [invoice.doc_id, payment.doc_id] + [r.row_id for r in public.ledger if r.payment_id == payment.payment_id]
            quote = payment_quote(public, payment)
            if quote is not None:
                witness.append(quote.evidence_id)
        issues.append(Issue(new_id('issue'), kind, affected, amount, public.manifest.base_currency,
                            (tuple(sorted(witness)),)))
    truth = Truth.from_dict(Truth(public.manifest.episode_id, tuple(issues)).to_dict())
    provenance = {**source.provenance, "scenario_generator_version": "0.2.0", "scenario_config": config.to_dict(), "changes": changes}
    return GeneratedScenario(public, truth, provenance)
