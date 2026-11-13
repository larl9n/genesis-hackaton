"""Strict public record schemas. Cross-record accounting is checked separately."""

from dataclasses import asdict, dataclass
from datetime import date, datetime
import re
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

SCHEMA_VERSION = "0.1"
MAX_MINOR = 10**15
ACCOUNTS = {"receivable", "revenue", "bank"}
ROUNDINGS = {"ROUND_HALF_EVEN", "ROUND_HALF_UP"}


class DataError(ValueError):
    """Input violates a published data contract."""


def integer(value: Any, name: str, minimum: int = -MAX_MINOR, maximum: int = MAX_MINOR) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise DataError(f"{name}: expected integer in [{minimum}, {maximum}]")
    return value


def text(value: Any, name: str, maximum: int = 200) -> str:
    if type(value) is not str or not value or len(value) > maximum:
        raise DataError(f"{name}: expected nonempty string of at most {maximum} characters")
    return value


def identifier(value: Any, name: str) -> str:
    if type(value) is not str or not re.fullmatch(r"[a-z]+_[a-zA-Z0-9_-]{1,80}", value):
        raise DataError(f"{name}: invalid identifier")
    return value


def currency(value: Any) -> str:
    if type(value) is not str or not re.fullmatch(r"[A-Z]{3}", value):
        raise DataError("currency: expected three uppercase letters")
    return value


def timestamp(value: Any) -> datetime:
    if type(value) is not str or not re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})", value
    ):
        raise DataError("timestamp: expected ISO-8601 with an offset")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise DataError("timestamp: invalid date or offset") from exc


def rate_string(value: Any) -> str:
    if type(value) is not str or not re.fullmatch(r"\d{1,12}(?:\.\d{1,18})?", value):
        raise DataError("rate: expected a finite decimal string, up to 12+18 digits")
    if not any(ch in "123456789" for ch in value):
        raise DataError("rate: must be positive")
    return value


def object_fields(data: Any, required: set[str]) -> dict:
    if type(data) is not dict or set(data) != required:
        raise DataError("object: missing or unexpected fields")
    return data


def array(value: Any) -> list:
    if type(value) is not list:
        raise DataError("array: expected a JSON list")
    return value


class Record:
    def to_dict(self) -> dict:
        def json_value(value):
            if isinstance(value, dict):
                return {key: json_value(item) for key, item in value.items()}
            if isinstance(value, (tuple, list)):
                return [json_value(item) for item in value]
            return value
        return json_value(asdict(self))

    @classmethod
    def from_dict(cls, data: Any):
        object_fields(data, set(cls.__dataclass_fields__))
        return cls(**data)


@dataclass(frozen=True)
class Manifest(Record):
    schema_version: str
    episode_id: str
    base_currency: str
    currency_exponents: dict[str, int]
    period_start: str
    period_end: str
    timezone: str
    row_count: int
    document_count: int
    amount_tolerance_minor: int
    rounding: str

    def __post_init__(self):
        if self.schema_version != SCHEMA_VERSION:
            raise DataError("schema_version: unsupported")
        identifier(self.episode_id, "episode_id")
        currency(self.base_currency)
        if type(self.currency_exponents) is not dict or not self.currency_exponents:
            raise DataError("currency_exponents: expected nonempty mapping")
        for code, exponent in self.currency_exponents.items():
            currency(code)
            integer(exponent, "currency exponent", 0, 6)
        if self.base_currency not in self.currency_exponents:
            raise DataError("base_currency: exponent missing")
        if timestamp(self.period_start) >= timestamp(self.period_end):
            raise DataError("period: end must follow start")
        text(self.timezone, "timezone")
        try:
            ZoneInfo(self.timezone)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise DataError("timezone: unknown") from exc
        integer(self.row_count, "row_count", 0, 10000)
        integer(self.document_count, "document_count", 0, 10000)
        integer(self.amount_tolerance_minor, "amount_tolerance_minor", 0, 100)
        if type(self.rounding) is not str or self.rounding not in ROUNDINGS:
            raise DataError("rounding: unsupported")


@dataclass(frozen=True)
class Policy(Record):
    period_boundary: str = "[start,end)"
    invoice_recognition: str = "issued_at"
    fx_date: str = "payment_date"
    rounding: str = "ROUND_HALF_EVEN"

    def __post_init__(self):
        if self.period_boundary != "[start,end)" or self.invoice_recognition != "issued_at":
            raise DataError("policy: unsupported recognition or boundary")
        if self.fx_date != "payment_date" or type(self.rounding) is not str or self.rounding not in ROUNDINGS:
            raise DataError("policy: unsupported FX date or rounding")


