"""Evaluator-only oracle demonstration, not a benchmark of an agent's ability."""

import json
from pathlib import Path

from genesis_fintech.domain.findings import oracle_submission
from genesis_fintech.environment.core import AuditEnv
from genesis_fintech.generation.scenario import ScenarioConfig, generate_scenario
from genesis_fintech.generation.storage import json_text, write_scenario


def run_demo(seed: int, config: ScenarioConfig, output: Path) -> dict:
    generated = generate_scenario(seed, config)
    write_scenario(generated, output)
    env = AuditEnv(mode="train")
    env.reset(seed, config.to_dict())
    documents = {record.doc_id for record in (*generated.public.invoices, *generated.public.payments)}
    requested = sorted({identifier for issue in generated.truth.issues
                        for identifier in issue.acceptable_evidence_sets[0]})
    for identifier in requested:
        action = ({"action": "get_document", "params": {"doc_id": identifier}} if identifier in documents
                  else {"action": "get_record", "params": {"table": "ledger", "id": identifier}})
        _, _, terminated, truncated, _ = env.step(action)
        if terminated or truncated:
            break
    else:
        env.step({"action": "submit", "params": oracle_submission(generated.truth)})
    summary = {"policy": "evaluator_oracle", "security_mode": "development_in_process",
               "scope": "duplicate invoices and payment allocation", "steps": len(env.trajectory),
               "metrics": env.evaluation_result()}
    with (output / "trajectories.jsonl").open("x", encoding="utf-8") as file:
        for item in env.trajectory:
            file.write(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n")
    with (output / "summary.json").open("x", encoding="utf-8") as file:
        file.write(json_text(summary))
    return summary
