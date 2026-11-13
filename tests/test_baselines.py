import ast
from dataclasses import replace
import json
from pathlib import Path
import random
import unittest

from genesis_fintech.domain.findings import Issue, Submission, Truth
from genesis_fintech.domain.models import PublicEpisode
from genesis_fintech.evaluation.benchmark import benchmark_cases, run_policy
from genesis_fintech.evaluation.scoring import evaluate_submission
from genesis_fintech.policies.baselines import FlagAllPolicy, RandomPolicy, ReconciliationPolicy


def offline_run(policy, raw, page_size=50):
    """Fake JSON tool bridge: policy has no env, truth, seed or filesystem handle."""
    initial = {"manifest": raw["manifest"], "policy": raw["policy"], "remaining_steps": 100}
    policy.reset(json.loads(json.dumps(initial)))
    observation = initial
    actions = []
    for _ in range(100):
        action = policy.act(json.loads(json.dumps(observation)))
        actions.append(action)
        if action["action"] == "submit":
            return action["params"], actions
        assert action["action"] == "list_records"
        params = action["params"]
        assert 1 <= params["limit"] <= 50
        offset = int(params["cursor"]) if params["cursor"] is not None else 0
        table = raw[params["table"]]
        end = min(offset + page_size, len(table))
        observation = {"result": {"records": table[offset:end],
                                  "next_cursor": str(end) if end < len(table) else None},
                       "remaining_steps": 100 - len(actions)}
    raise AssertionError("policy failed to submit")


def manual():
    return json.loads((Path(__file__).parent / "fixtures/clean_minimal.json").read_text())


