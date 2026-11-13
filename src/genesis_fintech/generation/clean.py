"""Seeded latent history first, public documents second. No injected errors yet."""

from dataclasses import asdict, dataclass, replace
from datetime import date, timedelta, timezone
from decimal import Context, Decimal, localcontext
import random
from zoneinfo import ZoneInfo

from genesis_fintech.domain.models import (
    Allocation, DataError, FxRate, Invoice, LedgerRow, LineItem, Manifest, Payment, Policy,
    PublicEpisode, Record, SCHEMA_VERSION, integer, object_fields, rate_string, timestamp,
)
from genesis_fintech.domain.money import convert_minor

GENERATOR_VERSION = "0.2.0"
SUPPORTED_EXPONENTS = {"KZT": 2, "USD": 2, "EUR": 2, "JPY": 0, "KWD": 3}


@dataclass(frozen=True)
class CleanConfig(Record):
    config_version: str = "0.2"
    invoice_count: int = 50
    base_currency: str = "KZT"
    timezone: str = "Asia/Almaty"
    period_start: str = "2026-10-01T00:00:00+05:00"
    period_end: str = "2026-11-01T00:00:00+05:00"
    split_percent: int = 30
    partial_percent: int = 25
    foreign_payment_invoices: int = 0
    foreign_currency: str = "USD"
    foreign_rate: str = "500.25"
    boundary_invoices: int = 0
    refund_invoices: int = 0

    def __post_init__(self):
        if self.config_version not in ("0.1", "0.2"):
            raise DataError("config_version: unsupported")
        integer(self.invoice_count, "invoice_count", 1, 60)
        integer(self.split_percent, "split_percent", 0, 100)
        integer(self.partial_percent, "partial_percent", 0, 100)
        integer(self.foreign_payment_invoices, "foreign_payment_invoices", 0, self.invoice_count)
        integer(self.boundary_invoices, "boundary_invoices", 0, self.invoice_count)
        integer(self.refund_invoices, "refund_invoices", 0, self.invoice_count)
        if self.config_version == "0.1" and (self.foreign_payment_invoices or self.boundary_invoices or self.refund_invoices):
            raise DataError("FX and boundary scenarios require config_version 0.2")
        if type(self.foreign_currency) is not str or self.foreign_currency not in SUPPORTED_EXPONENTS:
            raise DataError("foreign_currency: unsupported")
        if self.foreign_payment_invoices and self.foreign_currency == self.base_currency:
            raise DataError("foreign_currency must differ from base_currency")
        rate_string(self.foreign_rate)
        if type(self.base_currency) is not str or self.base_currency not in SUPPORTED_EXPONENTS:
            raise DataError("base_currency: unsupported by clean generator")
        duration = (timestamp(self.period_end) - timestamp(self.period_start)).total_seconds()
        if not 14 * 86400 <= duration <= 366 * 86400:
            raise DataError("clean generator: period must span 14..366 days")
        try:
            timestamp(self.period_start).astimezone(timezone.utc) - timedelta(days=2)
            timestamp(self.period_end).astimezone(timezone.utc) + timedelta(days=32)
        except OverflowError as exc:
            raise DataError("period is too close to the supported calendar bounds") from exc
        # Reuse the manifest contract for timezone and public policy validation.
        Manifest(SCHEMA_VERSION, "episode_config", self.base_currency,
                 {self.base_currency: SUPPORTED_EXPONENTS[self.base_currency]},
                 self.period_start, self.period_end, self.timezone, 0, 0, 0, "ROUND_HALF_EVEN")

    @classmethod
    def from_dict(cls, data):
        required = set(cls.__dataclass_fields__)
        if type(data) is dict and data.get("config_version") == "0.1":
            required -= {"foreign_payment_invoices", "foreign_currency", "foreign_rate", "boundary_invoices", "refund_invoices"}
        object_fields(data, required)
        return cls(**data)

    def to_dict(self):
        data = super().to_dict()
        if self.config_version == "0.1":
            for key in ("foreign_payment_invoices", "foreign_currency", "foreign_rate", "boundary_invoices", "refund_invoices"):
                del data[key]
        return data


