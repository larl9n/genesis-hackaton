"""Bounded local manual sessions and comparison of public demo policies."""

import secrets
import threading
import time

from genesis_fintech.domain.models import DataError, integer, object_fields
from genesis_fintech.environment.core import AuditEnv
from .app import POLICIES, SCENARIOS, run_view, scenario_config


def parameters(request):
    object_fields(request, {"seed", "scenario"})
    integer(request["seed"], "seed", 0, 2147483647)
    if type(request["scenario"]) is not str or request["scenario"] not in SCENARIOS:
        raise DataError("unknown scenario")
    return request


def compare_view(request):
    parameters(request)
    runs = [run_view({**request, "policy": policy}) for policy in POLICIES]
    identities = {run["manifest"]["episode_id"] for run in runs}
    if len(identities) != 1:
        raise DataError("comparison episode mismatch")
    return {"episode_id": runs[0]["manifest"]["episode_id"], **request,
            "mode": "local_demo", "oracle_included": False,
            "runs": [{key: run[key] for key in ("policy", "metrics", "steps", "terminated", "truncated")} for run in runs]}


class ManualSessions:
    def __init__(self, *, maximum=8, clock=time.monotonic):
        self.maximum, self.clock = maximum, clock
        self.sessions = {}
        self.lock = threading.Lock()

    def start(self, request):
        parameters(request)
        with self.lock:
            self.sessions = {key: value for key, value in self.sessions.items() if value[1] > self.clock()}
            if len(self.sessions) >= self.maximum:
                raise DataError("manual session capacity reached")
            env = AuditEnv(mode="evaluation", clock=self.clock)
            observation, _ = env.reset(request["seed"], scenario_config(request["scenario"]).to_dict())
            token = secrets.token_urlsafe(24)
            self.sessions[token] = (env, self.clock()+75, threading.Lock())
        return {"session": token, "observation": observation, "remaining_seconds": 60,
                "mode": "local_manual", "max_steps": 100}

    def step(self, request):
        object_fields(request, {"session", "action"})
        token = request["session"]
        if type(token) is not str or not 20 <= len(token) <= 64:
            raise DataError("invalid manual session")
        with self.lock:
            session = self.sessions.get(token)
            if session is None or session[1] <= self.clock():
                self.sessions.pop(token, None)
                raise DataError("manual session expired; start a new episode")
            # Serialize same-session actions while holding the lookup lease.
            if not session[2].acquire(blocking=False):
                raise DataError("manual session is busy")
        env = session[0]
        try:
            observation, reward, terminated, truncated, _ = env.step(request["action"])
            result = {"observation": observation, "reward": reward, "terminated": terminated,
                      "truncated": truncated, "steps": len(env.trajectory),
                      "remaining_seconds": max(0, int(env._deadline-self.clock()))}
            if terminated or truncated:
                result["metrics"] = env.evaluation_result()
                with self.lock: self.sessions.pop(token, None)
            return result
        finally:
            session[2].release()


MANUAL = ManualSessions()
