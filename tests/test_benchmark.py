import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from genesis_fintech.domain.models import DataError
from genesis_fintech.evaluation.benchmark import POLICIES, run_benchmark
from genesis_fintech.generation.storage import json_text, load_scenario


def without_timing(value):
    if isinstance(value, dict):
        return {k: without_timing(v) for k, v in value.items() if k not in ("elapsed_seconds", "mean_elapsed_seconds")}
    if isinstance(value, list):
        return [without_timing(v) for v in value]
    return value


class BenchmarkTests(unittest.TestCase):
    def test_reproducible_report_and_observation_only_trajectories(self):
        with tempfile.TemporaryDirectory() as directory:
            one, two = Path(directory) / "one", Path(directory) / "two"
            result = run_benchmark([42], one, policy_seed=19)
            run_benchmark([42], two, policy_seed=19)
            report = json.loads((one / "report.json").read_text())
            self.assertEqual(without_timing(report), without_timing(json.loads((two / "report.json").read_text())))
            self.assertEqual((result["episodes"], result["policy_runs"]), (5, 20))
            self.assertTrue((one / "report.md").is_file())
            for episode in (one / "episodes").iterdir():
                public, truth = load_scenario(episode)
                fingerprint = hashlib.sha256(json_text(public.to_dict()).encode()).hexdigest()
                rows = [r for r in report["runs"] if f"{r['case']}-{r['seed']}" == episode.name]
                self.assertEqual(len(rows), 4)
                self.assertEqual({r["public_sha256"] for r in rows}, {fingerprint})
                for policy in POLICIES:
                    trace = (episode / f"{policy}.jsonl").read_text()
                    self.assertEqual(trace, (two / "episodes" / episode.name / f"{policy}.jsonl").read_text())
                    for step in map(json.loads, trace.splitlines()):
                        self.assertEqual(step["reward"], 0)
                        visible = json.dumps(step["observation"])
                        for forbidden in ("expected_amount_minor", "acceptable_evidence_sets", "provenance", '"seed"'):
                            self.assertNotIn(forbidden, visible)
            for row in report["runs"]:
                for key in ("tp", "fp", "fn"):
                    self.assertEqual(sum(c[key] for c in row["by_family"].values()), row["metrics"][key])
            self.assertEqual(report["summary"]["reconciliation"]["micro_f1"], 1)
            self.assertEqual(report["summary"]["evaluator_oracle"]["micro_f1"], 1)
            self.assertEqual(report["summary"]["flag-all"]["mean_reward"], -1)

    def test_no_overwrite_and_invalid_seeds_leave_no_artifacts(self):
        with tempfile.TemporaryDirectory() as directory:
            for seeds in ([], [1, 1], [True], [-1], list(range(21))):
                output = Path(directory) / "invalid"
                with self.subTest(seeds=seeds), self.assertRaises(DataError):
                    run_benchmark(seeds, output)
                self.assertFalse(output.exists())
            with self.assertRaises(FileExistsError):
                run_benchmark([42], Path(directory))

    def test_benchmark_cli(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "cli"
            args = [sys.executable, "-m", "genesis_fintech", "benchmark", "--seeds", "7", "--output", str(output)]
            run = subprocess.run(args, env=dict(os.environ, PYTHONPATH="src"), capture_output=True, text=True, timeout=15)
            self.assertEqual(run.returncode, 0, run.stderr + run.stdout)
            self.assertEqual(json.loads(run.stdout)["policy_runs"], 20)
            again = subprocess.run(args, env=dict(os.environ, PYTHONPATH="src"), capture_output=True, text=True, timeout=15)
            self.assertEqual(again.returncode, 2)
            self.assertFalse(json.loads(again.stdout)["ok"])


if __name__ == "__main__":
    unittest.main()
