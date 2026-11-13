from dataclasses import replace
from pathlib import Path
import json
import unittest

from genesis_fintech.domain.findings import Truth
from genesis_fintech.domain.fx import in_period
from genesis_fintech.domain.models import Allocation, DataError, Payment, PublicEpisode
from genesis_fintech.evaluation.clean import check_clean
from genesis_fintech.evaluation.truth import validate_truth
from genesis_fintech.generation.clean import CleanConfig, generate_clean


class RefundTests(unittest.TestCase):
    def test_generated_refunds_are_clean_even_with_foreign_receipts_and_boundaries(self):
        config = CleanConfig(invoice_count=60, foreign_payment_invoices=12, boundary_invoices=4, refund_invoices=4)
        for seed in range(20):
            public = generate_clean(seed, config).public
            self.assertEqual(len([p for p in public.payments if p.amount_minor < 0]), 4)
            self.assertTrue(check_clean(public).ok, check_clean(public).errors)
            validate_truth(public, Truth(public.manifest.episode_id, ()))

    def test_refund_postings_reverse_bank_and_receivable(self):
        public = generate_clean(42, CleanConfig(refund_invoices=5)).public
        for refund in [p for p in public.payments if p.amount_minor < 0]:
            rows = [r for r in public.ledger if r.payment_id == refund.payment_id]
            if in_period(public.manifest, refund.timestamp):
                bank = next(r for r in rows if r.account == 'bank')
                ar = next(r for r in rows if r.account == 'receivable')
                self.assertEqual(bank.credit_minor, -refund.amount_minor)
                self.assertEqual(ar.debit_minor, -refund.amount_minor)

    def test_manual_refund_is_valid_but_excessive_refund_is_not(self):
        raw = json.loads((Path(__file__).parent / 'fixtures/clean_minimal.json').read_text())
        raw['manifest'].update(schema_version='0.2', row_count=8, document_count=4)
        raw['payments'].append(dict(doc_id='doc_refund', payment_id='payment_refund',
            timestamp='2026-10-05T10:00:00+05:00', currency='KZT', amount_minor=-1000,
            invoice_refs=[dict(invoice_id='invoice_manual', allocated_minor=-1000, currency='KZT')]))
        raw['ledger'].extend([
            dict(row_id='row_refund_bank', timestamp='2026-10-05T10:00:00+05:00', account='bank',
                 debit_minor=0, credit_minor=1000, currency='KZT', entity_id='entity_manual', invoice_id=None, payment_id='payment_refund'),
            dict(row_id='row_refund_ar', timestamp='2026-10-05T10:00:00+05:00', account='receivable',
                 debit_minor=1000, credit_minor=0, currency='KZT', entity_id='entity_manual', invoice_id='invoice_manual', payment_id='payment_refund'),
        ])
        public = PublicEpisode.from_dict(raw)
        self.assertTrue(check_clean(public).ok)
        changed = replace(public.payments[-1], amount_minor=-7000,
                          invoice_refs=(Allocation('invoice_manual', -7000, 'KZT'),))
        errors = check_clean(replace(public, payments=public.payments[:-1] + (changed,))).errors
        self.assertIn('refund exceeds prior allocations', errors)
        # A later refund must not hide a past over-allocation in this restricted model.
        raw['payments'][1].update(amount_minor=10000,
            invoice_refs=[dict(invoice_id='invoice_manual', allocated_minor=10000, currency='KZT')])
        raw['payments'][2].update(amount_minor=-3000,
            invoice_refs=[dict(invoice_id='invoice_manual', allocated_minor=-3000, currency='KZT')])
        raw['ledger'][4]['debit_minor'] = raw['ledger'][5]['credit_minor'] = 10000
        raw['ledger'][6]['credit_minor'] = raw['ledger'][7]['debit_minor'] = 3000
        self.assertIn('invoice is overallocated', check_clean(PublicEpisode.from_dict(raw)).errors)

    def test_refund_before_receipt_is_not_accepted_by_netting_future_cash(self):
        public = generate_clean(42, CleanConfig(invoice_count=1, refund_invoices=1)).public
        refund = next(p for p in public.payments if p.amount_minor < 0)
        invoice = public.invoices[0]
        changed = replace(refund, timestamp=invoice.issued_at)
        public = replace(public, payments=tuple(changed if p == refund else p for p in public.payments))
        self.assertIn('refund exceeds prior allocations', check_clean(public).errors)

    def test_refund_sign_and_zero_amount_are_strict(self):
        for amount, allocated in [(-1, 1), (1, -1), (0, 0)]:
            with self.assertRaises(DataError):
                Payment('doc_refund', 'payment_refund', '2026-10-01T00:00:00Z', 'KZT', amount,
                        (Allocation('invoice_a', allocated, 'KZT'),))

    def test_old_public_schema_does_not_silently_accept_new_refund_semantics(self):
        public = generate_clean(42, CleanConfig(refund_invoices=1)).public
        self.assertEqual(public.manifest.schema_version, '0.2')
        with self.assertRaises(DataError):
            replace(public, manifest=replace(public.manifest, schema_version='0.1'))


if __name__ == '__main__':
    unittest.main()
