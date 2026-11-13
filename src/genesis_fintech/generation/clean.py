"""Seeded latent history first, public documents second. No injected errors yet."""

from dataclasses import asdict, dataclass
from datetime import timedelta, timezone
import random
from zoneinfo import ZoneInfo

from genesis_fintech.domain.models import (
    Allocation, DataError, Invoice, LedgerRow, LineItem, Manifest, Payment, Policy,
    PublicEpisode, Record, SCHEMA_VERSION, integer, timestamp,
)

GENERATOR_VERSION = "0.1.0"
SUPPORTED_EXPONENTS = {"KZT": 2, "USD": 2, "EUR": 2, "JPY": 0, "KWD": 3}


@dataclass(frozen=True)
class CleanConfig(Record):
    config_version: str = "0.1"
    invoice_count: int = 50
    base_currency: str = "KZT"
    timezone: str = "Asia/Almaty"
    period_start: str = "2026-10-01T00:00:00+05:00"
    period_end: str = "2026-11-01T00:00:00+05:00"
    split_percent: int = 30
    partial_percent: int = 25

    def __post_init__(self):
        if self.config_version != "0.1":
            raise DataError("config_version: unsupported")
        integer(self.invoice_count, "invoice_count", 1, 60)
        integer(self.split_percent, "split_percent", 0, 100)
        integer(self.partial_percent, "partial_percent", 0, 100)
        if type(self.base_currency) is not str or self.base_currency not in SUPPORTED_EXPONENTS:
            raise DataError("base_currency: unsupported by clean generator")
        duration = (timestamp(self.period_end) - timestamp(self.period_start)).total_seconds()
        if not 14 * 86400 <= duration <= 366 * 86400:
            raise DataError("clean generator: period must span 14..366 days")
        # Reuse the manifest contract for timezone and public policy validation.
        Manifest(SCHEMA_VERSION, "episode_config", self.base_currency,
                 {self.base_currency: SUPPORTED_EXPONENTS[self.base_currency]},
                 self.period_start, self.period_end, self.timezone, 0, 0, 0, "ROUND_HALF_EVEN")


@dataclass(frozen=True)
class PaymentIntent:
    payment_id: str
    doc_id: str
    timestamp: str
    amount_minor: int


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
                                    (issued + timedelta(days=index + 1)).astimezone(local_zone).isoformat(), amount)
                      for index, amount in enumerate(amounts))
        history.append(Sale(new_id("invoice"), new_id("doc"), rng.choice(customers),
                            issued.astimezone(local_zone).isoformat(),
                            (issued + timedelta(days=30)).astimezone(local_zone).isoformat(), items, plans))

    # The full, consistent history exists before any document or ledger derivation.
    invoices, payments, ledger = [], [], []
    for sale in history:
        total = sum(item.quantity * item.unit_price_minor for item in sale.items)
        invoices.append(Invoice(sale.doc_id, sale.invoice_id, sale.entity_id, sale.issued_at, sale.due_at,
                                config.base_currency, total, sale.items))
        for account, debit, credit in [("receivable", total, 0), ("revenue", 0, total)]:
            ledger.append(LedgerRow(new_id("row"), sale.issued_at, account, debit, credit,
                                    config.base_currency, sale.entity_id, sale.invoice_id, None))
        for plan in sale.payments:
            payments.append(Payment(plan.doc_id, plan.payment_id, plan.timestamp, config.base_currency,
                                    plan.amount_minor, (Allocation(sale.invoice_id, plan.amount_minor,
                                                                    config.base_currency),)))
            ledger.extend([
                LedgerRow(new_id("row"), plan.timestamp, "bank", plan.amount_minor, 0,
                          config.base_currency, sale.entity_id, None, plan.payment_id),
                LedgerRow(new_id("row"), plan.timestamp, "receivable", 0, plan.amount_minor,
                          config.base_currency, sale.entity_id, sale.invoice_id, plan.payment_id),
            ])
    for records in (invoices, payments, ledger):
        rng.shuffle(records)
    manifest = Manifest(SCHEMA_VERSION, episode_id, config.base_currency,
                        {config.base_currency: SUPPORTED_EXPONENTS[config.base_currency]},
                        config.period_start, config.period_end, config.timezone,
                        len(ledger), len(invoices) + len(payments), 0, "ROUND_HALF_EVEN")
    public = PublicEpisode(manifest, Policy(), tuple(ledger), tuple(invoices), tuple(payments), ())
    return GeneratedEpisode(public, {
        "generator_version": GENERATOR_VERSION, "seed": seed, "config": asdict(config),
        "latent_history": [asdict(sale) for sale in history], "changes": [],
    })
