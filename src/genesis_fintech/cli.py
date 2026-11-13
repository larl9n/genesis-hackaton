"""Small, dependency-free CLI for inspecting the project scaffold."""

import argparse
import json
import sys

from . import __version__


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="genesis-fintech",
        description="Project scaffold; episode generation and evaluation are not implemented.",
    )
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("info", help="Show implementation status as JSON")
    commands.add_parser("doctor", help="Check the required Python version")
    args = parser.parse_args()

    if args.command == "doctor":
        supported = sys.version_info >= (3, 11)
        print(json.dumps({
            "python": ".".join(str(part) for part in sys.version_info[:3]),
            "required_python": ">=3.11",
            "ok": supported,
            "message": "Python version is supported." if supported else "Install Python 3.11 or newer.",
        }, indent=2))
        return 0 if supported else 1

    print(json.dumps({
        "project": "genesis-fintech-env",
        "version": __version__,
        "status": "scaffold",
        "implemented": ["project_info", "python_version_check", "interface_protocols"],
        "planned": ["domain", "generation", "environment", "evaluation", "policies"],
        "end_to_end_available": False,
    }, indent=2))
    return 0
