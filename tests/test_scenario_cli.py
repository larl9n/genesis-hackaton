from pathlib import Path
import json
import os
import subprocess
import sys
import tempfile
import unittest

from genesis_fintech.domain.findings import oracle_submission
from genesis_fintech.evaluation.scoring import evaluate_submission
from genesis_fintech.generation.scenario import generate_scenario
from genesis_fintech.generation.storage import load_scenario, write_scenario


class ScenarioCliTests(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, '-m', 'genesis_fintech', *args],
                              env=dict(os.environ, PYTHONPATH='src'), text=True, capture_output=True, timeout=15)

    def test_scenario_storage_round_trip_and_truth_verification(self):
        with tempfile.TemporaryDirectory() as directory:
            generated = generate_scenario(42)
            path = Path(directory) / 'episode'
            write_scenario(generated, path)
            public, truth = load_scenario(path)
            self.assertEqual((public, truth), (generated.public, generated.truth))
            self.assertEqual(evaluate_submission(oracle_submission(truth), truth, public).reward, 1)

    def test_demo_runs_full_episode_and_exports_only_requested_observations(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'demo'
            run = self.run_cli('demo', '--seed', '42', '--config', 'configs/scenario.json', '--output', str(output))
            self.assertEqual(run.returncode, 0, run.stderr + run.stdout)
            summary = json.loads(run.stdout)
            self.assertEqual(summary['policy'], 'evaluator_oracle')
            self.assertEqual(summary['metrics']['tp'], 2)
            self.assertEqual(summary['metrics']['f1'], 1)
            trajectory = [json.loads(line) for line in (output / 'trajectories.jsonl').read_text().splitlines()]
            self.assertTrue(trajectory[-1]['terminated'])
            self.assertFalse(trajectory[-1]['truncated'])
            self.assertAlmostEqual(sum(item['reward'] for item in trajectory), summary['metrics']['reward'])
            for item in trajectory:
                visible = json.dumps(item['observation'])
                for forbidden in ['acceptable_evidence_sets', 'issues', 'provenance', 'seed', 'expected_amount_minor']:
                    self.assertNotIn(forbidden, visible)
            submission = output / 'findings.json'
            submission.write_text(json.dumps(trajectory[-1]['action']['params']))
            score = self.run_cli('score', str(output), '--findings', str(submission),
                                 '--inspection-steps', str(len(trajectory) - 1))
            self.assertEqual(score.returncode, 0, score.stderr + score.stdout)
            self.assertEqual(json.loads(score.stdout)['reward'], summary['metrics']['reward'])

    def test_generate_and_validate_scenario_from_cli(self):
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / 'episode')
            generated = self.run_cli('generate-scenario', '--seed', '7', '--output', path)
            self.assertEqual(generated.returncode, 0, generated.stderr)
            checked = self.run_cli('validate-scenario', path)
            self.assertEqual(json.loads(checked.stdout), {'ok': True, 'issues': 2})


if __name__ == '__main__':
    unittest.main()