class BaselineTests(unittest.TestCase):
    def test_manual_clean_partial_payments_and_opaque_pagination(self):
        raw = manual()
        submission, actions = offline_run(ReconciliationPolicy(), raw, page_size=1)
        self.assertEqual(submission["findings"], [])
        self.assertEqual(len(actions), 11)
        self.assertTrue(Submission.from_dict(submission))

    def test_manual_four_error_composition_without_generator(self):
        raw = manual()
        raw["manifest"]["currency_exponents"]["USD"] = 2
        raw["payments"][0].update(currency="USD", amount_minor=5)
        raw["fx"] = [{"date": "2026-10-03", "source_currency": "USD", "target_currency": "KZT", "rate": "500"}]
        raw["ledger"].extend([{**r, "row_id": r["row_id"] + "_copy"} for r in raw["ledger"][:2]])
        for row in raw["ledger"]:
            if row["payment_id"] is None:
                row["timestamp"] = raw["manifest"]["period_end"]
        raw["ledger"][2]["debit_minor"] = 2495
        raw["ledger"][3]["credit_minor"] = 1495
        raw["ledger"].append({**raw["ledger"][3], "row_id": "row_wrong_revenue", "account": "revenue", "credit_minor": 1000})
        raw["manifest"]["row_count"] = len(raw["ledger"])
        public = PublicEpisode.from_dict(raw)
        sale_witness = tuple(sorted(["doc_invoice", "row_sale_ar", "row_sale_revenue", "row_sale_ar_copy", "row_sale_revenue_copy"]))
        pay_witness = tuple(sorted(["doc_invoice", "doc_payment_a", "row_bank_a", "row_payment_ar_a",
                                    "row_wrong_revenue", "fx_2026-10-03_USD_KZT"]))
        truth = Truth("episode_manual", (
            Issue("issue_dup", "duplicate_invoice", ("invoice_manual",), 10000, "KZT", (sale_witness,)),
            Issue("issue_period", "period_cutoff", ("invoice_manual",), 10000, "KZT", (sale_witness,)),
            Issue("issue_fx", "fx_mismatch", ("invoice_manual", "payment_a"), 5, "KZT", (pay_witness,)),
            Issue("issue_alloc", "payment_allocation", ("invoice_manual", "payment_a"), 1000, "KZT", (pay_witness,)),
        ))
        submission, _ = offline_run(ReconciliationPolicy(), raw, page_size=2)
        score = evaluate_submission(submission, truth, public)
        self.assertEqual((score.tp, score.fp, score.fn), (4, 0, 0))
        # IDs are opaque. Permuting and renaming public IDs cannot change amounts.
        identifiers = sorted({v for table in ("invoices", "payments", "ledger") for row in raw[table]
                              for k, v in row.items() if k.endswith("_id") and v is not None})
        mapping = {identifier: f"opaque_{n}" for n, identifier in enumerate(identifiers)}

        def rename(value):
            if isinstance(value, str):
                return mapping.get(value, value)
            if isinstance(value, dict):
                return {k: rename(v) for k, v in value.items()}
            if isinstance(value, list):
                return [rename(v) for v in value]
            return value

        changed = rename(raw)
        for table in ("invoices", "payments", "ledger", "fx"):
            changed[table].reverse()
        submission, _ = offline_run(ReconciliationPolicy(), changed, page_size=1)
        changed_truth = Truth.from_dict(rename(truth.to_dict()))
        self.assertEqual(evaluate_submission(submission, changed_truth, PublicEpisode.from_dict(changed)).f1, 1)

    def test_all_profiles_and_10_seeds_have_correct_reconciliation(self):
        for case, config in benchmark_cases().items():
            for seed in range(10):
                with self.subTest(case=case, seed=seed):
                    result, _, trace = run_policy("reconciliation", seed, config)
                    self.assertEqual(result["metrics"]["f1"], 1)
                    self.assertIsNone(result["failure"])
                    self.assertTrue(all(item["reward"] == 0 for item in trace))
                    self.assertFalse(any("error" in item["observation"] for item in trace))

    def test_maximum_12_findings_and_nondefault_currency_exponents(self):
        full = benchmark_cases()["independent-date"]
        for base, foreign, rate in [("JPY", "USD", "150.25"), ("KWD", "EUR", "0.30")]:
            clean = replace(full.clean, base_currency=base, foreign_currency=foreign, foreign_rate=rate)
            config = replace(full, clean=clean, duplicate_invoices=3, allocation_errors=3, fx_errors=3, cutoff_errors=3)
            result, _, _ = run_policy("reconciliation", 7, config)
            self.assertEqual((result["metrics"]["tp"], result["metrics"]["fp"], result["metrics"]["fn"]), (12, 0, 0))

    def test_flag_all_is_valid_and_penalized_on_clean_company(self):
        config = benchmark_cases()["clean"]
        result, _, trace = run_policy("flag-all", 42, config)
        self.assertTrue(result["metrics"]["valid_submission"])
        self.assertEqual((result["metrics"]["tp"], result["metrics"]["fp"], result["metrics"]["reward"]), (0, 30, -1))
        self.assertEqual(len(Submission.from_dict(trace[-1]["action"]["params"]).findings), 30)

    def test_random_seed_is_separate_repeatable_and_does_not_touch_global_rng(self):
        before = random.getstate()
        raw = manual()
        one = offline_run(RandomPolicy(1), raw)
        self.assertEqual(one, offline_run(RandomPolicy(1), raw))
        self.assertNotEqual(one, offline_run(RandomPolicy(2), raw))
        self.assertEqual(before, random.getstate())
        self.assertTrue(Submission.from_dict(one[0]))

    def test_incomplete_budget_abstains_and_reserves_submit_step(self):
        for policy in ("random", "flag-all", "reconciliation"):
            result, _, trace = run_policy(policy, 42, benchmark_cases()["independent-rate"], max_steps=2)
            self.assertTrue(result["terminated"])
            self.assertFalse(result["truncated"])
            self.assertEqual(trace[-1]["action"]["params"]["findings"], [])
            self.assertEqual(len(trace), 2)

    def test_tool_error_causes_valid_abstention(self):
        raw = manual()
        for policy in (RandomPolicy(), FlagAllPolicy(), ReconciliationPolicy()):
            policy.reset({"manifest": raw["manifest"], "policy": raw["policy"]})
            policy.act({"remaining_steps": 100})
            action = policy.act({"error": "invalid_request", "remaining_steps": 99})
            self.assertEqual(Submission.from_dict(action["params"]).findings, ())

    def test_policy_source_has_no_privileged_imports_or_file_calls(self):
        tree = ast.parse(Path("src/genesis_fintech/policies/baselines.py").read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                self.assertNotRegex(node.module, r"evaluation|environment|generation")
            if isinstance(node, ast.Import):
                for name in node.names:
                    self.assertNotRegex(name.name, r"evaluation|environment|generation|pathlib|os|sys|importlib")
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                self.assertNotIn(node.func.id, ("open", "eval", "exec", "__import__"))
        # Source checks are maintenance guards; they do not establish OS isolation.


if __name__ == "__main__":
    unittest.main()
