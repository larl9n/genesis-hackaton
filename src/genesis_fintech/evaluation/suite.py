"""One-command evaluator for a frozen corpus, external baselines and host-only oracle."""

from collections import Counter
import json
from pathlib import Path
import resource
import sys
import time
from types import SimpleNamespace

from genesis_fintech import __version__
from genesis_fintech.domain.findings import Truth, oracle_submission
from genesis_fintech.domain.models import DataError, PublicEpisode, integer
from genesis_fintech.environment.core import AuditEnv
from genesis_fintech.generation.datasets import validate_dataset, sha256
from genesis_fintech.generation.storage import json_text, load_scenario, read_json
from .demo import oracle_actions
from .external import DEFAULT_IMAGE, docker_image_id, run_external_episode
from .scoring import score_submission, evaluate_submission

SUITE_VERSION = "conformance-v1"
POLICIES = ("random", "flag-all", "reconciliation", "evaluator_oracle")


def _oracle(public, truth, output):
    env = AuditEnv(mode="evaluation")
    env.reset_episode(public, truth)
    started = time.monotonic()
    for action in oracle_actions(SimpleNamespace(public=public, truth=truth)):
        observation, _, terminated, truncated, _ = env.step(action)
        if observation.get("error"):
            raise DataError("oracle evidence retrieval failed")
        if terminated or truncated:
            break
    output.mkdir(parents=True, exist_ok=False)
    result = {"policy": "evaluator_oracle", "security_mode": "evaluator_only", "failure": None,
              "metrics": env.evaluation_result(), "steps": len(env.trajectory),
              "terminated": terminated, "truncated": truncated, "elapsed_seconds": time.monotonic()-started}
    (output/"summary.json").write_text(json_text(result))
    (output/"trajectories.jsonl").write_text("".join(json_text_line(item) for item in env.trajectory))
    return result


