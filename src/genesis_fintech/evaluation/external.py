"""Supervisor-side external policy runner with bounded, deadline-aware pipes.

Docker is the default and fails closed. Development subprocesses are for trusted
code only: a subprocess alone does not restrict access to host files or network.
"""

from contextlib import contextmanager
import json
import os
from pathlib import Path
import selectors
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import uuid

from genesis_fintech import __version__
from genesis_fintech.domain.models import DataError, integer
from genesis_fintech.environment.core import AuditEnv
from genesis_fintech.generation.scenario import generate_scenario
from genesis_fintech.generation.storage import json_text, write_scenario
from genesis_fintech.policies.wire import MAX_FRAME_BYTES, ProtocolError, decode_frame, encode_frame

DEFAULT_IMAGE = "genesis-audit-worker:0.4.0"
POLICIES = {"random", "flag-all", "reconciliation"}


class WorkerTimeout(Exception):
    pass


class WorkerExit(Exception):
    pass


class WorkerChannel:
    """A single request/response stream. No shell, inherited stdin or stderr logs."""

    def __init__(self, command, *, cwd, env):
        self.process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=subprocess.DEVNULL, cwd=cwd, env=env,
                                        start_new_session=True, bufsize=0, close_fds=True)
        os.set_blocking(self.process.stdin.fileno(), False)
        os.set_blocking(self.process.stdout.fileno(), False)
        self.buffer = bytearray()

    def _wait(self, stream, event, deadline):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise WorkerTimeout()
        with selectors.DefaultSelector() as selector:
            selector.register(stream, event)
            if not selector.select(remaining):
                raise WorkerTimeout()

    def exchange(self, observation, request_id, deadline):
        data = memoryview(encode_frame(request_id, "observation", observation))
        while data:
            self._wait(self.process.stdin, selectors.EVENT_WRITE, deadline)
            try:
                count = os.write(self.process.stdin.fileno(), data)
            except BlockingIOError:
                continue
            except BrokenPipeError as exc:
                raise WorkerExit() from exc
            data = data[count:]
        while b"\n" not in self.buffer:
            self._wait(self.process.stdout, selectors.EVENT_READ, deadline)
            try:
                block = os.read(self.process.stdout.fileno(), min(65536, MAX_FRAME_BYTES + 1 - len(self.buffer)))
            except BlockingIOError:
                continue
            if not block:
                raise WorkerExit()
            self.buffer.extend(block)
            if len(self.buffer) > MAX_FRAME_BYTES:
                raise ProtocolError("invalid worker frame")
        line, _, rest = self.buffer.partition(b"\n")
        self.buffer = bytearray(rest)
        return decode_frame(bytes(line) + b"\n", request_id, "action")

    def close(self):
        # Kill the whole development process group, including spawned descendants.
        status = self.process.poll()
        try:
            os.killpg(self.process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        except PermissionError:
            # A reaped group can be inaccessible in a nested macOS sandbox. A
            # live child must never silently survive a failed kill request.
            if status is None and self.process.poll() is None:
                raise
        finally:
            self.process.wait(timeout=5)
            self.process.stdin.close()
            self.process.stdout.close()


def drive_worker(env, initial, command, *, cwd, child_env, deadline, collect_resources=None):
    """Host-only primitive. command is trusted supervisor configuration, never an action."""
    observation, request_id, failure = initial, 0, None
    channel = WorkerChannel(command, cwd=cwd, env=child_env)
    resources = None
    try:
        while True:
            action = channel.exchange(observation, request_id, deadline)
            observation, _, terminated, truncated, _ = env.step(action)
            if terminated or truncated:
                break
            request_id += 1
    except (WorkerTimeout, ProtocolError, WorkerExit) as exc:
        failure = {WorkerTimeout: "worker_timeout", ProtocolError: "worker_protocol_error",
                   WorkerExit: "worker_exit"}[type(exc)]
        env.abort_worker(failure)
    finally:
        try:
            if collect_resources is not None:
                resources = collect_resources()
        finally:
            channel.close()
    return {"metrics": env.evaluation_result(), "failure": failure,
            "worker_resources": resources,
            "terminated": env.trajectory[-1]["terminated"], "truncated": env.trajectory[-1]["truncated"],
            "steps": sum(item["action"] is not None for item in env.trajectory)}


def docker_resources(name):
    """Read kernel cgroup-v2 counters before cleanup; never accept worker claims.

    The fixed reader runs as the same unprivileged UID and contributes to the
    measured peak itself. No mounts or extra capabilities are granted.
    """
    script = """import json
from pathlib import Path
p=Path('/sys/fs/cgroup')
cpu=dict(line.split() for line in (p/'cpu.stat').read_text().splitlines())
events=dict(line.split() for line in (p/'memory.events').read_text().splitlines())
print(json.dumps(dict(peak_memory_bytes=int((p/'memory.peak').read_text()),
 memory_limit_bytes=int((p/'memory.max').read_text()),cpu_usage_usec=int(cpu['usage_usec']),
 oom_kills=int(events['oom_kill']))))
"""
    try:
        result = subprocess.run(["docker", "exec", "--user", "65534:65534", name,
                                 "python", "-I", "-S", "-c", script],
                                capture_output=True, timeout=5, check=True)
        data = json.loads(result.stdout)
        required = {"peak_memory_bytes", "memory_limit_bytes", "cpu_usage_usec", "oom_kills"}
        if set(data) != required or any(type(value) is not int or value < 0 for value in data.values()):
            raise ValueError("invalid counters")
        return {"measured": True, "source": "cgroup_v2_including_counter_reader", **data}
    except (subprocess.SubprocessError, ValueError, OSError) as exc:
        return {"measured": False, "reason": type(exc).__name__}


def docker_image_id(image):
    if not shutil.which("docker"):
        raise DataError("Docker is unavailable; no fallback to an unisolated policy")
    try:
        result = subprocess.run(["docker", "image", "inspect", image], capture_output=True, timeout=10, check=True)
        metadata = json.loads(result.stdout)[0]
        image_id = metadata["Id"]
        if not image_id.startswith("sha256:") or metadata.get("Config", {}).get("Volumes"):
            raise ValueError()
        return image_id
    except (subprocess.SubprocessError, ValueError, KeyError, IndexError) as exc:
        raise DataError("A local worker image without declared volumes is required; build it first") from exc


def docker_command(image_id, name, worker_command):
    """No mounts, no socket, no host namespaces, no automatic pull, no image entrypoint."""
    return ["docker", "run", "--rm", "--interactive", "--pull=never", "--name", name,
            "--network=none", "--ipc=none", "--read-only", "--user=65534:65534",
            "--cap-drop=ALL", "--security-opt=no-new-privileges:true", "--pids-limit=64",
            "--memory=512m", "--memory-swap=512m", "--cpus=1", "--ulimit=nofile=128:128",
            "--ulimit=core=0:0", "--tmpfs=/tmp:rw,noexec,nosuid,nodev,size=64m",
            "--workdir=/tmp", "--hostname=audit-worker", "--log-driver=none",
            "--env=HOME=/tmp", "--env=PYTHONHASHSEED=0", "--entrypoint=python",
            image_id, *worker_command]


@contextmanager
def worker_launch(backend, policy, policy_seed, image):
    if backend not in {"docker", "development"} or policy not in POLICIES:
        raise DataError("unknown backend or external policy")
    integer(policy_seed, "policy_seed", 0, 2**63 - 1)
    image_id = docker_image_id(image) if backend == "docker" else None
    with tempfile.TemporaryDirectory(prefix="genesis-worker-") as cwd:
        name = "genesis-worker-" + uuid.uuid4().hex
        if backend == "docker":
            command = docker_command(image_id, name, ["-I", "-S", "-u",
                                     "/app/src/genesis_fintech/policies/worker.py", policy,
                                     "--policy-seed", str(policy_seed)])
            # Credentials/context are for the trusted Docker client; no host env
            # is forwarded into the container except explicit --env flags above.
            child_env = dict(os.environ)
        else:
            worker = Path(__file__).resolve().parents[1] / "policies" / "worker.py"
            command = [sys.executable, "-I", "-S", "-u", str(worker), policy, "--policy-seed", str(policy_seed)]
            child_env = {"PATH": os.defpath, "HOME": cwd, "LANG": "C.UTF-8", "PYTHONHASHSEED": "0"}
        try:
            yield command, cwd, child_env, image_id
        finally:
            if backend == "docker":
                # Killing the CLI is insufficient: remove the named container too.
                subprocess.run(["docker", "rm", "--force", name], stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL, timeout=10, check=False)


def run_external(seed, config, output, *, policy="reconciliation", policy_seed=0,
                 backend="docker", image=DEFAULT_IMAGE, wall_time_seconds=60, max_steps=100):
    integer(wall_time_seconds, "wall_time_seconds", 1, 60)
    integer(max_steps, "max_steps", 1, 100)
    # Backend preflight precedes generation/export; unavailable Docker is a hard error.
    with worker_launch(backend, policy, policy_seed, image) as (command, cwd, child_env, image_id):
        generated = generate_scenario(seed, config)
        output = Path(output)
        write_scenario(generated, output)
        return _run_loaded(generated.public, generated.truth, output, command, cwd, child_env, image_id,
                           policy, policy_seed, backend, wall_time_seconds, max_steps)


def run_external_episode(public, truth, output, *, policy="reconciliation", policy_seed=0,
                         backend="docker", image=DEFAULT_IMAGE, wall_time_seconds=60, max_steps=100):
    """Evaluate the exact stored episode. Seed/config are never required by the worker."""
    integer(wall_time_seconds, "wall_time_seconds", 1, 60)
    integer(max_steps, "max_steps", 1, 100)
    with worker_launch(backend, policy, policy_seed, image) as (command, cwd, child_env, image_id):
        output = Path(output)
        output.mkdir(parents=True, exist_ok=False)
        return _run_loaded(public, truth, output, command, cwd, child_env, image_id,
                           policy, policy_seed, backend, wall_time_seconds, max_steps)


def _run_loaded(public, truth, output, command, cwd, child_env, image_id,
                policy, policy_seed, backend, wall_time_seconds, max_steps):
    env = AuditEnv(mode="evaluation", max_steps=max_steps, wall_time_seconds=wall_time_seconds)
    initial, _ = env.reset_episode(public, truth)
    started = time.monotonic()
    result = drive_worker(env, initial, command, cwd=cwd, child_env=child_env,
                          deadline=started + wall_time_seconds,
                          collect_resources=(lambda: docker_resources(command[command.index("--name")+1]))
                          if backend == "docker" else None)
    result.update(version=__version__, protocol_version=1, policy=policy,
                  policy_seed=policy_seed, backend=backend, worker_image_id=image_id,
                  security_mode="docker_container" if backend == "docker" else "development_subprocess",
                  elapsed_seconds=time.monotonic() - started, ok=not result["truncated"])
    (output / "summary.json").write_text(json_text(result), encoding="utf-8")
    with (output / "trajectories.jsonl").open("x", encoding="utf-8") as stream:
        for item in env.trajectory:
            stream.write(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n")
    return result
