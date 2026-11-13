"""CLI for project inspection and the verified clean-data milestone."""

import argparse
import json
import sys

from . import __version__


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="genesis-fintech",
        description="Synthetic clean financial records; agent episodes and scoring are not implemented yet.",
    )
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("info", help="Show implementation status as JSON")
    commands.add_parser("doctor", help="Check the required Python version")
    generate = commands.add_parser("generate-clean", help="Generate and independently check a clean company")
    generate.add_argument("--seed", type=int, required=True)
    generate.add_argument("--output", required=True)
    generate.add_argument("--config", help="Strict clean-generation JSON config, e.g. configs/clean.json")
    generate.add_argument("--invoices", type=int, help="Override invoice_count (1..60)")
    validate = commands.add_parser("validate-clean", help="Independently validate a public clean-data directory")
    validate.add_argument("public_directory")
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

    if args.command in {"generate-clean", "validate-clean"}:
        if sys.version_info < (3, 11):
            print(json.dumps({"ok": False, "error": "Python 3.11 or newer required"}))
            return 2
        from dataclasses import replace
        from pathlib import Path
        from .domain.models import DataError
        from .evaluation.clean import check_clean
        from .generation.clean import CleanConfig, generate_clean
        from .generation.storage import load_public, read_json, write_clean
        try:
            if args.command == "generate-clean":
                config = CleanConfig.from_dict(read_json(Path(args.config))) if args.config else CleanConfig()
                if args.invoices is not None:
                    config = replace(config, invoice_count=args.invoices)
                generated = generate_clean(args.seed, config)
                write_clean(generated, Path(args.output))
                # Verify files, not just the objects passed to the writer.
                report = check_clean(load_public(Path(args.output) / "public"))
            else:
                report = check_clean(load_public(Path(args.public_directory)))
            print(json.dumps(report.to_dict(), indent=2))
            return 0 if report.ok else 1
        except (DataError, OSError) as exc:
            print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
            return 2

    print(json.dumps({
        "project": "genesis-fintech-env",
        "version": __version__,
        "status": "clean_data_milestone",
        "implemented": ["project_info", "python_version_check", "interface_protocols", "public_record_validation",
                        "decimal_conversion", "clean_generation", "public_private_export", "independent_clean_checker"],
        "planned": ["error_injection", "environment", "reward_matching", "policies", "process_isolation"],
        "end_to_end_available": False,
    }, indent=2))
    return 0
