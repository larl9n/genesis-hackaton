"""Reconstruct expected postings from public documents; never read provenance."""

from collections import Counter, defaultdict
from dataclasses import dataclass

from genesis_fintech.domain.models import PublicEpisode, timestamp


@dataclass(frozen=True)
class CleanReport:
    errors: tuple[str, ...]
    ledger_rows: int
    invoices: int
    payments: int

    @property
    def ok(self) -> bool:
        return not self.errors

    def to_dict(self) -> dict:
        return {"ok": self.ok, "errors": list(self.errors), "ledger_rows": self.ledger_rows,
                "invoices": self.invoices, "payments": self.payments,
                "scope": "single-currency clean sales and allocated positive payments"}


def check_clean(episode: PublicEpisode) -> CleanReport:
    """Validate only the documented clean model, not arbitrary accounting books."""
    errors = []
    manifest = episode.manifest
    base = manifest.base_currency
    start, end = timestamp(manifest.period_start), timestamp(manifest.period_end)
    if manifest.row_count != len(episode.ledger):
        errors.append("manifest row_count differs from records")
    if manifest.document_count != len(episode.invoices) + len(episode.payments):
        errors.append("manifest document_count differs from records")
    if manifest.rounding != episode.policy.rounding:
        errors.append("manifest and policy rounding differ")
    namespaces = (
        ("row", [r.row_id for r in episode.ledger]),
        ("invoice", [i.invoice_id for i in episode.invoices]),
        ("payment", [p.payment_id for p in episode.payments]),
        ("document", [d.doc_id for d in (*episode.invoices, *episode.payments)]),
        ("FX", [r.evidence_id for r in episode.fx]),
    )
    all_ids = []
    for name, ids in namespaces:
        if len(ids) != len(set(ids)):
            errors.append(f"duplicate {name} IDs")
        all_ids.extend(ids)
    if len(all_ids) != len(set(all_ids)):
        errors.append("IDs overlap across evidence namespaces")
    invoices = {i.invoice_id: i for i in episode.invoices}
    paid = defaultdict(int)
    expected = Counter()

    def posting(at, account, debit, credit, entity, invoice_id, payment_id):
        return (timestamp(at), account, debit, credit, base, entity, invoice_id, payment_id)

    for invoice in episode.invoices:
        if invoice.currency != base:
            errors.append("clean checker does not support cross-currency invoices")
        if not start <= timestamp(invoice.issued_at) < end:
            errors.append("invoice recognition falls outside reporting period")
        expected[posting(invoice.issued_at, "receivable", invoice.total_minor, 0,
                         invoice.entity_id, invoice.invoice_id, None)] += 1
        expected[posting(invoice.issued_at, "revenue", 0, invoice.total_minor,
                         invoice.entity_id, invoice.invoice_id, None)] += 1
    for payment in episode.payments:
        if payment.currency != base:
            errors.append("clean checker does not support cross-currency payments")
        if not start <= timestamp(payment.timestamp) < end:
            errors.append("payment falls outside reporting period")
        if not payment.invoice_refs:
            errors.append("unallocated payment is outside the supported clean model")
            continue
        allocated = 0
        entities = set()
        for allocation in payment.invoice_refs:
            invoice = invoices.get(allocation.invoice_id)
            if invoice is None:
                errors.append("payment references unknown invoice")
                continue
            entities.add(invoice.entity_id)
            if allocation.currency != invoice.currency or allocation.currency != payment.currency:
                errors.append("allocation currency mismatch; conversion is not implicit")
                continue
            if timestamp(payment.timestamp) < timestamp(invoice.issued_at):
                errors.append("payment precedes invoice in the supported clean model")
            allocated += allocation.allocated_minor
            paid[invoice.invoice_id] += allocation.allocated_minor
            expected[posting(payment.timestamp, "receivable", 0, allocation.allocated_minor,
                             invoice.entity_id, invoice.invoice_id, payment.payment_id)] += 1
        if allocated != payment.amount_minor:
            errors.append("payment amount differs from allocations")
        if len(entities) != 1:
            errors.append("payment must belong to one known entity in the clean model")
        else:
            expected[posting(payment.timestamp, "bank", payment.amount_minor, 0,
                             next(iter(entities)), None, payment.payment_id)] += 1
    for invoice_id, total_paid in paid.items():
        if total_paid > invoices[invoice_id].total_minor:
            errors.append("invoice is overallocated")
    actual = Counter()
    balances = defaultdict(int)
    for row in episode.ledger:
        actual[(timestamp(row.timestamp), row.account, row.debit_minor, row.credit_minor,
                row.currency, row.entity_id, row.invoice_id, row.payment_id)] += 1
        balances[row.currency] += row.debit_minor - row.credit_minor
        if row.currency != base:
            errors.append("clean checker does not support cross-currency postings")
    if any(balances.values()):
        errors.append("ledger debits and credits do not balance per currency")
    if expected != actual:
        errors.append("ledger differs from postings reconstructed from documents")
    return CleanReport(tuple(sorted(set(errors))), len(episode.ledger), len(episode.invoices), len(episode.payments))