@dataclass(frozen=True)
class PaymentIntent:
    payment_id: str
    doc_id: str
    timestamp: str
    amount_minor: int
    currency: str
    allocated_minor: int


@dataclass(frozen=True)
class Sale:
    invoice_id: str
    doc_id: str
    entity_id: str
    issued_at: str
    due_at: str
    items: tuple[LineItem, ...]
    payments: tuple[PaymentIntent, ...]


@dataclass(frozen=True)
class GeneratedEpisode:
    public: PublicEpisode
    provenance: dict


def generate_clean(seed: int, config: CleanConfig | None = None) -> GeneratedEpisode:
    integer(seed, "seed", 0, 2**63 - 1)
    config = config or CleanConfig()
    rng = random.Random(seed)

    def new_id(prefix: str) -> str:
        return f"{prefix}_{rng.getrandbits(128):032x}"

    episode_id = new_id("episode")
    customers = [new_id("entity") for _ in range(8)]
    start = timestamp(config.period_start).astimezone(timezone.utc)
    duration = int((timestamp(config.period_end) - start).total_seconds())
    local_zone = ZoneInfo(config.timezone)
    factor = 10 ** SUPPORTED_EXPONENTS[config.base_currency]
    history = []
    for _ in range(config.invoice_count):
        issued = start + timedelta(seconds=rng.randrange(0, duration - 7 * 86400))
        items = tuple(LineItem(rng.choice(["Synthetic consulting", "Synthetic hosting", "Synthetic support"]),
                               rng.randint(1, 4), rng.choice([10, 25, 50, 100]) * factor)
                      for _ in range(rng.randint(1, 3)))
        total = sum(item.quantity * item.unit_price_minor for item in items)
        paid = rng.randint(1, total - 1) if rng.randrange(100) < config.partial_percent else total
        amounts = [paid]
        if paid > 1 and rng.randrange(100) < config.split_percent:
            first = rng.randint(1, paid - 1)
            amounts = [first, paid - first]
        plans = tuple(PaymentIntent(new_id("payment"), new_id("doc"),
                                    (issued + timedelta(days=index + 1)).astimezone(local_zone).isoformat(), amount,
                                    config.base_currency, amount)
                      for index, amount in enumerate(amounts))
        history.append(Sale(new_id("invoice"), new_id("doc"), rng.choice(customers),
                            issued.astimezone(local_zone).isoformat(),
                            (issued + timedelta(days=30)).astimezone(local_zone).isoformat(), items, plans))

    # Boundary and FX plans are still latent history; no ledger has been derived yet.
    if config.boundary_invoices:
        selected = sorted(rng.sample(range(len(history)), config.boundary_invoices))
        end = timestamp(config.period_end).astimezone(timezone.utc)
        for pattern, index in enumerate(selected):
            sale = history[index]
            at = (end - timedelta(seconds=1), end, start, start - timedelta(seconds=1))[pattern % 4]
            plans = tuple(replace(plan, timestamp=(at + timedelta(days=i + 1)).astimezone(local_zone).isoformat())
                          for i, plan in enumerate(sale.payments))
            history[index] = replace(sale, issued_at=at.astimezone(local_zone).isoformat(),
                                     due_at=(at + timedelta(days=30)).astimezone(local_zone).isoformat(), payments=plans)
    quotes = {}

    def quote(at):
        # Synthetic daily variation is generated independently of public-record checking.
        with localcontext(Context(prec=80)):
            value = Decimal(config.foreign_rate) * (1 + Decimal(date.fromisoformat(at).toordinal() % 17) / 1000)
            return format(value.quantize(Decimal("0.000000000000000001")), "f").rstrip("0").rstrip(".")

    if config.foreign_payment_invoices:
        selected = sorted(rng.sample(range(len(history)), config.foreign_payment_invoices))
        source_exp, target_exp = SUPPORTED_EXPONENTS[config.foreign_currency], SUPPORTED_EXPONENTS[config.base_currency]
        for index in selected:
            sale = history[index]
            remaining = sum(item.quantity * item.unit_price_minor for item in sale.items)
            plans = []
            for plan in sale.payments:
                day = timestamp(plan.timestamp).astimezone(local_zone).date()
                for at in (day, day - timedelta(days=1)):
                    rate = FxRate(at.isoformat(), config.foreign_currency, config.base_currency, quote(at.isoformat()))
                    quotes[rate.evidence_id] = rate
                rate = quote(day.isoformat())
                desired = min(remaining, plan.amount_minor)
                with localcontext(Context(prec=80)):
                    foreign_minor = int(Decimal(desired) * Decimal(10) ** (source_exp - target_exp) / Decimal(rate))
                foreign_minor = max(1, foreign_minor)
                integer(foreign_minor, "foreign payment amount", 1)
                allocated = convert_minor(foreign_minor, source_exp, target_exp, rate)
                if not 0 < allocated <= remaining:
                    if plans:
                        continue
                    raise DataError("FX configuration cannot produce a positive affordable payment")
                plans.append(replace(plan, amount_minor=foreign_minor, currency=config.foreign_currency,
                                     allocated_minor=allocated))
                remaining -= allocated
            history[index] = replace(sale, payments=tuple(plans))

    if config.refund_invoices:
        for index in sorted(rng.sample(range(len(history)), config.refund_invoices)):
            sale = history[index]
            received = sum(plan.allocated_minor for plan in sale.payments)
            amount = rng.randint(1, received)
            at = max(timestamp(plan.timestamp) for plan in sale.payments) + timedelta(days=1)
            refund = PaymentIntent(new_id('payment'), new_id('doc'), at.isoformat(), -amount,
                                   config.base_currency, -amount)
            history[index] = replace(sale, payments=sale.payments + (refund,))

    # The full, consistent history exists before any document or ledger derivation.
    invoices, payments, ledger = [], [], []
    for sale in history:
        total = sum(item.quantity * item.unit_price_minor for item in sale.items)
        invoices.append(Invoice(sale.doc_id, sale.invoice_id, sale.entity_id, sale.issued_at, sale.due_at,
                                config.base_currency, total, sale.items))
        if timestamp(config.period_start) <= timestamp(sale.issued_at) < timestamp(config.period_end):
            for account, debit, credit in [("receivable", total, 0), ("revenue", 0, total)]:
                ledger.append(LedgerRow(new_id("row"), sale.issued_at, account, debit, credit,
                                        config.base_currency, sale.entity_id, sale.invoice_id, None))
        for plan in sale.payments:
            payments.append(Payment(plan.doc_id, plan.payment_id, plan.timestamp, plan.currency,
                                    plan.amount_minor, (Allocation(sale.invoice_id, plan.allocated_minor,
                                                                    config.base_currency),)))
            if not timestamp(config.period_start) <= timestamp(plan.timestamp) < timestamp(config.period_end):
                continue
            ledger.extend([
                LedgerRow(new_id("row"), plan.timestamp, "bank", max(plan.allocated_minor, 0), max(-plan.allocated_minor, 0),
                          config.base_currency, sale.entity_id, None, plan.payment_id),
                LedgerRow(new_id("row"), plan.timestamp, "receivable", max(-plan.allocated_minor, 0), max(plan.allocated_minor, 0),
                          config.base_currency, sale.entity_id, sale.invoice_id, plan.payment_id),
            ])
    for records in (invoices, payments, ledger):
        rng.shuffle(records)
    fx = list(quotes.values())
    if fx:
        rng.shuffle(fx)
    exponents = {config.base_currency: SUPPORTED_EXPONENTS[config.base_currency]}
    if config.foreign_payment_invoices:
        exponents[config.foreign_currency] = SUPPORTED_EXPONENTS[config.foreign_currency]
    schema_version = "0.1" if config.config_version == "0.1" else SCHEMA_VERSION
    manifest = Manifest(schema_version, episode_id, config.base_currency, exponents,
                        config.period_start, config.period_end, config.timezone,
                        len(ledger), len(invoices) + len(payments), 0, "ROUND_HALF_EVEN")
    public = PublicEpisode(manifest, Policy(), tuple(ledger), tuple(invoices), tuple(payments), tuple(fx))
    return GeneratedEpisode(public, {
        "generator_version": GENERATOR_VERSION, "seed": seed, "config": config.to_dict(),
        "latent_history": [asdict(sale) for sale in history], "changes": [],
    })