def json_text_line(item):
    return json.dumps(item, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n"


def _read_trace(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def _check_run(result, trace, public, truth):
    if (result["truncated"] or not result["terminated"] or result["failure"]
            or not result["metrics"]["valid_submission"] or not 1 <= result["steps"] <= 100):
        raise DataError("suite: policy violated execution contract")
    if result.get("backend") == "docker":
        counters = result.get("worker_resources") or {}
        if (not counters.get("measured") or counters["oom_kills"]
                or not 0 < counters["peak_memory_bytes"] <= counters["memory_limit_bytes"] == 512*1024*1024
                or result["elapsed_seconds"] > 60):
            raise DataError("suite: missing counters or worker resource budget exceeded")
    for item in trace:
        if item["reward"] != 0 or item["observation"].get("error"):
            raise DataError("suite: reward exposure or invalid tool request")
        def check(value):
            if type(value) is dict:
                if set(value) & {"truth", "provenance", "seed", "acceptable_evidence_sets", "expected_amount_minor", "latent_history"}:
                    raise DataError("suite: private field in observation")
                for child in value.values(): check(child)
            elif type(value) is list:
                for child in value: check(child)
        check(item["observation"])
    last = trace[-1]
    if last["action"].get("action") != "submit":
        raise DataError("suite: no final submission")
    raw = last["action"]["params"]
    inspections = sum(item["action"] is not None and item["action"].get("action") != "submit" for item in trace)
    rescored = evaluate_submission(raw, truth, public, inspections).to_dict()
    if rescored != result["metrics"]:
        raise DataError("suite: persisted submission/score mismatch")
    return raw


def _paired_check(public, truth):
    ids = {public.manifest.episode_id}
    for row in public.ledger: ids.update([row.row_id, row.entity_id])
    for invoice in public.invoices: ids.update([invoice.invoice_id, invoice.doc_id, invoice.entity_id])
    for payment in public.payments: ids.update([payment.payment_id, payment.doc_id])
    ids.update(issue.issue_id for issue in truth.issues)
    mapping = {old: old.split("_", 1)[0]+"_pair_"+str(index) for index, old in enumerate(sorted(ids))}
    def rename(value):
        if type(value) is dict: return {key: rename(item) for key, item in value.items()}
        if type(value) is list: return [rename(item) for item in value]
        return mapping.get(value, value) if type(value) is str else value
    data = rename(public.to_dict())
    for table in ("ledger", "invoices", "payments", "fx"): data[table].reverse()
    paired_public, paired_truth = PublicEpisode.from_dict(data), Truth.from_dict(rename(truth.to_dict()))
    original = evaluate_submission(oracle_submission(truth), truth, public, 7).to_dict()
    changed = evaluate_submission(oracle_submission(paired_truth), paired_truth, paired_public, 7).to_dict()
    if original != changed:
        raise DataError("suite: ID/order transformation changed supported oracle score")
    return True


def _aggregate(runs):
    summary = {}
    for policy in POLICIES:
        selected = [run for run in runs if run["policy"] == policy]
        counts = {key: sum(run["metrics"][key] for run in selected) for key in ("tp", "fp", "fn")}
        tp, fp, fn = (counts[key] for key in ("tp", "fp", "fn"))
        clean = [run for run in selected if run["truth_count"] == 0]
        summary[policy] = {**counts, "episodes": len(selected),
                           "micro_precision": tp/(tp+fp) if tp+fp else 0,
                           "micro_recall": tp/(tp+fn) if tp+fn else 0,
                           "micro_f1": 2*tp/(2*tp+fp+fn) if tp+fp+fn else 1,
                           "mean_reward": sum(run["metrics"]["reward"] for run in selected)/len(selected),
                           "mean_steps": sum(run["steps"] for run in selected)/len(selected),
                           "max_elapsed_seconds": max(run["elapsed_seconds"] for run in selected),
                           "clean_correct": sum(run["metrics"]["fp"] == 0 for run in clean),
                           "clean_episodes": len(clean)}
    return summary


def evaluate_dataset(directory, output, *, backend="docker", image=DEFAULT_IMAGE, policy_seed=17, replay=False):
    integer(policy_seed, "policy_seed", 0, 2**63-1)
    if backend not in {"docker", "development"}:
        raise DataError("suite: unknown backend")
    root = Path(directory)
    corpus = validate_dataset(root, replay=replay)
    # Freeze the image to its immutable ID for the whole comparison, no pulls.
    image_id = docker_image_id(image) if backend == "docker" else None
    index = read_json(root/"dataset.json")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    runs, paired = [], []
    started = time.monotonic()
    for item in index["episodes"]:
        episode = root/"episodes"/item["split"]/item["episode_id"]
        public, truth = load_scenario(episode)
        fingerprint = sha256(json_text(public.to_dict()).encode())
        for policy in POLICIES:
            run_path = output/"runs"/item["split"]/item["episode_id"]/policy
            def execute(path):
                return (_oracle(public, truth, path) if policy == "evaluator_oracle"
                        else run_external_episode(public, truth, path, policy=policy, policy_seed=policy_seed,
                                                  backend=backend, image=image_id or image))
            result = execute(run_path)
            trace = _read_trace(run_path/"trajectories.jsonl")
            raw = _check_run(result, trace, public, truth)
            if policy == "evaluator_oracle" and (result["metrics"]["tp"] != len(truth.issues) or result["metrics"]["fp"] or result["metrics"]["fn"]):
                raise DataError("suite: oracle did not reach supported F1 ceiling")
            if replay:
                repeated = execute(run_path.parent/(policy+"-replay"))
                again = _read_trace(run_path.parent/(policy+"-replay")/"trajectories.jsonl")
                _check_run(repeated, again, public, truth)
                if repeated["metrics"] != result["metrics"] or again != trace:
                    raise DataError("suite: policy replay mismatch")
            result.update(split=item["split"], episode_id=item["episode_id"], public_sha256=fingerprint,
                          truth_count=len(truth.issues), findings_count=len(raw["findings"]))
            result["diagnostic"] = ("false_alarms_and_misses" if result["metrics"]["fp"] and result["metrics"]["fn"]
                                    else "false_alarms" if result["metrics"]["fp"] else "misses" if result["metrics"]["fn"] else None)
            runs.append(result)
        paired.append({"episode_id": item["episode_id"], "passed": _paired_check(public, truth)})
    summary = _aggregate(runs)
    if summary["flag-all"]["micro_f1"] >= summary["evaluator_oracle"]["micro_f1"]:
        raise DataError("suite: flag-all matches or exceeds the supported oracle")
    # Confirm source corpus was not modified by any run.
    validate_dataset(root)
    rss_unit = 1 if sys.platform == "darwin" else 1024
    report = {"version": __version__, "suite_version": SUITE_VERSION, "dataset": corpus,
              "security_mode": "docker_container" if backend == "docker" else "development_subprocess",
              "oracle_is_evaluator_only": True, "worker_image_id": image_id, "policy_seed": policy_seed,
              "replay_performed": replay, "summary": summary, "runs": runs,
              "resources": {"elapsed_seconds": time.monotonic()-started,
                            "supervisor_peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*rss_unit,
                            "child_cli_peak_rss_bytes": resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss*rss_unit,
                            "worker_memory_limit_bytes": 512*1024*1024 if backend == "docker" else None,
                            "max_worker_peak_memory_bytes": max((run["worker_resources"]["peak_memory_bytes"]
                                for run in runs if (run.get("worker_resources") or {}).get("measured")), default=None),
                            "worker_counter_checks": sum(bool((run.get("worker_resources") or {}).get("measured")) for run in runs),
                            "measurement_scope": "Supervisor/CLI RSS peaks and worker cgroup peaks are separate. Counter reader included; Docker daemon/kernel excluded. Not a total-system hardware certification."}}
    checks = {"dataset_integrity": True, "persisted_score_checks": len(runs), "execution_contract_checks": len(runs),
              "observation_privacy_checks": len(runs), "paired_id_order_checks": paired,
              "replay_checks": len(runs) if replay else 0, "oracle_ceiling": True, "flag_all_penalized": True,
              "source_corpus_unchanged": True}
    (output/"report.json").write_text(json_text(report))
    (output/"conformance.json").write_text(json_text(checks))
    lines = ["# Frozen corpus evaluation", "", f"Mode: {report['security_mode']}; evaluator-only oracle is privileged.",
             "", "| Policy | TP | FP | FN | Micro F1 | Mean reward | Clean correct |", "| --- | --- | --- | --- | --- | --- | --- |"]
    for name, row in summary.items():
        lines.append(f"| {name} | {row['tp']} | {row['fp']} | {row['fn']} | {row['micro_f1']:.4f} | {row['mean_reward']:.4f} | {row['clean_correct']}/{row['clean_episodes']} |")
    lines.extend(["", "Same stored public records for every policy; seed/config are not passed to workers.",
                  f"20 paired checks; {checks['replay_checks']} replays; {len(runs)} independently re-scored submissions.",
                  "", report['resources']['measurement_scope']])
    (output/"report.md").write_text("\n".join(lines)+"\n")
    return {"ok": True, "report": str(output/"report.json"), "episodes": 20, "policy_runs": len(runs),
            "security_mode": report["security_mode"], "replay_checks": checks["replay_checks"],
            "paired_checks": len(paired), "summary": summary}
