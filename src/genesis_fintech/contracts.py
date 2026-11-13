"""Draft v0.1 interfaces. Types do not provide runtime validation or isolation.

Only the supervisor-side environment receives seed and config. A held-out policy
receives an initial observation and a narrow action bridge, never an environment
instance, scorer, private truth or generator state.
"""

from typing import Any, Dict, List, Protocol, Tuple, TypedDict

JSONMapping = Dict[str, Any]
Observation = JSONMapping
Info = JSONMapping
StepResult = Tuple[Observation, float, bool, bool, Info]


class Action(TypedDict):
    action: str
    params: JSONMapping


class Finding(TypedDict):
    type: str
    affected_ids: List[str]
    claimed_amount_minor: int
    currency: str
    evidence_ids: List[str]
    explanation: str


class Submission(TypedDict):
    episode_id: str
    findings: List[Finding]


class AuditEnvironment(Protocol):
    """Supervisor-side API; not exposed as a Python object to evaluated policies."""

    def reset(self, seed: int, config: JSONMapping) -> Tuple[Observation, Info]: ...

    def step(self, action: Action) -> StepResult: ...


class Policy(Protocol):
    """A policy sees only serialized public observations, including tool results."""

    def reset(self, observation: Observation) -> None: ...

    def act(self, observation: Observation) -> Action: ...
