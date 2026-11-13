"""Supervisor-side baseline benchmark and failure analysis (development only)."""

from dataclasses import replace
import hashlib
import json
from pathlib import Path
import time

from genesis_fintech import __version__
from genesis_fintech.domain.findings import ISSUE_TYPES, Truth
from genesis_fintech.domain.models import DataError, integer
from genesis_fintech.environment.core import AuditEnv
from genesis_fintech.generation.clean import CleanConfig
from genesis_fintech.generation.scenario import ScenarioConfig, generate_scenario
from genesis_fintech.generation.storage import json_text, write_scenario
from genesis_fintech.policies.baselines import make_policy
from .demo import oracle_actions
from .scoring import score_submission

POLICIES = ("random", "flag-all", "reconciliation", "evaluator_oracle")


def benchmark_cases():
    """Five development profiles; no claim of held-out generalization."""
    clean = CleanConfig(invoice_count=60, foreign_payment_invoices=12,
                        boundary_invoices=4, refund_invoices=4)
    full = ScenarioConfig(clean=clean, fx_errors=1, cutoff_errors=1)
    return {
        "clean": replace(full, duplicate_invoices=0, allocation_errors=0, fx_errors=0, cutoff_errors=0),
        "two-families": ScenarioConfig(),
        "independent-rate": full,
        "independent-date": replace(full, fx_error_mode="date", allocation_mode="missing"),
        "compositions": replace(full, interaction_scenarios=("fx_allocation", "duplicate_cutoff")),
    }


def run_policy(name, seed, config, *, policy_seed=0, max_steps=100, generated=None):
    """Only this supervisor receives seed/config/truth. A policy sees JSON copies."""
    if name not in POLICIES:
        raise DataError("unknown benchmark policy")
    generated = generated if generated is not None else generate_scenario(seed, config)
    env = AuditEnv(mode="evaluation", max_steps=max_steps)
    observation, _ = env.reset(seed, config.to_dict())
    initial = json.loads(json.dumps(observation))
    oracle = iter(oracle_actions(generated)) if name == "evaluator_oracle" else None
    policy = make_policy(name, policy_seed) if oracle is None else None
    if policy is not None:
        policy.reset(json.loads(json.dumps(initial)))
    started = time.perf_counter()
    while True:
        action = next(oracle) if oracle is not None else policy.act(json.loads(json.dumps(observation)))
        observation, _, terminated, truncated, _ = env.step(action)
        if oracle is not None and observation.get("error") == "invalid_request":
            raise DataError("oracle could not retrieve its declared observable evidence")
        if terminated or truncated:
            break
    elapsed = time.perf_counter() - started
    # A truncated episode is scored by the environment as an empty submission.
    last = env.trajectory[-1]
    raw = (last["action"]["params"] if terminated and last["action"]["action"] == "submit"
           else {"episode_id": generated.public.manifest.episode_id, "findings": []})
    metrics = env.evaluation_result()
    families = {}
    for family in sorted(ISSUE_TYPES):
        truth = Truth(generated.truth.episode_id, tuple(i for i in generated.truth.issues if i.type == family))
        submission = {"episode_id": raw["episode_id"],
                      "findings": [f for f in raw["findings"] if f["type"] == family]}
        score = score_submission(submission, truth, generated.public)
        families[family] = {key: getattr(score, key) for key in ("tp", "fp", "fn")}
    failure = None
    if truncated:
        failure = "budget_exhausted"
    elif not metrics["valid_submission"]:
        failure = "invalid_submission"
    elif metrics["fp"] and metrics["fn"]:
        failure = "false_alarms_and_misses"
    elif metrics["fp"]:
        failure = "false_alarms"
    elif metrics["fn"]:
        failure = "misses"
    return {"policy": name, "metrics": metrics, "by_family": families, "failure": failure,
            "steps": len(env.trajectory), "terminated": terminated, "truncated": truncated,
            "elapsed_seconds": elapsed}, initial, env.trajectory


def _aggregate(runs):
    result = {}
    for policy in POLICIES:
        selected = [r for r in runs if r["policy"] == policy]
        counts = {key: sum(r["metrics"][key] for r in selected) for key in ("tp", "fp", "fn")}
        tp, fp, fn = (counts[k] for k in ("tp", "fp", "fn"))
        clean = [r for r in selected if r["case"] == "clean"]
        result[policy] = {**counts, "episodes": len(selected),
                          "micro_precision": tp / (tp + fp) if tp + fp else 0,
                          "micro_recall": tp / (tp + fn) if tp + fn else 0,
                          "micro_f1": 2 * tp / (2 * tp + fp + fn) if tp + fp + fn else 1,
                          "mean_episode_f1": sum(r["metrics"]["f1"] for r in selected) / len(selected),
                          "mean_reward": sum(r["metrics"]["reward"] for r in selected) / len(selected),
                          "mean_steps": sum(r["steps"] for r in selected) / len(selected),
                          "mean_elapsed_seconds": sum(r["elapsed_seconds"] for r in selected) / len(selected),
                          "clean_correct": sum(r["metrics"]["fp"] == 0 and r["metrics"]["valid_submission"]
                                               and not r["truncated"] for r in clean),
                          "clean_episodes": len(clean),
                          "failures": sum(r["failure"] is not None for r in selected),
                          "by_family": {f: {k: sum(r["by_family"][f][k] for r in selected)
                                            for k in ("tp", "fp", "fn")} for f in sorted(ISSUE_TYPES)}}
    return result


