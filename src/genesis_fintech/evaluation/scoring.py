"""Common F1 reward and deterministic maximum one-to-one evidence matching."""

from dataclasses import dataclass

from genesis_fintech.domain.findings import Submission, Truth, evidence_ids
from genesis_fintech.domain.models import DataError, PublicEpisode, integer
from .truth import validate_truth


@dataclass(frozen=True)
class Score:
    tp: int
    fp: int
    fn: int
    precision: float
    recall: float
    f1: float
    reward: float
    inspection_steps: int
    valid_submission: bool
    error: str | None = None

    def to_dict(self) -> dict:
        return dict(vars(self))


def score_submission(raw, truth: Truth, public: PublicEpisode, inspection_steps: int = 0) -> Score:
    """Pure matcher. Caller must validate private truth against public records first."""
    integer(inspection_steps, "inspection_steps", 0, 100)
    truth = Truth.from_dict(truth.to_dict())
    if truth.episode_id != public.manifest.episode_id:
        raise DataError("truth episode_id mismatch")
    try:
        submission = Submission.from_dict(raw)
        if submission.episode_id != truth.episode_id:
            raise DataError("submission episode_id mismatch")
    except DataError as exc:
        return Score(0, 0, len(truth.issues), 0.0, 0.0, 0.0, -1.0, inspection_steps, False, str(exc))
    available = evidence_ids(public)
    issues = sorted(truth.issues, key=lambda issue: issue.issue_id)
    candidates = []
    tolerance = public.manifest.amount_tolerance_minor
    for finding in submission.findings:
        supplied = set(finding.evidence_ids)
        candidates.append([
            index for index, issue in enumerate(issues)
            if finding.type == issue.type and finding.affected_ids == issue.affected_ids
            and finding.currency == issue.currency
            and abs(finding.claimed_amount_minor - issue.expected_amount_minor) <= tolerance
            and supplied <= available
            and any(set(required) <= supplied for required in issue.acceptable_evidence_sets)
        ])
    # Augmenting paths avoid a greedy-order bug when tolerance ranges overlap.
    matched = {}

    def assign(finding_index, visited):
        for issue_index in candidates[finding_index]:
            if issue_index in visited:
                continue
            visited.add(issue_index)
            if issue_index not in matched or assign(matched[issue_index], visited):
                matched[issue_index] = finding_index
                return True
        return False

    for index in range(len(submission.findings)):
        assign(index, set())
    tp = len(matched)
    fp, fn = len(submission.findings) - tp, len(issues) - tp
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * tp / (2 * tp + fp + fn) if tp + fp + fn else 1.0
    reward = max(-1.0, min(1.0, 2 * f1 - 1 - 0.002 * inspection_steps))
    return Score(tp, fp, fn, precision, recall, f1, reward, inspection_steps, True)


def evaluate_submission(raw, truth: Truth, public: PublicEpisode, inspection_steps: int = 0) -> Score:
    """Host-side entry point: verify truth independently before calculating reward."""
    validate_truth(public, truth)
    return score_submission(raw, truth, public, inspection_steps)
