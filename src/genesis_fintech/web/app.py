"""UI view model built from real baseline results and observed evidence only."""

from dataclasses import replace

from genesis_fintech import __version__
from genesis_fintech.domain.models import integer, object_fields
from genesis_fintech.evaluation.benchmark import run_policy
from genesis_fintech.generation.clean import CleanConfig
from genesis_fintech.generation.scenario import ScenarioConfig

SCENARIOS = {
    "interactions": "Взаимодействующие ошибки",
    "independent": "Четыре независимые ошибки",
    "clean": "Чистая компания",
}
POLICIES = {"reconciliation": "Сверка документов", "random": "Случайные гипотезы", "flag-all": "Отметить всё"}


def scenario_config(name):
    config = ScenarioConfig(clean=CleanConfig(invoice_count=60, foreign_payment_invoices=12,
                                             boundary_invoices=4, refund_invoices=4), fx_errors=1, cutoff_errors=1)
    if name == "interactions":
        return replace(config, interaction_scenarios=("fx_allocation", "duplicate_cutoff"))
    if name == "clean":
        return replace(config, duplicate_invoices=0, allocation_errors=0, fx_errors=0, cutoff_errors=0)
    return config


def run_view(request):
    object_fields(request, {"seed", "scenario", "policy"})
    seed = integer(request["seed"], "seed", 0, 2147483647)
    if type(request["scenario"]) is not str or request["scenario"] not in SCENARIOS:
        raise ValueError("unknown scenario")
    if type(request["policy"]) is not str or request["policy"] not in POLICIES:
        raise ValueError("unknown policy")
    result, initial, trace = run_policy(request["policy"], seed, scenario_config(request["scenario"]))
    seen = {}
    timeline = []
    for item in trace:
        action = item["action"] or {}
        response = item["observation"].get("result", {})
        records = response.get("records", []) if type(response) is dict else []
        if type(response) is dict and any(key in response for key in ("row_id", "doc_id", "date")):
            records = [response]
        for record in records:
            for field in ("row_id", "doc_id", "invoice_id", "payment_id"):
                if record.get(field):
                    # A document's IDs should resolve to that document, not to a
                    # ledger row which merely references it.
                    if field in ("invoice_id", "payment_id") and "row_id" in record:
                        continue
                    seen[record[field]] = record
            if "rate" in record:
                seen[f"fx_{record['date']}_{record['source_currency']}_{record['target_currency']}"] = record
        timeline.append({"step": item["step"], "action": action.get("action"),
                         "table": action.get("params", {}).get("table"), "records": len(records),
                         "error": item["observation"].get("error")})
    last = trace[-1]
    params = (last["action"] or {}).get("params", {}) if result["terminated"] else {}
    findings = []
    for finding in params.get("findings", []):
        findings.append({**finding, "evidence": [{"id": key, "record": seen.get(key)} for key in finding["evidence_ids"]]})
    return {"version": __version__, "seed": seed, "scenario": request["scenario"], "policy": request["policy"],
            "security_mode": result.get("security_mode", "development_in_process"),
            "metrics": result["metrics"], "steps": result["steps"], "failure": result["failure"],
            "terminated": result["terminated"], "truncated": result["truncated"],
            "manifest": initial["manifest"], "findings": findings, "timeline": timeline}