@dataclass(frozen=True)
class LedgerRow(Record):
    row_id: str
    timestamp: str
    account: str
    debit_minor: int
    credit_minor: int
    currency: str
    entity_id: str
    invoice_id: str | None
    payment_id: str | None

    def __post_init__(self):
        identifier(self.row_id, "row_id")
        timestamp(self.timestamp)
        if type(self.account) is not str or self.account not in ACCOUNTS:
            raise DataError("account: unsupported")
        integer(self.debit_minor, "debit_minor", 0)
        integer(self.credit_minor, "credit_minor", 0)
        if (self.debit_minor > 0) == (self.credit_minor > 0):
            raise DataError("ledger row: exactly one side must be positive")
        currency(self.currency)
        identifier(self.entity_id, "entity_id")
        for key in ("invoice_id", "payment_id"):
            if getattr(self, key) is not None:
                identifier(getattr(self, key), key)


@dataclass(frozen=True)
class LineItem(Record):
    description: str
    quantity: int
    unit_price_minor: int

    def __post_init__(self):
        text(self.description, "description", 500)
        integer(self.quantity, "quantity", 1, 10**6)
        integer(self.unit_price_minor, "unit_price_minor", 1)
        integer(self.quantity * self.unit_price_minor, "line total", 1)


@dataclass(frozen=True)
class Invoice(Record):
    doc_id: str
    invoice_id: str
    entity_id: str
    issued_at: str
    due_at: str
    currency: str
    total_minor: int
    line_items: tuple[LineItem, ...]

    def __post_init__(self):
        for key in ("doc_id", "invoice_id", "entity_id"):
            identifier(getattr(self, key), key)
        if timestamp(self.due_at) < timestamp(self.issued_at):
            raise DataError("due_at: precedes issued_at")
        currency(self.currency)
        integer(self.total_minor, "total_minor", 1)
        if not self.line_items or len(self.line_items) > 100 or not all(type(x) is LineItem for x in self.line_items):
            raise DataError("line_items: expected 1..100 line items")
        if sum(x.quantity * x.unit_price_minor for x in self.line_items) != self.total_minor:
            raise DataError("total_minor: differs from line items")

    @classmethod
    def from_dict(cls, data):
        object_fields(data, set(cls.__dataclass_fields__))
        return cls(**{**data, "line_items": tuple(LineItem.from_dict(x) for x in array(data["line_items"]))})


@dataclass(frozen=True)
class Allocation(Record):
    invoice_id: str
    allocated_minor: int
    currency: str

    def __post_init__(self):
        identifier(self.invoice_id, "invoice_id")
        integer(self.allocated_minor, "allocated_minor", 1)
        currency(self.currency)


@dataclass(frozen=True)
class Payment(Record):
    doc_id: str
    payment_id: str
    timestamp: str
    currency: str
    amount_minor: int
    invoice_refs: tuple[Allocation, ...]

    def __post_init__(self):
        identifier(self.doc_id, "doc_id")
        identifier(self.payment_id, "payment_id")
        timestamp(self.timestamp)
        currency(self.currency)
        integer(self.amount_minor, "amount_minor", 1)
        if len(self.invoice_refs) > 100 or not all(type(x) is Allocation for x in self.invoice_refs):
            raise DataError("invoice_refs: invalid allocations")
        ids = [x.invoice_id for x in self.invoice_refs]
        if len(ids) != len(set(ids)):
            raise DataError("invoice_refs: duplicate invoice ID")

    @classmethod
    def from_dict(cls, data):
        object_fields(data, set(cls.__dataclass_fields__))
        return cls(**{**data, "invoice_refs": tuple(Allocation.from_dict(x) for x in array(data["invoice_refs"]))})


@dataclass(frozen=True)
class FxRate(Record):
    date: str
    source_currency: str
    target_currency: str
    rate: str

    def __post_init__(self):
        if type(self.date) is not str or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", self.date):
            raise DataError("FX date: expected ISO date")
        try:
            date.fromisoformat(self.date)
        except ValueError as exc:
            raise DataError("FX date: invalid") from exc
        currency(self.source_currency)
        currency(self.target_currency)
        rate_string(self.rate)

    @property
    def evidence_id(self) -> str:
        return f"fx_{self.date}_{self.source_currency}_{self.target_currency}"


@dataclass(frozen=True)
class PublicEpisode(Record):
    manifest: Manifest
    policy: Policy
    ledger: tuple[LedgerRow, ...]
    invoices: tuple[Invoice, ...]
    payments: tuple[Payment, ...]
    fx: tuple[FxRate, ...]

    @classmethod
    def from_dict(cls, data):
        object_fields(data, set(cls.__dataclass_fields__))
        return cls(
            Manifest.from_dict(data["manifest"]), Policy.from_dict(data["policy"]),
            *(tuple(model.from_dict(x) for x in array(data[key])) for key, model in (
                ("ledger", LedgerRow), ("invoices", Invoice), ("payments", Payment), ("fx", FxRate)
            )),
        )
