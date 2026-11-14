"""Trusted-host training rollouts of observation-only policies on stored train data.

This exports interactions and rewards, not model weights or isolated workers.
"""

import json
from pathlib import Path

from genesis_fintech import __version__
from genesis_fintech.domain.models import DataError, integer, object_fields
from genesis_fintech.environment.core import AuditEnv
from genesis_fintech.generation.datasets import validate_dataset, sha256, _read_bytes
from genesis_fintech.generation.storage import json_text, load_scenario, parse_json, read_json
from genesis_fintech.policies.baselines import make_policy

FORMAT = "training-rollouts-v1"
POLICIES = ("random", "flag-all", "reconciliation")
FILES = ("initial_observations.jsonl", "trajectories.jsonl")
PRIVATE_KEYS = {"truth", "provenance", "seed", "expected_amount_minor",
                "acceptable_evidence_sets", "latent_history"}


def _line(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False)+"\n"


def _copy(value):
    return json.loads(json.dumps(value, allow_nan=False))


def _parse(raw):
    try:
        return parse_json(raw.decode("utf-8"))
    except UnicodeError as exc:
        raise DataError("rollouts: invalid UTF-8") from exc


def _visible(value):
    if type(value) is dict:
        if PRIVATE_KEYS & set(value):
            raise DataError("rollouts: private field in policy-visible data")
        for child in value.values(): _visible(child)
    elif type(value) is list:
        for child in value: _visible(child)


def _train_items(root):
    index = read_json(root/"dataset.json")
    return [item for item in index["episodes"] if item["split"] == "train"]


def collect_trajectories(directory, output, *, policy="reconciliation", policy_seed=17):
    if policy not in POLICIES:
        raise DataError("rollouts: only observation-only baseline policies are permitted")
    integer(policy_seed, "policy_seed", 0, 2**63-1)
    root, output = Path(directory), Path(output)
    corpus = validate_dataset(root)
    if output.exists() or output.is_symlink():
        raise FileExistsError(output)
    initials, traces, episodes = [], [], []
    for item in _train_items(root):
        public, truth = load_scenario(root/"episodes"/"train"/item["episode_id"])
        env = AuditEnv(mode="train")
        observation, _ = env.reset_episode(public, truth)
        initial = _copy(observation)
        agent = make_policy(policy, policy_seed)
        agent.reset(_copy(observation))
        while True:
            action = agent.act(_copy(observation))
            observation, _, terminated, truncated, _ = env.step(action)
            if observation.get("error") or truncated:
                raise DataError("rollouts: baseline failed the training execution contract")
            if terminated: break
        _visible(initial)
        _visible(env.trajectory)
        initials.append({"episode_id": item["episode_id"], "observation": initial})
        traces.extend(env.trajectory)
        episodes.append({"episode_id": item["episode_id"], "steps": len(env.trajectory),
                         "episode_return": env.trajectory[-1]["reward"],
                         "public_sha256": sha256(json_text(public.to_dict()).encode())})
    contents = {"initial_observations.jsonl": "".join(map(_line, initials)).encode(),
                "trajectories.jsonl": "".join(map(_line, traces)).encode()}
    manifest = {"format": FORMAT, "engine_version": __version__, "mode": "train", "split": "train",
                "policy": policy, "policy_seed": policy_seed, "security_mode": "trusted_in_process",
                "model_weight_training": False, "dataset_id": corpus["dataset_id"],
                "public_archive_sha256": corpus["public_archive_sha256"], "episodes": episodes,
                "files": {name: sha256(data) for name, data in contents.items()}}
    output.mkdir(parents=True, exist_ok=False)
    for name, data in contents.items():
        (output/name).write_bytes(data)
    (output/"manifest.json").write_text(json_text(manifest), encoding="utf-8")
    return validate_trajectories(root, output)


