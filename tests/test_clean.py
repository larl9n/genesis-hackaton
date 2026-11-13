from dataclasses import replace
import json
from pathlib import Path
import random
import unittest

from genesis_fintech.domain.models import DataError, PublicEpisode
from genesis_fintech.evaluation.clean import check_clean
from genesis_fintech.generation.clean import CleanConfig, generate_clean


class GenerationTests(unittest.TestCase):
    def test_same_seed_exactly_reproduces_history_and_documents(self):
        a, b = generate_clean(42), generate_clean(42)
        self.assertEqual(a, b)
        self.assertNotEqual(a.public, generate_clean(43).public)

    def test_generator_does_not_change_global_random_state(self):
        state = random.getstate()
        generate_clean(3)
        self.assertEqual(state, random.getstate())

    def test_default_size_and_clean_accounting_over_many_seeds(self):
        for seed in range(50):
            public = generate_clean(seed).public
            with self.subTest(seed=seed):
                self.assertGreaterEqual(len(public.ledger), 200)
                self.assertLessEqual(len(public.ledger), 2000)
                self.assertGreaterEqual(public.manifest.document_count, 20)
                self.assertLessEqual(public.manifest.document_count, 200)
                self.assertTrue(check_clean(public).ok, check_clean(public).errors)

    def test_public_schema_round_trip_does_not_expose_seed_or_history(self):
        generated = generate_clean(42)
        data = json.loads(json.dumps(generated.public.to_dict()))
        self.assertEqual(PublicEpisode.from_dict(data), generated.public)
        self.assertNotIn('seed', json.dumps(data))
        self.assertNotIn('latent_history', json.dumps(data))
        self.assertEqual(generated.provenance['seed'], 42)
        with self.assertRaises(DataError):
            PublicEpisode.from_dict({**data, 'truth': []})

    def test_split_and_partial_payments_are_valid(self):
        public = generate_clean(7, CleanConfig(invoice_count=5, split_percent=100, partial_percent=100)).public
        self.assertEqual(len(public.payments), 10)
        self.assertTrue(check_clean(public).ok)
        paid = {invoice.invoice_id: 0 for invoice in public.invoices}
        for payment in public.payments:
            for ref in payment.invoice_refs:
                paid[ref.invoice_id] += ref.allocated_minor
        self.assertTrue(all(0 < paid[i.invoice_id] < i.total_minor for i in public.invoices))

    def test_currency_exponents_and_timezones(self):
        for code, exponent in [('JPY', 0), ('KWD', 3), ('USD', 2)]:
            public = generate_clean(3, CleanConfig(invoice_count=3, base_currency=code, timezone='America/New_York')).public
            self.assertEqual(public.manifest.currency_exponents[code], exponent)
            self.assertTrue(check_clean(public).ok)

    def test_invalid_config_and_seed(self):
        for patch in [dict(invoice_count=True), dict(invoice_count=0), dict(invoice_count=61),
                      dict(base_currency='missing'), dict(partial_percent=101), dict(timezone='bad/zone')]:
            with self.subTest(patch=patch), self.assertRaises(DataError):
                CleanConfig(**patch)
        for seed in [True, -1, 1.0, '42']:
            with self.assertRaises(DataError):
                generate_clean(seed)


class IndependentCheckerTests(unittest.TestCase):
    def setUp(self):
        self.public = generate_clean(42, CleanConfig(invoice_count=3)).public

    def test_balanced_duplicate_is_not_clean(self):
        # A balanced extra pair passes a sum-only checker, but duplicates a real invoice.
        invoice = self.public.invoices[0]
        originals = [r for r in self.public.ledger if r.invoice_id == invoice.invoice_id and r.payment_id is None]
        extras = tuple(replace(r, row_id=f'row_extra_{index}') for index, r in enumerate(originals))
        changed = replace(self.public, ledger=self.public.ledger + extras,
                          manifest=replace(self.public.manifest, row_count=len(self.public.ledger) + 2))
        report = check_clean(changed)
        self.assertFalse(report.ok)
        self.assertNotIn('ledger debits and credits do not balance per currency', report.errors)
        self.assertIn('ledger differs from postings reconstructed from documents', report.errors)

    def test_hand_authored_fixture_with_remaining_receivable(self):
        fixture = Path(__file__).parent / 'fixtures/clean_minimal.json'
        public = PublicEpisode.from_dict(json.loads(fixture.read_text()))
        self.assertTrue(check_clean(public).ok)
        receivable = sum(row.debit_minor - row.credit_minor for row in public.ledger
                         if row.account == 'receivable')
        self.assertEqual(receivable, 4000)

    def test_unknown_invoice_is_rejected_without_crashing(self):
        payment = self.public.payments[0]
        bad = replace(payment, invoice_refs=(replace(payment.invoice_refs[0], invoice_id='invoice_missing'),))
        public = replace(self.public, payments=(bad,) + self.public.payments[1:])
        self.assertIn('payment references unknown invoice', check_clean(public).errors)

    def test_payment_and_manifest_tampering(self):
        payment = self.public.payments[0]
        public = replace(self.public, payments=(replace(payment, amount_minor=payment.amount_minor + 1),)
                         + self.public.payments[1:], manifest=replace(self.public.manifest, row_count=1))
        errors = check_clean(public).errors
        self.assertIn('payment amount differs from allocations', errors)
        self.assertIn('manifest row_count differs from records', errors)

    def test_repeated_ids_are_rejected(self):
        rows = self.public.ledger
        public = replace(self.public, ledger=(replace(rows[0], row_id=rows[1].row_id),) + rows[1:])
        self.assertIn('duplicate row IDs', check_clean(public).errors)

    def test_period_end_is_exclusive(self):
        invoice = self.public.invoices[0]
        invoice = replace(invoice, issued_at=self.public.manifest.period_end,
                          due_at='2026-12-01T00:00:00+05:00')
        public = replace(self.public, invoices=(invoice,) + self.public.invoices[1:])
        self.assertIn('invoice recognition falls outside reporting period', check_clean(public).errors)

    def test_no_silent_cross_currency_comparison(self):
        invoice = self.public.invoices[0]
        public = replace(self.public, invoices=(replace(invoice, currency='USD'),) + self.public.invoices[1:])
        self.assertIn('clean checker does not support cross-currency invoices', check_clean(public).errors)

    def test_order_does_not_change_checker_result(self):
        public = replace(self.public, ledger=self.public.ledger[::-1], invoices=self.public.invoices[::-1],
                         payments=self.public.payments[::-1])
        self.assertTrue(check_clean(public).ok)


if __name__ == '__main__':
    unittest.main()
