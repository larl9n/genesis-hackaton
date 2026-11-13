"""Strict submission and private truth contracts, with published canonical IDs."""

from dataclasses import dataclass

from .models import DataError, Record, array, currency, identifier, integer, object_fields

ISSUE_TYPES = {"duplicate_invoice", "payment_allocation", "fx_mismatch", "period_cutoff"}


def canonical_ids(value, name: str, maximum: int = 50, allow_empty: bool = False) -> tuple[str, ...]:
    items = array(value)
    if len(items) > maximum or (not items and not allow_empty):
        raise DataError(f"{name}: invalid number of IDs")
    for item in items:
        identifier(item, name)
    # Case-sensitive set semantics; list length is bounded before deduplication.
    return tuple(sorted(set(items)))


def issue_type(value):
    if type(value) is not str or value not in ISSUE_TYPES:
        raise DataError("type: unsupported issue family")


@dataclass(frozen=True)
class Finding(Record):
    type: str
    affected_ids: tuple[str, ...]
    claimed_amount_minor: int
    currency: str
    evidence_ids: tuple[str, ...]
    explanation: str

    @classmethod
    def from_dict(cls, data):
        object_fields(data, set(cls.__dataclass_fields__))
        issue_type(data["type"])
        currency(data["currency"])
        integer(data["claimed_amount_minor"], "claimed_amount_minor", 0)
        explanation = data["explanation"]
        if type(explanation) is not str or len(explanation) > 1000:
            raise DataError("explanation: expected at most 1000 characters")
        return cls(data["type"], canonical_ids(data["affected_ids"], "affected_ids"),
                   data["claimed_amount_minor"], data["currency"],
                   canonical_ids(data["evidence_ids"], "evidence_ids", 10, True), explanation)


@dataclass(frozen=True)
class Submission(Record):
    episode_id: str
    findings: tuple[Finding, ...]

    @classmethod
    def from_dict(cls, data):
        object_fields(data, set(cls.__dataclass_fields__))
        identifier(data["episode_id"], "episode_id")
        findings = array(data["findings"])
        if len(findings) > 30:
            raise DataError("findings: at most 30 allowed")
        return cls(data["episode_id"], tuple(Finding.from_dict(item) for item in findings))


@dataclass(frozen=True)
class Issue(Record):
    issue_id: str
    type: str
    affected_ids: tuple[str, ...]
    expected_amount_minor: int
    currency: str
    acceptable_evidence_sets: tuple[tuple[str, ...], ...]

    @classmethod
    def from_dict(cls, data):
        object_fields(data, set(cls.__dataclass_fields__))
        identifier(data["issue_id"], "issue_id")
        issue_type(data["type"])
        integer(data["expected_amount_minor"], "expected_amount_minor", 1)
        currency(data["currency"])
        sets = array(data["acceptable_evidence_sets"])
        if not 1 <= len(sets) <= 10:
            raise DataError("acceptable_evidence_sets: expected 1..10 complete sets")
        return cls(data["issue_id"], data["type"], canonical_ids(data["affected_ids"], "affected_ids"),
                   data["expected_amount_minor"], data["currency"],
                   tuple(canonical_ids(ids, "evidence_ids", 10) for ids in sets))


@dataclass(frozen=True)
class Truth(Record):
    episode_id: str
    issues: tuple[Issue, ...]

    @classmethod
    def from_dict(cls, data):
        object_fields(data, set(cls.__dataclass_fields__))
        identifier(data["episode_id"], "episode_id")
        issues = array(data["issues"])
        if len(issues) > 12:
            raise DataError("issues: at most 12 allowed")
        parsed = tuple(Issue.from_dict(item) for item in issues)
        if len({issue.issue_id for issue in parsed}) != len(parsed):
            raise DataError("issues: duplicate private issue IDs")
        return cls(data["episode_id"], parsed)


def evidence_ids(public) -> set[str]:
    return ({row.row_id for row in public.ledger}
            | {doc.doc_id for doc in (*public.invoices, *public.payments)}
            | {row.evidence_id for row in public.fx})


def oracle_submission(truth: Truth) -> dict:
    """Evaluator-only ceiling probe; never a policy-visible tool."""
    return Submission(truth.episode_id, tuple(
        Finding(issue.type, issue.affected_ids, issue.expected_amount_minor, issue.currency,
                issue.acceptable_evidence_sets[0], "Evaluator-only supported finding")
        for issue in truth.issues
    )).to_dict()
