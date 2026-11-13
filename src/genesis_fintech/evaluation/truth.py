"""Independent public-record explanation of the two implemented error families."""

from dataclasses import dataclass, replace

from genesis_fintech.domain.findings import Truth, evidence_ids
from genesis_fintech.domain.models import DataError, PublicEpisode, timestamp
from .clean import check_clean


@dataclass(frozen=True)
class ObservedIssue:
    type: str
    affected_ids: tuple[str, ...]
    amount_minor: int
    currency: str
    evidence: tuple[str, ...]

    @property
    def key(self):
        return self.type, self.affected_ids, self.amount_minor, self.currency


def inspect_supported_issues(public: PublicEpisode) -> tuple[ObservedIssue, ...]:
    """Read no provenance. Reject unaccounted-for corruption, rather than label it."""
    initial = check_clean(public)
    allowed = {"ledger differs from postings reconstructed from documents"}
    if set(initial.errors) - allowed:
        raise DataError("public records violate supported scenario invariants")
    rows = {row.row_id: row for row in public.ledger}
    repaired = dict(rows)
    observed = []
    invoices = {invoice.invoice_id: invoice for invoice in public.invoices}
    for invoice in public.invoices:
        sale = sorted((row for row in public.ledger if row.invoice_id == invoice.invoice_id
                       and row.payment_id is None), key=lambda row: row.row_id)
        if len(sale) != 4:
            continue
        if any(r.entity_id != invoice.entity_id or r.currency != invoice.currency
               or timestamp(r.timestamp) != timestamp(invoice.issued_at) for r in sale):
            continue
        ar = [r for r in sale if r.account == "receivable" and r.debit_minor == invoice.total_minor]
        revenue = [r for r in sale if r.account == "revenue" and r.credit_minor == invoice.total_minor]
        if len(ar) == len(revenue) == 2:
            # Keep either identical posting; row identity cannot decide which one was original.
            del repaired[ar[1].row_id]
            del repaired[revenue[1].row_id]
            observed.append(ObservedIssue("duplicate_invoice", (invoice.invoice_id,), invoice.total_minor,
                                          invoice.currency, tuple(sorted([invoice.doc_id] + [r.row_id for r in sale]))))
    for payment in public.payments:
        if len(payment.invoice_refs) != 1:
            continue
        allocation = payment.invoice_refs[0]
        invoice = invoices[allocation.invoice_id]
        linked = [r for r in public.ledger if r.payment_id == payment.payment_id]
        if any(r.entity_id != invoice.entity_id or r.currency != payment.currency
               or timestamp(r.timestamp) != timestamp(payment.timestamp) for r in linked):
            continue
        bank = [r for r in linked if r.account == "bank"]
        credits = [r for r in linked if r.account == "receivable" and r.invoice_id == invoice.invoice_id]
        misclassified = [r for r in linked if r.account == "revenue" and r.invoice_id == invoice.invoice_id]
        if len(bank) != 1 or len(credits) > 1 or len(misclassified) != 1:
            continue
        actual = sum(r.credit_minor for r in credits)
        delta = allocation.allocated_minor - actual
        if delta <= 0 or misclassified[0].credit_minor != delta:
            continue
        for row in credits + misclassified:
            del repaired[row.row_id]
        reference = credits[0] if credits else misclassified[0]
        repaired[reference.row_id] = replace(reference, account="receivable", debit_minor=0,
                                              credit_minor=allocation.allocated_minor)
        observed.append(ObservedIssue("payment_allocation", tuple(sorted([invoice.invoice_id, payment.payment_id])),
                                      delta, payment.currency,
                                      tuple(sorted([invoice.doc_id, payment.doc_id] + [r.row_id for r in linked]))))
    restored = replace(public, ledger=tuple(repaired.values()),
                       manifest=replace(public.manifest, row_count=len(repaired)))
    if not check_clean(restored).ok:
        raise DataError("public discrepancy is not fully explained by supported issue families")
    return tuple(sorted(observed, key=lambda issue: issue.key))


def validate_truth(public: PublicEpisode, truth: Truth) -> None:
    truth = Truth.from_dict(truth.to_dict())
    if truth.episode_id != public.manifest.episode_id:
        raise DataError("truth episode_id mismatch")
    observed = inspect_supported_issues(public)
    expected = {issue.key: issue for issue in observed}
    if len(expected) != len(observed) or len(truth.issues) != len(observed):
        raise DataError("truth does not cover exactly the observable discrepancies")
    seen = set()
    available = evidence_ids(public)
    for issue in truth.issues:
        key = (issue.type, issue.affected_ids, issue.expected_amount_minor, issue.currency)
        if key not in expected or key in seen:
            raise DataError("truth type, affected IDs, amount or currency is unsupported")
        seen.add(key)
        required = set(expected[key].evidence)
        for candidate in issue.acceptable_evidence_sets:
            if not required <= set(candidate) <= available:
                raise DataError("truth contains insufficient or inaccessible evidence")