def run_benchmark(seeds, output: Path, *, policy_seed=0):
    seeds = list(seeds)
    if not 1 <= len(seeds) <= 20 or len(set(seeds)) != len(seeds):
        raise DataError("benchmark requires 1..20 distinct episode seeds")
    for seed in seeds:
        integer(seed, "seed", 0, 2**63 - 1)
    integer(policy_seed, "policy_seed", 0, 2**63 - 1)
    # All host reports, truth and trajectories are evaluator artifacts. They must
    # never be mounted into a future isolated policy worker.
    output.mkdir(parents=True, exist_ok=False)
    runs = []
    cases = benchmark_cases()
    for case, config in cases.items():
        for seed in seeds:
            generated = generate_scenario(seed, config)
            episode = output / "episodes" / f"{case}-{seed}"
            write_scenario(generated, episode)
            fingerprint = hashlib.sha256(json_text(generated.public.to_dict()).encode()).hexdigest()
            reference_initial = None
            for name in POLICIES:
                result, initial, trace = run_policy(name, seed, config, policy_seed=policy_seed, generated=generated)
                if reference_initial is not None and initial != reference_initial:
                    raise DataError("policies did not receive the same initial observation")
                reference_initial = initial
                result.update(case=case, seed=seed, public_sha256=fingerprint)
                runs.append(result)
                with (episode / f"{name}.jsonl").open("x", encoding="utf-8") as file:
                    for item in trace:
                        file.write(json.dumps(item, sort_keys=True, ensure_ascii=False) + "\n")
    report = {"version": __version__, "security_mode": "development_in_process",
              "suite": "baseline-development-v1", "episode_seeds": seeds, "policy_seed": policy_seed,
              "reproducibility": "All fields except elapsed_seconds and mean_elapsed_seconds are deterministic.",
              "oracle_is_privileged": True, "cases": {k: v.to_dict() for k, v in cases.items()},
              "summary": _aggregate(runs), "runs": runs}
    (output / "report.json").write_text(json_text(report), encoding="utf-8")
    _write_markdown(report, output / "report.md")
    return {"ok": True, "report": str(output / "report.json"), "episodes": len(seeds) * len(cases),
            "policy_runs": len(runs), "summary": report["summary"]}


def _write_markdown(report, path):
    lines = ["# Development baseline benchmark", "",
             f"Version {report['version']}; suite {report['suite']}; episode seeds {report['episode_seeds']}; policy seed {report['policy_seed']}.",
             "", "Same scenarios for each policy. Oracle has privileged truth access. In-process development only; no held-out claim.",
             "", "| Policy | TP | FP | FN | Micro F1 | Mean F1 | Mean reward | Mean steps | Clean correct |",
             "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for policy, row in report["summary"].items():
        lines.append(f"| {policy} | {row['tp']} | {row['fp']} | {row['fn']} | {row['micro_f1']:.4f} | "
                     f"{row['mean_episode_f1']:.4f} | {row['mean_reward']:.4f} | {row['mean_steps']:.2f} | "
                     f"{row['clean_correct']}/{row['clean_episodes']} |")
    lines.extend(["", "## Failure analysis", "",
                  "A failure means FP, FN, invalid submission or truncation. Per-family counts use the same matcher, filtered by family.",
                  "Random draws 0..12 invoice-level hypotheses; flag-all alleges duplicates on at most 30 invoices. Neither is an auditor.",
                  "Reconciliation is a fixed aggregate rule set for this synthetic data model; it has no LLM or training. Foreign invoices, multi-invoice receipts and unknown error types are outside its scope.",
                  "", "| Policy | Family | TP | FP | FN |", "| --- | --- | --- | --- | --- |"])
    for policy, row in report["summary"].items():
        for family, counts in row["by_family"].items():
            lines.append(f"| {policy} | {family} | {counts['tp']} | {counts['fp']} | {counts['fn']} |")
    lines.extend(["", "## Failed runs", "", "| Case | Seed | Policy | Reason | FP | FN |",
                  "| --- | --- | --- | --- | --- | --- |"])
    for run in report["runs"]:
        if run["failure"]:
            lines.append(f"| {run['case']} | {run['seed']} | {run['policy']} | {run['failure']} | "
                         f"{run['metrics']['fp']} | {run['metrics']['fn']} |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
