import copy
from dataclasses import replace
import itertools
import unittest

from genesis_fintech.domain.findings import Finding, Issue, Submission, Truth, oracle_submission
from genesis_fintech.domain.models import DataError, PublicEpisode
from genesis_fintech.evaluation.scoring import evaluate_submission, score_submission
from genesis_fintech.generation.scenario import ScenarioConfig, generate_scenario


class ScoringTests(unittest.TestCase):
    def setUp(self):
        self.scenario = generate_scenario(42)
        self.perfect = oracle_submission(self.scenario.truth)

    def score(self, raw, steps=0):
        return evaluate_submission(raw, self.scenario.truth, self.scenario.public, steps)

    def test_perfect_supported_findings_reach_ceiling(self):
        score = self.score(self.perfect)
        self.assertEqual((score.tp, score.fp, score.fn), (2, 0, 0))
        self.assertEqual((score.precision, score.recall, score.f1, score.reward), (1, 1, 1, 1))

    def test_abstention_loses_on_faulty_books(self):
        score = self.score({**self.perfect, 'findings': []})
        self.assertEqual((score.tp, score.fp, score.fn, score.reward), (0, 0, 2, -1))

    def test_clean_abstention_beats_false_alarm(self):
        clean = generate_scenario(42, ScenarioConfig(duplicate_invoices=0, allocation_errors=0))
        empty = oracle_submission(clean.truth)
        abstain = evaluate_submission(empty, clean.truth, clean.public)
        false = evaluate_submission({**empty, 'findings': self.perfect['findings'][:1]}, clean.truth, clean.public)
        self.assertEqual((abstain.f1, abstain.reward), (1, 1))
        self.assertEqual((false.f1, false.reward), (0, -1))

    def test_duplicate_claim_gets_no_second_credit(self):
        raw = {**self.perfect, 'findings': self.perfect['findings'] + self.perfect['findings'][:1]}
        result = self.score(raw)
        self.assertEqual((result.tp, result.fp, result.fn), (2, 1, 0))
        self.assertAlmostEqual(result.f1, 0.8)

    def test_unsupported_evidence_and_guessed_ids_fail(self):
        for evidence in [[], ['row_guessed'], self.perfect['findings'][0]['evidence_ids'][:-1],
                         self.perfect['findings'][0]['evidence_ids'] + ['doc_guessed']]:
            raw = copy.deepcopy(self.perfect)
            raw['findings'] = [{**raw['findings'][0], 'evidence_ids': evidence}]
            with self.subTest(evidence=evidence):
                self.assertEqual((self.score(raw).tp, self.score(raw).fp), (0, 1))

    def test_wrong_type_amount_currency_or_affected_ids_fail(self):
        for patch in [dict(type='period_cutoff'), dict(claimed_amount_minor=0), dict(currency='USD'),
                      dict(affected_ids=['invoice_guessed'])]:
            raw = {**self.perfect, 'findings': [{**self.perfect['findings'][0], **patch}]}
            with self.subTest(patch=patch):
                self.assertEqual(self.score(raw).tp, 0)

    def test_text_does_not_change_reward_and_ids_are_sets(self):
        raw = copy.deepcopy(self.perfect)
        for finding in raw['findings']:
            finding['explanation'] = 'A persuasive explanation changes no structured fields.'
            finding['affected_ids'] = finding['affected_ids'][::-1] * 2
            finding['evidence_ids'] = finding['evidence_ids'][::-1]
        self.assertEqual(self.score(raw), self.score(self.perfect))

    def test_step_cost_is_small_and_only_terminal(self):
        self.assertAlmostEqual(self.score(self.perfect, 10).reward, 0.98)
        self.assertAlmostEqual(self.score(self.perfect, 20).reward, 0.96)
        self.assertEqual(self.score({**self.perfect, 'findings': []}, 100).reward, -1)

    def test_malformed_submissions_always_receive_minus_one(self):
        cases = [None, [], {}, {**self.perfect, 'episode_id': 'episode_wrong'},
                 {**self.perfect, 'extra': True}, {**self.perfect, 'findings': self.perfect['findings'] * 16}]
        for patch in [dict(claimed_amount_minor=True), dict(claimed_amount_minor=1.0),
                      dict(evidence_ids=['doc_x'] * 11), dict(explanation='x' * 1001), dict(type='unknown')]:
            cases.append({**self.perfect, 'findings': [{**self.perfect['findings'][0], **patch}]})
        for raw in cases:
            with self.subTest(raw=raw):
                score = self.score(raw)
                self.assertEqual(score.reward, -1)
                self.assertFalse(score.valid_submission)

    def test_flag_all_attack_performs_poorly(self):
        guesses = [{**self.perfect['findings'][0], 'affected_ids': [row.row_id]}
                   for row in self.scenario.public.ledger[:30]]
        self.assertEqual(self.score({**self.perfect, 'findings': guesses}).reward, -1)

    def test_maximum_matching_is_order_invariant_with_overlapping_tolerance(self):
        # This isolates matching math from the separate public-record truth verifier.
        original = self.scenario.truth.issues[0]
        first = replace(original, issue_id='issue_a', expected_amount_minor=100)
        second = replace(original, issue_id='issue_b', expected_amount_minor=102)
        truth = replace(self.scenario.truth, issues=(first, second))
        public = replace(self.scenario.public,
                         manifest=replace(self.scenario.public.manifest, amount_tolerance_minor=1))
        base = oracle_submission(Truth(truth.episode_id, (first,)))['findings'][0]
        findings = [{**base, 'claimed_amount_minor': 101}, {**base, 'claimed_amount_minor': 100}]
        for order in itertools.permutations(findings):
            raw = dict(episode_id=truth.episode_id, findings=list(order))
            self.assertEqual(score_submission(raw, truth, public).tp, 2)

    def test_full_entry_point_rejects_bad_private_truth(self):
        issue = self.scenario.truth.issues[0]
        bad = replace(self.scenario.truth, issues=(replace(issue, expected_amount_minor=1),)
                      + self.scenario.truth.issues[1:])
        with self.assertRaises(DataError):
            evaluate_submission(self.perfect, bad, self.scenario.public)

    def test_id_renaming_preserves_truth_and_reward(self):
        public, truth = self.scenario.public, self.scenario.truth
        ids = {public.manifest.episode_id}
        for row in public.ledger:
            ids.update([row.row_id, row.entity_id])
        for invoice in public.invoices:
            ids.update([invoice.invoice_id, invoice.doc_id, invoice.entity_id])
        for payment in public.payments:
            ids.update([payment.payment_id, payment.doc_id])
        ids.update(issue.issue_id for issue in truth.issues)
        mapping = {old: old.split('_', 1)[0] + '_renamed_' + str(index) for index, old in enumerate(sorted(ids))}

        def rename(value):
            if isinstance(value, dict):
                return {key: rename(item) for key, item in value.items()}
            if isinstance(value, list):
                return [rename(item) for item in value]
            return mapping.get(value, value) if isinstance(value, str) else value

        changed_public = PublicEpisode.from_dict(rename(public.to_dict()))
        changed_truth = Truth.from_dict(rename(truth.to_dict()))
        actual = evaluate_submission(rename(self.perfect), changed_truth, changed_public, 7)
        self.assertEqual(actual, self.score(self.perfect, 7))

    def test_private_schemas_reject_empty_evidence_or_repeated_issue_id(self):
        raw = self.scenario.truth.to_dict()
        raw['issues'][0]['acceptable_evidence_sets'] = [[]]
        with self.assertRaises(DataError):
            Truth.from_dict(raw)
        raw = self.scenario.truth.to_dict()
        raw['issues'] = [raw['issues'][0], raw['issues'][0]]
        with self.assertRaises(DataError):
            Truth.from_dict(raw)


if __name__ == '__main__':
    unittest.main()
