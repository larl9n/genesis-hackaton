"""Worker entry point: stdin observations -> stdout actions; never reads episodes.

Run via an isolated Python interpreter. In the Docker image only public domain
primitives and policies are present, not the environment, truth or generator.
"""

import argparse
from pathlib import Path
import sys

if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from genesis_fintech.policies.baselines import make_policy
from genesis_fintech.policies.wire import MAX_FRAME_BYTES, decode_frame, encode_frame


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("policy", choices=["random", "flag-all", "reconciliation"])
    parser.add_argument("--policy-seed", type=int, default=0)
    args = parser.parse_args()
    policy = make_policy(args.policy, args.policy_seed)
    request_id = 0
    while True:
        data = sys.stdin.buffer.readline(MAX_FRAME_BYTES + 1)
        if not data:
            return 0
        observation = decode_frame(data, request_id, "observation")
        if request_id == 0:
            policy.reset(observation)
        action = policy.act(observation)
        sys.stdout.buffer.write(encode_frame(request_id, "action", action))
        sys.stdout.buffer.flush()
        request_id += 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, KeyError, TypeError, OSError, RecursionError):
        # No tracebacks or incoming content on the protocol stream.
        raise SystemExit(2)
