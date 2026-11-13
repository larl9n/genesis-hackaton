import copy
from decimal import Inexact, Rounded, localcontext
import unittest

from genesis_fintech.domain.models import (
    Allocation, DataError, FxRate, Invoice, LedgerRow, Manifest, Payment, timestamp,
)
from genesis_fintech.domain.money import convert_minor


def invoice_data():
    return dict(doc_id="doc_a", invoice_id="invoice_a", entity_id="entity_a",
                issued_at="2026-10-01T10:00:00+05:00", due_at="2026-10-10T10:00:00+05:00",
                currency="KZT", total_minor=100, line_items=[
                    dict(description="Synthetic service", quantity=2, unit_price_minor=50)])


class SchemaTests(unittest.TestCase):
    def test_valid_invoice_round_trip(self):
        original = Invoice.from_dict(invoice_data())
        self.assertEqual(original, Invoice.from_dict(original.to_dict()))
        import json
        self.assertEqual(original, Invoice.from_dict(json.loads(json.dumps(original.to_dict()))))

    def test_reject_invalid_amounts(self):
        for amount in [True, False, 100.0, "100", -100, 0, 10**16]:
            with self.subTest(amount=amount), self.assertRaises(DataError):
                Invoice.from_dict({**invoice_data(), "total_minor": amount})

    def test_unknown_and_missing_fields(self):
        for data in [{**invoice_data(), "seed": 42}, {k: v for k, v in invoice_data().items() if k != "entity_id"}]:
            with self.assertRaises(DataError):
                Invoice.from_dict(data)

    def test_invoice_totals_and_dates(self):
        for patch in [dict(total_minor=101), dict(currency="kzt"), dict(due_at="2026-09-01T10:00:00+05:00")]:
            with self.subTest(patch=patch), self.assertRaises(DataError):
                Invoice.from_dict({**invoice_data(), **patch})

    def test_line_item_shape(self):
        for quantity in [True, 0, -1, 1.5]:
            data = copy.deepcopy(invoice_data())
            data["line_items"][0]["quantity"] = quantity
            with self.assertRaises(DataError):
                Invoice.from_dict(data)

    def test_timestamp_requires_real_offset_date(self):
        for value in ["2026-10-01", "2026-10-01T10:00:00", "2026-02-30T10:00:00Z", "2026-10-01T10:00:00+25:00"]:
            with self.subTest(value=value), self.assertRaises(DataError):
                timestamp(value)
        self.assertEqual(timestamp("2026-10-01T00:00:00Z"), timestamp("2026-10-01T05:00:00+05:00"))

    def test_ledger_requires_one_positive_side(self):
        data = dict(row_id="row_a", timestamp="2026-10-01T00:00:00Z", account="bank",
                    debit_minor=10, credit_minor=0, currency="KZT", entity_id="entity_a",
                    invoice_id=None, payment_id="payment_a")
        LedgerRow.from_dict(data)
        for patch in [dict(debit_minor=0), dict(credit_minor=10), dict(debit_minor=True), dict(account="unknown")]:
            with self.subTest(patch=patch), self.assertRaises(DataError):
                LedgerRow.from_dict({**data, **patch})

    def test_payment_allocation_ids_unique(self):
        allocation = Allocation("invoice_a", 50, "KZT")
        with self.assertRaises(DataError):
            Payment("doc_a", "payment_a", "2026-10-01T00:00:00Z", "KZT", 100, (allocation, allocation))

    def test_manifest_rounding_and_period(self):
        data = dict(schema_version="0.1", episode_id="episode_a", base_currency="KZT",
                    currency_exponents={"KZT": 2}, period_start="2026-10-01T00:00:00+05:00",
                    period_end="2026-11-01T00:00:00+05:00", timezone="Asia/Almaty",
                    row_count=200, document_count=100, amount_tolerance_minor=0, rounding="ROUND_HALF_EVEN")
        Manifest.from_dict(data)
        for patch in [dict(currency_exponents={"KZT": True}), dict(timezone="missing/zone"),
                      dict(schema_version="9"), dict(rounding="unknown"), dict(period_end=data["period_start"])]:
            with self.subTest(patch=patch), self.assertRaises(DataError):
                Manifest.from_dict({**data, **patch})


class MoneyTests(unittest.TestCase):
    def test_currency_exponents_and_negative_conversion(self):
        self.assertEqual(convert_minor(12345, 2, 0, "150"), 18518)
        self.assertEqual(convert_minor(100, 2, 3, "0.300"), 300)
        self.assertEqual(convert_minor(-125, 2, 2, "1"), -125)

    def test_declared_rounding(self):
        self.assertEqual(convert_minor(1, 0, 0, "0.5"), 0)
        self.assertEqual(convert_minor(1, 0, 0, "0.5", "ROUND_HALF_UP"), 1)
        self.assertEqual(convert_minor(3, 0, 0, "0.5"), 2)

    def test_caller_precision_does_not_change_money(self):
        with localcontext() as ctx:
            ctx.prec = 2
            self.assertEqual(convert_minor(123456789, 2, 2, "1.123456789"), 138698368)

    def test_reject_invalid_rates(self):
        for rate in ["NaN", "Infinity", "-1", "0", "0.0", "1e3", 1.5, True]:
            with self.subTest(rate=rate), self.assertRaises(DataError):
                convert_minor(100, 2, 2, rate)

    def test_conversion_overflow(self):
        with self.assertRaises(DataError):
            convert_minor(10**15, 0, 6, "1000000")

    def test_caller_traps_do_not_break_declared_rounding(self):
        with localcontext() as ctx:
            ctx.traps[Inexact] = True
            ctx.traps[Rounded] = True
            self.assertEqual(convert_minor(1, 0, 0, "0.5"), 0)

    def test_fx_evidence_key(self):
        self.assertEqual(FxRate("2026-10-01", "USD", "KZT", "500.5").evidence_id,
                         "fx_2026-10-01_USD_KZT")


if __name__ == "__main__":
    unittest.main()