def validate_trajectories(directory, rollouts):
    """Replay every saved action against independently validated stored episodes.

    A correct checksum alone cannot justify an invented observation or reward.
    The generator and oracle are never used to construct replayed transitions.
    """
    root, output = Path(directory), Path(rollouts)
    corpus = validate_dataset(root)
    if output.is_symlink() or not output.is_dir():
        raise DataError("rollouts: expected a regular directory")
    manifest = _parse(_read_bytes(output/"manifest.json"))
    object_fields(manifest, {"format", "engine_version", "mode", "split", "policy", "policy_seed",
                             "security_mode", "model_weight_training", "dataset_id",
                             "public_archive_sha256", "episodes", "files"})
    if (manifest["format"] != FORMAT or manifest["engine_version"] != __version__
            or manifest["mode"] != "train" or manifest["split"] != "train"
            or manifest["policy"] not in POLICIES or manifest["security_mode"] != "trusted_in_process"
            or manifest["model_weight_training"] is not False
            or manifest["dataset_id"] != corpus["dataset_id"]
            or manifest["public_archive_sha256"] != corpus["public_archive_sha256"]):
        raise DataError("rollouts: incompatible manifest or corpus")
    integer(manifest["policy_seed"], "policy_seed", 0, 2**63-1)
    object_fields(manifest["files"], set(FILES))
    data = {}
    for name in FILES:
        raw = _read_bytes(output/name)
        if sha256(raw) != manifest["files"][name]:
            raise DataError("rollouts: file checksum mismatch")
        try:
            data[name] = [parse_json(line) for line in raw.decode("utf-8").splitlines()]
        except UnicodeError as exc:
            raise DataError("rollouts: invalid UTF-8") from exc
    items = _train_items(root)
    if (type(manifest["episodes"]) is not list or len(manifest["episodes"]) != len(items)
            or len(data[FILES[0]]) != len(items)):
        raise DataError("rollouts: exactly ten train episodes required")
    trace, cursor, returns = data[FILES[1]], 0, []
    for item, meta, initial in zip(items, manifest["episodes"], data[FILES[0]]):
        object_fields(meta, {"episode_id", "steps", "episode_return", "public_sha256"})
        object_fields(initial, {"episode_id", "observation"})
        steps = integer(meta["steps"], "steps", 1, 100)
        if meta["episode_id"] != item["episode_id"] or initial["episode_id"] != item["episode_id"]:
            raise DataError("rollouts: unexpected episode identity or dev episode")
        public, truth = load_scenario(root/"episodes"/"train"/item["episode_id"])
        if meta["public_sha256"] != sha256(json_text(public.to_dict()).encode()):
            raise DataError("rollouts: public records mismatch")
        env = AuditEnv(mode="train")
        observation, _ = env.reset_episode(public, truth)
        if _line(observation) != _line(initial["observation"]):
            raise DataError("rollouts: initial observation mismatch")
        _visible(initial)
        agent = make_policy(manifest["policy"], manifest["policy_seed"])
        agent.reset(_copy(observation))
        for step in range(1, steps+1):
            if cursor >= len(trace): raise DataError("rollouts: missing transition")
            saved = trace[cursor]
            object_fields(saved, {"episode_id", "step", "action", "observation", "reward", "terminated", "truncated"})
            _visible(saved)
            # Verify claimed policy identity as well as transition correctness.
            if _line(saved["action"]) != _line(agent.act(_copy(observation))):
                raise DataError("rollouts: action does not match declared policy")
            observation, reward, terminated, truncated, _ = env.step(saved["action"])
            if _line(saved) != _line(env.trajectory[-1]):
                raise DataError("rollouts: transition or reward replay mismatch")
            if truncated or observation.get("error") or terminated != (step == steps):
                raise DataError("rollouts: invalid terminal state")
            cursor += 1
        if type(meta["episode_return"]) not in (float, int) or meta["episode_return"] != reward:
            raise DataError("rollouts: episode return mismatch")
        returns.append(reward)
    if cursor != len(trace):
        raise DataError("rollouts: unexpected extra transitions")
    return {"ok": True, "format": FORMAT, "episodes": len(items), "transitions": len(trace),
            "mode": "train", "split": "train", "policy": manifest["policy"],
            "mean_episode_return": sum(returns)/len(returns), "replay_verified": True,
            "model_weight_training": False, "security_mode": "trusted_in_process"}
