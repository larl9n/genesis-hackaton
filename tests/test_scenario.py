from dataclasses import replace
import json
import unittest

from genesis_fintech.domain.findings import Issue, Truth, evidence_ids
from genesis_fintech.domain.models import DataError, LedgerRow
from genesis_fintech.evaluation.clean import check_clean
from genesis_fintech.evaluation.truth import inspect_supported_issues, validate_truth
from genesis_fintech.generation.clean import CleanConfig, generate_clean
from genesis_fintech.generation.scenario import ScenarioConfig, generate_scenario


class ScenarioTests(unittest.TestCase):
    def test_reproducible_and_independently_validated_over_50_seeds(self):
        for seed in range(50):
            scenario = generate_scenario(seed)
            with self.subTest(seed=seed):
                validate_truth(scenario.public, scenario.truth)
                self.assertEqual(len(scenario.truth.issues), 2)
                self.assertEqual(scenario, generate_scenario(seed))
                self.assertFalse(check_clean(scenario.public).ok)

    def test_families_can_be_disabled_independently_and_all_counts_bounded(self):
        for duplicates, allocations in [(0, 0), (1, 0), (0, 1), (3, 4), (6, 6)]:
            scenario = generate_scenario(42, ScenarioConfig(duplicate_invoices=duplicates, allocation_errors=allocations))
            validate_truth(scenario.public, scenario.truth)
            self.assertEqual(len(scenario.truth.issues), duplicates + allocations)
        scenario = generate_scenario(42, ScenarioConfig(duplicate_invoices=0, allocation_errors=0))
        self.assertEqual(scenario.public, generate_clean(42).public)
        self.assertTrue(check_clean(scenario.public).ok)

    def test_recorded_mutations_reconstruct_actual_public_ledger(self):
        scenario = generate_scenario(42)
        source = generate_clean(42)
        rows = {row.row_id: row for row in source.public.ledger}
        for change in scenario.provenance['changes']:
            for before in change['before']:
                parsed = LedgerRow.from_dict(before)
                self.assertEqual(rows.pop(parsed.row_id), parsed)
            for after in change['after']:
                parsed = LedgerRow.from_dict(after)
                self.assertNotIn(parsed.row_id, rows)
                rows[parsed.row_id] = parsed
        self.assertEqual(rows, {row.row_id: row for row in scenario.public.ledger})
        self.assertEqual(source.public.invoices, scenario.public.invoices)
        self.assertEqual(source.public.payments, scenario.public.payments)

    def test_allocation_error_keeps_ledger_balanced_and_documents_unchanged(self):
        scenario = generate_scenario(7, ScenarioConfig(duplicate_invoices=0))
        self.assertEqual(sum(r.debit_minor - r.credit_minor for r in scenario.public.ledger), 0)
        self.assertEqual(len(inspect_supported_issues(scenario.public)), 1)

    def test_fully_missing_allocation_has_observable_complete_evidence(self):
        scenario = generate_scenario(7, ScenarioConfig(duplicate_invoices=0, allocation_mode='missing'))
        validate_truth(scenario.public, scenario.truth)
        issue = scenario.truth.issues[0]
        payment_id = next(i for i in issue.affected_ids if i.startswith('payment_'))
        linked = [row for row in scenario.public.ledger if row.payment_id == payment_id]
        self.assertEqual({row.account for row in linked}, {'bank', 'revenue'})
        self.assertEqual(len(issue.acceptable_evidence_sets[0]), 4)

    def test_truth_amount_and_evidence_are_checked_against_records(self):
        scenario = generate_scenario(42)
        original = scenario.truth.issues[0]
        for wrong in [replace(original, expected_amount_minor=original.expected_amount_minor + 1),
                      replace(original, currency='USD'), replace(original, affected_ids=('invoice_unknown',)),
                      replace(original, acceptable_evidence_sets=((original.acceptable_evidence_sets[0][0],),))]:
            truth = replace(scenario.truth, issues=(wrong,) + scenario.truth.issues[1:])
            with self.subTest(wrong=wrong), self.assertRaises(DataError):
                validate_truth(scenario.public, truth)

    def test_no_missing_or_repeated_labels(self):
        scenario = generate_scenario(42)
        for issues in [(), scenario.truth.issues[:1],
                       (scenario.truth.issues[0], replace(scenario.truth.issues[0], issue_id='issue_extra'))]:
            with self.assertRaises(DataError):
                validate_truth(scenario.public, replace(scenario.truth, issues=issues))

    def test_additional_unsupported_corruption_is_not_ignored(self):
        scenario = generate_scenario(42)
        row = scenario.public.ledger[0]
        public = replace(scenario.public, ledger=(replace(row, entity_id='entity_unknown'),) + scenario.public.ledger[1:])
        with self.assertRaises(DataError):
            validate_truth(public, scenario.truth)

    def test_public_does_not_include_error_labels(self):
        scenario = generate_scenario(42)
        raw = json.dumps(scenario.public.to_dict())
        for private in ['acceptable_evidence_sets', 'issue_', 'scenario_config', 'seed', 'changes']:
            self.assertNotIn(private, raw)
        self.assertTrue(all(set(s) <= evidence_ids(scenario.public) for issue in scenario.truth.issues
                            for s in issue.acceptable_evidence_sets))

    def test_order_perturbation_does_not_change_truth_validity(self):
        scenario = generate_scenario(42)
        public = replace(scenario.public, ledger=scenario.public.ledger[::-1],
                         invoices=scenario.public.invoices[::-1], payments=scenario.public.payments[::-1])
        validate_truth(public, scenario.truth)

    def test_invalid_counts_and_versions(self):
        for patch in [dict(duplicate_invoices=True), dict(allocation_errors=-1), dict(duplicate_invoices=12, allocation_errors=1),
                      dict(clean=CleanConfig(invoice_count=1)), dict(config_version='9')]:
            with self.subTest(patch=patch), self.assertRaises(DataError):
                ScenarioConfig(**patch)


if __name__ == '__main__':
    unittest.main()
