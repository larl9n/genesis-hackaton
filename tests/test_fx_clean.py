from dataclasses import replace
from datetime import timezone
import unittest

from genesis_fintech.domain.fx import in_period, payment_date, payment_quote, payment_value_minor
from genesis_fintech.domain.models import DataError, timestamp
from genesis_fintech.evaluation.clean import check_clean
from genesis_fintech.generation.clean import CleanConfig, generate_clean


def fx_config(**patch):
    return CleanConfig(invoice_count=60, foreign_payment_invoices=12, boundary_invoices=4, **patch)


class FxCleanTests(unittest.TestCase):
    def test_fx_and_boundary_clean_history_over_50_seeds(self):
        for seed in range(50):
            public = generate_clean(seed, fx_config()).public
            with self.subTest(seed=seed):
                self.assertTrue(check_clean(public).ok, check_clean(public).errors)
                self.assertTrue(public.fx)
                self.assertEqual(public.manifest.currency_exponents, {'KZT': 2, 'USD': 2})
                self.assertGreaterEqual(public.manifest.row_count, 200)
                self.assertLessEqual(public.manifest.document_count, 200)

    def test_fx_allocations_are_in_base_minor_units(self):
        public = generate_clean(42, fx_config()).public
        for payment in public.payments:
            self.assertEqual(sum(a.allocated_minor for a in payment.invoice_refs), payment_value_minor(public, payment))
            self.assertTrue(all(a.currency == 'KZT' for a in payment.invoice_refs))

    def test_period_edges_are_valid_decoys(self):
        public = generate_clean(42, fx_config()).public
        start, end = timestamp(public.manifest.period_start), timestamp(public.manifest.period_end)
        self.assertTrue(any(timestamp(i.issued_at) == start for i in public.invoices))
        self.assertTrue(any(timestamp(i.issued_at) == end for i in public.invoices))
        for invoice in public.invoices:
            postings = [row for row in public.ledger if row.invoice_id == invoice.invoice_id and row.payment_id is None]
            self.assertEqual(len(postings), 2 if in_period(public.manifest, invoice.issued_at) else 0)
        for payment in public.payments:
            postings = [row for row in public.ledger if row.payment_id == payment.payment_id]
            self.assertEqual(len(postings), 2 if in_period(public.manifest, payment.timestamp) else 0)

    def test_missing_or_ambiguous_quote_is_rejected(self):
        public = generate_clean(42, fx_config()).public
        payment = next(p for p in public.payments if p.currency != 'KZT')
        quote = payment_quote(public, payment)
        missing = replace(public, fx=tuple(q for q in public.fx if q != quote))
        self.assertFalse(check_clean(missing).ok)
        ambiguous = replace(public, fx=public.fx + (quote,))
        self.assertFalse(check_clean(ambiguous).ok)

    def test_fx_date_uses_manifest_timezone_not_timestamp_text_date(self):
        public = generate_clean(42, fx_config()).public
        self.assertEqual(payment_date(public.manifest, '2026-10-01T21:30:00Z'), '2026-10-02')
        converted = tuple(replace(p, timestamp=timestamp(p.timestamp).astimezone(timezone.utc).isoformat())
                          for p in public.payments)
        self.assertTrue(check_clean(replace(public, payments=converted)).ok)

    def test_supported_minor_unit_exponents(self):
        for base, foreign, rate in [('JPY', 'USD', '150.25'), ('KWD', 'EUR', '0.30'), ('USD', 'JPY', '0.0067')]:
            public = generate_clean(7, CleanConfig(invoice_count=10, base_currency=base,
                                                    foreign_currency=foreign, foreign_rate=rate,
                                                    foreign_payment_invoices=5)).public
            self.assertTrue(check_clean(public).ok, check_clean(public).errors)

    def test_legacy_config_keeps_zero_new_features_and_is_round_trippable(self):
        from genesis_fintech.generation.storage import read_json
        from pathlib import Path
        legacy = read_json(Path('configs/clean.json'))
        parsed = CleanConfig.from_dict(legacy)
        self.assertEqual(parsed.to_dict(), legacy)
        self.assertEqual(parsed.foreign_payment_invoices, 0)
        self.assertEqual(parsed.boundary_invoices, 0)

    def test_infeasible_fx_and_invalid_configs_fail_clearly(self):
        for patch in [dict(foreign_payment_invoices=True), dict(foreign_currency='KZT', foreign_payment_invoices=1),
                      dict(foreign_rate='NaN'), dict(boundary_invoices=61),
                      dict(config_version='0.1', foreign_payment_invoices=1)]:
            with self.subTest(patch=patch), self.assertRaises(DataError):
                CleanConfig(**patch)
        with self.assertRaises(DataError):
            generate_clean(7, CleanConfig(foreign_payment_invoices=1, foreign_rate='999999999999'))


if __name__ == '__main__':
    unittest.main()
