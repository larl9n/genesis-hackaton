from dataclasses import replace
from pathlib import Path
import json
import unittest

from genesis_fintech.domain.findings import Issue, Truth, oracle_submission
from genesis_fintech.domain.fx import payment_quote
from genesis_fintech.domain.models import DataError, FxRate, LedgerRow, PublicEpisode
from genesis_fintech.evaluation.clean import check_clean
from genesis_fintech.evaluation.scoring import evaluate_submission
from genesis_fintech.evaluation.truth import validate_truth
from genesis_fintech.generation.clean import CleanConfig, generate_clean
from genesis_fintech.generation.scenario import ScenarioConfig, generate_scenario


def full_config(interactions=(), **patch):
    values = dict(clean=CleanConfig(invoice_count=60, foreign_payment_invoices=12, boundary_invoices=4),
                  duplicate_invoices=1, allocation_errors=1, fx_errors=1, cutoff_errors=1,
                  interaction_scenarios=interactions)
    values.update(patch)
    return ScenarioConfig(**values)


class FullScenarioTests(unittest.TestCase):
    def test_four_families_and_both_compositions_over_50_seeds(self):
        for interactions in [(), ('fx_allocation', 'duplicate_cutoff')]:
            config = full_config(interactions)
            for seed in range(50):
                scenario = generate_scenario(seed, config)
                with self.subTest(seed=seed, interactions=interactions):
                    validate_truth(scenario.public, scenario.truth)
                    self.assertEqual({i.type for i in scenario.truth.issues},
                                     {'duplicate_invoice', 'payment_allocation', 'fx_mismatch', 'period_cutoff'})
                    self.assertEqual(evaluate_submission(oracle_submission(scenario.truth), scenario.truth, scenario.public).reward, 1)
                    self.assertEqual(scenario, generate_scenario(seed, config))

    def test_all_16_family_combinations_can_be_configured_independently(self):
        for mask in range(16):
            counts = [(mask >> i) & 1 for i in range(4)]
            config = full_config(duplicate_invoices=counts[0], allocation_errors=counts[1],
                                 fx_errors=counts[2], cutoff_errors=counts[3])
            scenario = generate_scenario(42, config)
            validate_truth(scenario.public, scenario.truth)
            self.assertEqual(len(scenario.truth.issues), sum(counts))

    def test_interactions_share_targets_and_have_causally_dependent_mutations(self):
        scenario = generate_scenario(42, full_config(('fx_allocation', 'duplicate_cutoff')))
        by_type = {i.type: i for i in scenario.truth.issues}
        self.assertEqual(by_type['fx_mismatch'].affected_ids, by_type['payment_allocation'].affected_ids)
        self.assertEqual(by_type['duplicate_invoice'].affected_ids, by_type['period_cutoff'].affected_ids)
        changes = {c['type']: c for c in scenario.provenance['changes']}
        self.assertEqual(len(changes['period_cutoff']['before']), 4)
        fx_after = {r['row_id']: r for r in changes['fx_mismatch']['after']}
        allocation_before = changes['payment_allocation']['before'][0]
        self.assertEqual(allocation_before, fx_after[allocation_before['row_id']])

    def test_composed_provenance_replays_exact_ledger(self):
        config = full_config(('fx_allocation', 'duplicate_cutoff'))
        scenario = generate_scenario(42, config)
        rows = {row.row_id: row for row in generate_clean(42, config.clean).public.ledger}
        for change in scenario.provenance['changes']:
            for before in change['before']:
                parsed = LedgerRow.from_dict(before)
                self.assertEqual(rows.pop(parsed.row_id), parsed)
            for after in change['after']:
                parsed = LedgerRow.from_dict(after)
                self.assertNotIn(parsed.row_id, rows)
                rows[parsed.row_id] = parsed
        self.assertEqual(rows, {row.row_id: row for row in scenario.public.ledger})

    def test_date_mismatch_uses_a_real_prior_day_quote(self):
        for seed in range(20):
            scenario = generate_scenario(seed, full_config(fx_error_mode='date'))
            validate_truth(scenario.public, scenario.truth)
            issue = next(i for i in scenario.truth.issues if i.type == 'fx_mismatch')
            payment = next(p for p in scenario.public.payments if p.payment_id in issue.affected_ids)
            correct = payment_quote(scenario.public, payment)
            change = next(c for c in scenario.provenance['changes'] if c['type'] == 'fx_mismatch')
            self.assertNotEqual(correct.rate, change['applied_rate'])
            self.assertTrue(any(q.rate == change['applied_rate'] and q.date < correct.date for q in scenario.public.fx))

    def test_missing_correct_quote_cannot_support_fx_claim(self):
        scenario = generate_scenario(42, full_config())
        issue = next(i for i in scenario.truth.issues if i.type == 'fx_mismatch')
        witness = tuple(i for i in issue.acceptable_evidence_sets[0] if not i.startswith('fx_'))
        wrong = replace(issue, acceptable_evidence_sets=(witness,))
        truth = replace(scenario.truth, issues=tuple(wrong if i == issue else i for i in scenario.truth.issues))
        with self.assertRaises(DataError):
            validate_truth(scenario.public, truth)

    def test_manual_foreign_payment_proves_minor_unit_delta_without_generator(self):
        raw = json.loads((Path(__file__).parent / 'fixtures/clean_minimal.json').read_text())
        raw['manifest']['currency_exponents']['USD'] = 2
        raw['payments'][0].update(currency='USD', amount_minor=5)
        raw['payments'][1].update(currency='USD', amount_minor=7)
        raw['fx'] = [FxRate('2026-10-03', 'USD', 'KZT', '500').to_dict(),
                     FxRate('2026-10-04', 'USD', 'KZT', '500').to_dict()]
        clean = PublicEpisode.from_dict(raw)
        self.assertTrue(check_clean(clean).ok)
        raw['ledger'][2]['debit_minor'] = 2495
        raw['ledger'][3]['credit_minor'] = 2495
        public = PublicEpisode.from_dict(raw)
        witness = tuple(sorted(['doc_invoice', 'doc_payment_a', 'row_bank_a', 'row_payment_ar_a',
                                'fx_2026-10-03_USD_KZT']))
        issue = Issue('issue_manual', 'fx_mismatch', ('invoice_manual', 'payment_a'), 5, 'KZT', (witness,))
        truth = Truth(public.manifest.episode_id, (issue,))
        validate_truth(public, truth)
        self.assertEqual(evaluate_submission(oracle_submission(truth), truth, public).tp, 1)

    def test_manual_reverse_cutoff_excludes_invoice_at_period_end(self):
        raw = json.loads((Path(__file__).parent / 'fixtures/clean_minimal.json').read_text())
        raw['manifest']['period_end'] = raw['invoices'][0]['issued_at']
        raw['manifest']['row_count'] = 0
        source_rows = raw['ledger'][:2]
        raw['ledger'] = []
        self.assertTrue(check_clean(PublicEpisode.from_dict(raw)).ok)
        raw['manifest']['row_count'] = 2
        raw['ledger'] = [{**row, 'timestamp': '2026-10-02T09:59:59+05:00'} for row in source_rows]
        public = PublicEpisode.from_dict(raw)
        witness = tuple(sorted(['doc_invoice', 'row_sale_ar', 'row_sale_revenue']))
        truth = Truth(public.manifest.episode_id, (Issue('issue_manual', 'period_cutoff',
                      ('invoice_manual',), 10000, 'KZT', (witness,)),))
        validate_truth(public, truth)

    def test_unexplained_base_bank_error_cannot_be_repaired_as_allocation_only(self):
        scenario = generate_scenario(42, ScenarioConfig(duplicate_invoices=0))
        payment_id = next(x for x in scenario.truth.issues[0].affected_ids if x.startswith('payment_'))
        changed = []
        for row in scenario.public.ledger:
            if row.payment_id == payment_id and row.account == 'bank':
                row = replace(row, debit_minor=row.debit_minor + 10)
            elif row.payment_id == payment_id and row.account == 'receivable':
                row = replace(row, credit_minor=row.credit_minor + 10)
            changed.append(row)
        with self.assertRaises(DataError):
            validate_truth(replace(scenario.public, ledger=tuple(changed)), scenario.truth)

    def test_full_config_round_trip_and_legacy_config_compatibility(self):
        config = full_config(('fx_allocation', 'duplicate_cutoff'))
        self.assertEqual(ScenarioConfig.from_dict(config.to_dict()), config)
        from genesis_fintech.generation.storage import read_json
        old = read_json(Path('configs/scenario.json'))
        self.assertEqual(ScenarioConfig.from_dict(old).to_dict(), old)

    def test_renamed_ids_and_record_order_preserve_full_reward(self):
        scenario = generate_scenario(42, full_config(('fx_allocation', 'duplicate_cutoff')))
        public, truth = scenario.public, scenario.truth
        ids = {public.manifest.episode_id}
        for row in public.ledger:
            ids.update([row.row_id, row.entity_id])
        for invoice in public.invoices:
            ids.update([invoice.invoice_id, invoice.doc_id, invoice.entity_id])
        for payment in public.payments:
            ids.update([payment.payment_id, payment.doc_id])
        ids.update(issue.issue_id for issue in truth.issues)
        mapping = {old: old.split('_', 1)[0] + '_paired_' + str(i) for i, old in enumerate(sorted(ids))}

        def rename(value):
            if isinstance(value, dict):
                return {key: rename(item) for key, item in value.items()}
            if isinstance(value, list):
                return [rename(item) for item in value]
            return mapping.get(value, value) if isinstance(value, str) else value

        data = rename(public.to_dict())
        for key in ('ledger', 'invoices', 'payments', 'fx'):
            data[key].reverse()
        changed_public = PublicEpisode.from_dict(data)
        changed_truth = Truth.from_dict(rename(truth.to_dict()))
        score = evaluate_submission(oracle_submission(changed_truth), changed_truth, changed_public, 12)
        self.assertEqual(score, evaluate_submission(oracle_submission(truth), truth, public, 12))

    def test_twelve_errors_fit_observation_and_step_budgets(self):
        from genesis_fintech.evaluation.demo import run_demo
        import tempfile
        config = full_config(('fx_allocation', 'duplicate_cutoff'), duplicate_invoices=3,
                             allocation_errors=3, fx_errors=3, cutoff_errors=3)
        with tempfile.TemporaryDirectory() as directory:
            report = run_demo(42, config, Path(directory) / 'demo')
            self.assertEqual(report['metrics']['tp'], 12)
            self.assertLessEqual(report['steps'], 100)
            self.assertEqual(report['metrics']['f1'], 1)

    def test_invalid_interactions_and_unavailable_targets_are_rejected(self):
        for patch in [dict(fx_errors=1), dict(interaction_scenarios=('unknown',)),
                      dict(interaction_scenarios=('fx_allocation',)),
                      dict(interaction_scenarios=('duplicate_cutoff',), cutoff_errors=0),
                      dict(config_version='0.1', cutoff_errors=1),
                      dict(interaction_scenarios=('duplicate_cutoff', 'duplicate_cutoff'), cutoff_errors=1)]:
            with self.subTest(patch=patch), self.assertRaises(DataError):
                ScenarioConfig(**patch)


if __name__ == '__main__':
    unittest.main()
