"""Development reset/step environment; this class is not an OS security boundary."""

import base64
import json
import time

from genesis_fintech.domain.models import DataError, integer, object_fields
from genesis_fintech.evaluation.scoring import score_submission
from genesis_fintech.evaluation.truth import validate_truth
from genesis_fintech.generation.scenario import ScenarioConfig, generate_scenario
from .calculator import calculate


class EpisodeFinished(RuntimeError):
    pass


class AuditEnv:
    def __init__(self, *, mode="train", max_steps=100, wall_time_seconds=60, clock=time.monotonic):
        if mode not in ("train", "evaluation"):
            raise DataError("unknown mode")
        integer(max_steps, "max_steps", 1, 100)
        integer(wall_time_seconds, "wall_time_seconds", 1, 60)
        self.mode, self.max_steps, self.wall_time_seconds = mode, max_steps, wall_time_seconds
        self._clock = clock
        self._active = False
        self._score = None
        self.trajectory = []

    def reset(self, seed, config=None):
        config = ScenarioConfig() if config is None else ScenarioConfig.from_dict(config)
        generated = generate_scenario(seed, config)
        validate_truth(generated.public, generated.truth)
        self._public, self._truth = generated.public, generated.truth
        self._tables = {
            "ledger": [(r.row_id, r.to_dict()) for r in self._public.ledger],
            "invoices": [(r.invoice_id, r.to_dict()) for r in self._public.invoices],
            "payments": [(r.payment_id, r.to_dict()) for r in self._public.payments],
            "fx": [(r.evidence_id, r.to_dict()) for r in self._public.fx],
        }
        self._documents = {r.doc_id: r.to_dict() for r in (*self._public.invoices, *self._public.payments)}
        self._steps, self._inspections, self._active, self._score, self.trajectory = 0, 0, True, None, []
        self._deadline = self._clock() + self.wall_time_seconds
        return {"task": "Audit synthetic records; submit supported discrepancies or no findings.",
                "manifest": self._public.manifest.to_dict(), "policy": self._public.policy.to_dict(),
                "remaining_steps": self.max_steps}, {}

    def _finish(self, raw, inspections):
        self._score = score_submission(raw, self._truth, self._public, inspections)
        self._active = False

    def evaluation_result(self):
        """Supervisor-only result, deliberately absent from the action vocabulary."""
        if self._score is None:
            raise DataError("episode_not_finished")
        return self._score.to_dict()

    def _truncate(self):
        self._finish({"episode_id": self._public.manifest.episode_id, "findings": []}, self._inspections)

    def abort_worker(self, reason):
        """Supervisor-only truncation; a policy cannot call this via the tool bridge."""
        if reason not in {"worker_timeout", "worker_protocol_error", "worker_exit"}:
            raise DataError("unknown worker failure")
        if not self._active:
            raise EpisodeFinished("episode already finished")
        self._truncate()
        return self._record(None, {"error": reason, "remaining_steps": self.max_steps - self._steps}, False, True)

    def _tool(self, name, params):
        if name == "calculator":
            object_fields(params, {"expression"})
            return {"value": calculate(params["expression"])}
        if name == "get_document":
            object_fields(params, {"doc_id"})
            if type(params["doc_id"]) is not str or params["doc_id"] not in self._documents:
                raise DataError("unknown_document")
            return self._documents[params["doc_id"]]
        if name not in ("list_records", "get_record"):
            raise DataError("unknown_action")
        object_fields(params, {"table", "cursor", "limit"} if name == "list_records" else {"table", "id"})
        table = params["table"]
        if type(table) is not str or table not in self._tables:
            raise DataError("unknown_table")
        records = self._tables[table]
        if name == "get_record":
            if type(params["id"]) is not str:
                raise DataError("unknown_record")
            for record_id, record in records:
                if record_id == params["id"]:
                    return record
            raise DataError("unknown_record")
        limit = integer(params["limit"], "limit", 1, 50)
        cursor, offset = params["cursor"], 0
        if cursor is not None:
            if type(cursor) is not str or len(cursor) > 128:
                raise DataError("invalid_cursor")
            try:
                decoded = json.loads(base64.b64decode(cursor, altchars=b'-_', validate=True))
                if type(decoded) is not list or len(decoded) != 2 or decoded[0] != table:
                    raise ValueError()
                offset = integer(decoded[1], "cursor offset", 0, len(records))
            except (ValueError, TypeError, UnicodeError) as exc:
                raise DataError("invalid_cursor") from exc
        end = min(offset + limit, len(records))
        next_cursor = (base64.urlsafe_b64encode(json.dumps([table, end]).encode()).decode()
                       if end < len(records) else None)
        return {"records": [record for _, record in records[offset:end]], "next_cursor": next_cursor}

    def step(self, action):
        if not self._active:
            raise EpisodeFinished("reset required before stepping a finished or uninitialized episode")
        was_submit = type(action) is dict and action.get("action") == "submit"
        try:
            encoded = json.dumps(action, allow_nan=False)
            if len(encoded.encode("utf-8")) > 512 * 1024:
                raise ValueError("oversized action")
            action = json.loads(encoded)
        except (TypeError, ValueError, RecursionError):
            # Preserve submit termination semantics without keeping arbitrary objects or huge payloads in logs.
            action = {"action": "submit", "params": {}} if was_submit else None
        if self._clock() >= self._deadline:
            self._truncate()
            observation = {"error": "time_limit", "remaining_steps": self.max_steps - self._steps}
            return self._record(action, observation, False, True)
        self._steps += 1
        terminated = truncated = False
        inspection_counted = False
        try:
            object_fields(action, {"action", "params"})
            name, params = action["action"], action["params"]
            if type(name) is not str:
                raise DataError("invalid_action")
            if name == "submit":
                if self._clock() >= self._deadline:
                    self._truncate()
                    truncated = True
                    observation = {"error": "time_limit"}
                else:
                    self._finish(params, self._inspections)
                    if self._clock() >= self._deadline:
                        self._truncate()
                        truncated = True
                        observation = {"error": "time_limit"}
                    else:
                        terminated = True
                        observation = {"result": {"submitted": True}}
            else:
                self._inspections += 1
                inspection_counted = True
                observation = {"result": self._tool(name, params)}
        except DataError:
            if was_submit:
                self._finish(None, self._inspections)
                terminated = True
                observation = {"result": {"submitted": True}}
            else:
                if not inspection_counted:
                    self._inspections += 1
                # Never return incoming IDs, internal paths, scorer diagnostics or stack traces.
                observation = {"error": "invalid_request"}
        if self._active and (self._steps >= self.max_steps or self._clock() >= self._deadline):
            self._truncate()
            terminated, truncated = False, True
            observation = {"error": "step_or_time_limit"}
        observation["remaining_steps"] = self.max_steps - self._steps
        return self._record(action, observation, terminated, truncated)

    def _record(self, action, observation, terminated, truncated):
        reward = self._score.reward if self._score is not None and self.mode == "train" else 0.0
        # Copy both directions: a caller cannot mutate future records or past trajectory items.
        safe_observation = json.loads(json.dumps(observation))
        self.trajectory.append({"episode_id": self._public.manifest.episode_id, "step": self._steps,
                                "action": json.loads(json.dumps(action)), "observation": safe_observation,
                                "reward": reward, "terminated": terminated, "truncated": truncated})
        return json.loads(json.dumps(safe_observation)), reward, terminated, truncated, {}
