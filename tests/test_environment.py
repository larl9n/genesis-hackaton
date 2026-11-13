import copy
import json
import unittest

from genesis_fintech.domain.findings import oracle_submission
from genesis_fintech.domain.models import DataError
from genesis_fintech.environment.calculator import calculate
from genesis_fintech.environment.core import AuditEnv, EpisodeFinished
from genesis_fintech.generation.scenario import ScenarioConfig, generate_scenario


class CalculatorTests(unittest.TestCase):
    def test_exact_decimal_arithmetic(self):
        self.assertEqual(calculate('0.1 + 0.2'), '0.3')
        self.assertEqual(calculate('-(10 + 5) / 2'), '-7.5')
        self.assertEqual(calculate('100 * 10'), '1000')

    def test_code_and_unbounded_expressions_are_rejected(self):
        for expression in ["__import__('os').getcwd()", 'open("a")', '2**10000', '1/0', 'True',
                           '1e20', '0x10', '[1][0]', '1' * 257, '-' * 20 + '1', '0.1' * 100]:
            with self.subTest(expression=expression), self.assertRaises(DataError):
                calculate(expression)


class EnvironmentTests(unittest.TestCase):
    def action(self, name, **params):
        return dict(action=name, params=params)

    def setUp(self):
        self.env = AuditEnv()
        self.initial, info = self.env.reset(42)
        self.assertEqual(info, {})

    def test_initial_observation_and_tools_hide_private_state(self):
        data = json.dumps(self.initial)
        for forbidden in ['seed', 'issues', 'provenance', 'changes', 'acceptable_evidence']:
            self.assertNotIn(forbidden, data)
        for name in ['truth', 'provenance', 'seed']:
            observation, reward, terminated, truncated, info = self.env.step(self.action('get_record', table=name, id='x'))
            self.assertEqual(observation['error'], 'invalid_request')
            self.assertEqual((reward, terminated, truncated, info), (0, False, False, {}))

    def test_pages_are_bounded_stable_and_cover_table(self):
        cursor, seen = None, []
        while True:
            observation, reward, *_ = self.env.step(self.action('list_records', table='ledger', cursor=cursor, limit=50))
            page = observation['result']
            self.assertLessEqual(len(page['records']), 50)
            self.assertEqual(reward, 0)
            seen.extend(row['row_id'] for row in page['records'])
            cursor = page['next_cursor']
            if cursor is None:
                break
        self.assertEqual(len(seen), self.initial['manifest']['row_count'])
        self.assertEqual(len(seen), len(set(seen)))

    def test_record_and_document_retrieval_and_observation_copy(self):
        first = self.env.step(self.action('list_records', table='invoices', cursor=None, limit=1))[0]['result']['records'][0]
        fetched = self.env.step(self.action('get_record', table='invoices', id=first['invoice_id']))[0]['result']
        document = self.env.step(self.action('get_document', doc_id=first['doc_id']))[0]['result']
        self.assertEqual(fetched, document)
        document['total_minor'] = 1
        again = self.env.step(self.action('get_document', doc_id=first['doc_id']))[0]['result']
        self.assertEqual(again['total_minor'], first['total_minor'])

    def test_bad_requests_consume_budget_and_do_not_end_episode(self):
        requests = [None, [], {}, self.action('shell', command='ls'), self.action('calculator', expression='1/0'),
                    self.action('list_records', table='ledger', cursor=None, limit=51),
                    self.action('list_records', table='ledger', cursor='bad!', limit=1),
                    self.action('get_document', doc_id=['not-a-string'])]
        for index, action in enumerate(requests):
            result = self.env.step(action)
            self.assertEqual(result[0]['error'], 'invalid_request')
            self.assertEqual(result[0]['remaining_steps'], 99 - index)
            self.assertFalse(result[2] or result[3])

    def test_non_json_and_oversized_requests_are_bounded_failures(self):
        for raw in [object(), {'bad': float('nan')}, {'bad': 'x' * (513 * 1024)}]:
            observation, reward, terminated, truncated, _ = self.env.step(raw)
            self.assertEqual(observation['error'], 'invalid_request')
            self.assertEqual((reward, terminated, truncated), (0, False, False))
            self.assertLess(len(json.dumps(self.env.trajectory[-1])), 1000)

    def test_oversized_submission_is_malformed_and_terminates(self):
        result = self.env.step(self.action('submit', episode_id=self.initial['manifest']['episode_id'],
                                          findings=[], extra='x' * (513 * 1024)))
        self.assertEqual((result[1], result[2], result[3]), (-1, True, False))

    def test_supported_submission_and_cost(self):
        self.env.step(self.action('calculator', expression='0.1+0.2'))
        truth = generate_scenario(42).truth
        result = self.env.step(self.action('submit', **oracle_submission(truth)))
        self.assertEqual((result[2], result[3]), (True, False))
        self.assertAlmostEqual(result[1], 0.998)
        self.assertEqual(self.env.evaluation_result()['tp'], 2)
        with self.assertRaises(EpisodeFinished):
            self.env.step(self.action('submit', **oracle_submission(truth)))

    def test_malformed_submission_terminates_with_minus_one(self):
        result = self.env.step(self.action('submit', episode_id='episode_wrong', findings=[]))
        self.assertEqual((result[1], result[2], result[3]), (-1, True, False))
        self.assertFalse(self.env.evaluation_result()['valid_submission'])

    def test_submission_is_allowed_on_last_step(self):
        env = AuditEnv(max_steps=1)
        env.reset(42)
        result = env.step(self.action('submit', **oracle_submission(generate_scenario(42).truth)))
        self.assertEqual((result[1], result[2], result[3]), (1, True, False))

    def test_step_limit_truncates_to_empty_submission(self):
        env = AuditEnv(max_steps=1)
        env.reset(42)
        result = env.step(self.action('calculator', expression='1+1'))
        self.assertEqual((result[1], result[2], result[3]), (-1, False, True))
        self.assertEqual(env.evaluation_result()['tp'], 0)
        self.assertEqual(env.evaluation_result()['inspection_steps'], 1)

    def test_wall_time_limit_with_controlled_clock(self):
        now = [0]
        env = AuditEnv(clock=lambda: now[0], wall_time_seconds=1)
        env.reset(42)
        now[0] = 1
        result = env.step(self.action('submit', **oracle_submission(generate_scenario(42).truth)))
        self.assertEqual((result[2], result[3]), (False, True))
        self.assertEqual(env.evaluation_result()['tp'], 0)

    def test_submission_finishing_after_deadline_is_discarded(self):
        ticks = iter([0, 0, 0, 2])
        env = AuditEnv(clock=lambda: next(ticks), wall_time_seconds=1)
        env.reset(42)
        result = env.step(self.action('submit', **oracle_submission(generate_scenario(42).truth)))
        self.assertEqual((result[2], result[3]), (False, True))
        self.assertEqual(env.evaluation_result()['tp'], 0)
        self.assertEqual(env.evaluation_result()['inspection_steps'], 0)

    def test_cursor_cannot_be_reused_for_another_table(self):
        cursor = self.env.step(self.action('list_records', table='ledger', cursor=None, limit=1))[0]['result']['next_cursor']
        result = self.env.step(self.action('list_records', table='invoices', cursor=cursor, limit=1))
        self.assertEqual(result[0]['error'], 'invalid_request')

    def test_evaluation_keeps_reward_and_diagnostics_host_side(self):
        env = AuditEnv(mode='evaluation')
        env.reset(42)
        result = env.step(self.action('submit', **oracle_submission(generate_scenario(42).truth)))
        self.assertEqual(result[1], 0)
        self.assertEqual(result[4], {})
        self.assertNotIn('tp', json.dumps(result[0]))
        self.assertEqual(env.evaluation_result()['reward'], 1)
        self.assertEqual(env.trajectory[-1]['reward'], 0)

    def test_reset_isolates_state_and_replay_is_exact(self):
        actions = [self.action('list_records', table='ledger', cursor=None, limit=2),
                   self.action('calculator', expression='10 / 4')]
        original = [self.env.step(action) for action in actions]
        self.env.reset(42)
        self.assertEqual([self.env.step(action) for action in actions], original)
        self.assertEqual(len(self.env.trajectory), 2)


if __name__ == '__main__':
    unittest.main()
