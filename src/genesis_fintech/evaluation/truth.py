"""Recover observable discrepancies and validate truth without reading provenance."""

from dataclasses import dataclass, replace

from genesis_fintech.domain.findings import Truth, evidence_ids
from genesis_fintech.domain.fx import in_period, payment_quote, payment_value_minor
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
    initial = check_clean(public)
    if set(initial.errors) - {"ledger differs from postings reconstructed from documents"}:
        raise DataError("public records violate supported scenario invariants")
    repaired = {row.row_id: row for row in public.ledger}
    observed = []
    invoices = {invoice.invoice_id: invoice for invoice in public.invoices}
    base = public.manifest.base_currency
    for invoice in public.invoices:
        sale = sorted((row for row in public.ledger if row.invoice_id == invoice.invoice_id
                       and row.payment_id is None), key=lambda row: row.row_id)
        if len(sale) not in (2, 4):
            continue
        if any(r.entity_id != invoice.entity_id or r.currency != base for r in sale):
            continue
        ar = [r for r in sale if r.account == 'receivable' and r.debit_minor == invoice.total_minor]
        revenue = [r for r in sale if r.account == 'revenue' and r.credit_minor == invoice.total_minor]
        if len(ar) != len(sale) // 2 or len(revenue) != len(sale) // 2:
            continue
        times = {timestamp(r.timestamp) for r in sale}
        if len(times) != 1:
            continue
        witness = tuple(sorted([invoice.doc_id] + [r.row_id for r in sale]))
        if len(sale) == 4:
            del repaired[ar[1].row_id]
            del repaired[revenue[1].row_id]
            observed.append(ObservedIssue('duplicate_invoice', (invoice.invoice_id,), invoice.total_minor, base, witness))
        if in_period(public.manifest, sale[0].timestamp) != in_period(public.manifest, invoice.issued_at):
            for row in sale:
                if row.row_id in repaired:
                    if in_period(public.manifest, invoice.issued_at):
                        repaired[row.row_id] = replace(row, timestamp=invoice.issued_at)
                    else:
                        del repaired[row.row_id]
            observed.append(ObservedIssue('period_cutoff', (invoice.invoice_id,), invoice.total_minor, base, witness))
    for payment in public.payments:
        if payment.amount_minor < 0 or len(payment.invoice_refs) != 1 or not in_period(public.manifest, payment.timestamp):
            continue
        invoice = invoices[payment.invoice_refs[0].invoice_id]
        linked = [r for r in public.ledger if r.payment_id == payment.payment_id]
        if any(r.entity_id != invoice.entity_id or r.currency != base
               or timestamp(r.timestamp) != timestamp(payment.timestamp) for r in linked):
            continue
        bank = [r for r in linked if r.account == 'bank' and r.invoice_id is None and r.credit_minor == 0]
        credits = [r for r in linked if r.account == 'receivable' and r.invoice_id == invoice.invoice_id and r.debit_minor == 0]
        revenue = [r for r in linked if r.account == 'revenue' and r.invoice_id == invoice.invoice_id and r.debit_minor == 0]
        if len(bank) != 1 or len(credits) > 1 or len(revenue) > 1 or len(bank + credits + revenue) != len(linked):
            continue
        booked = bank[0].debit_minor
        allocated = sum(r.credit_minor for r in credits)
        misplaced = sum(r.credit_minor for r in revenue)
        if booked != allocated + misplaced:
            continue
        expected = payment_value_minor(public, payment)
        quote = payment_quote(public, payment)
        if quote is None and booked != expected:
            # A wrong bank amount in the base currency is not an FX error and cannot
            # be silently repaired while labelling only a revenue misclassification.
            continue
        affected = tuple(sorted([invoice.invoice_id, payment.payment_id]))
        witness = [invoice.doc_id, payment.doc_id] + [r.row_id for r in linked]
        if quote is not None:
            witness.append(quote.evidence_id)
        witness = tuple(sorted(witness))
        fx_error = quote is not None and booked != expected
        if fx_error:
            observed.append(ObservedIssue('fx_mismatch', affected, abs(booked - expected), base, witness))
        if misplaced:
            observed.append(ObservedIssue('payment_allocation', affected, misplaced, base, witness))
        if fx_error or misplaced:
            for row in credits + revenue:
                del repaired[row.row_id]
            reference = credits[0] if credits else revenue[0]
            repaired[reference.row_id] = replace(reference, account='receivable', debit_minor=0, credit_minor=expected)
            repaired[bank[0].row_id] = replace(bank[0], debit_minor=expected)
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
