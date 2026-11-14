"""CLI for generation, development episodes and baseline evaluation."""

import argparse
import json
import sys

from . import __version__


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="genesis-fintech",
        description="Synthetic audit environment: four error families, development episodes and baseline benchmarks.",
    )
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("info", help="Show implementation status as JSON")
    commands.add_parser("doctor", help="Check the required Python version")
    web = commands.add_parser("serve", help="Start the local audit UI on loopback")
    web.add_argument("--port", type=int, default=8765)
    dataset = commands.add_parser("generate-dataset", help="Create a frozen 10-train/10-dev corpus and public archive")
    dataset.add_argument("--spec", required=True)
    dataset.add_argument("--output", required=True)
    dataset_check = commands.add_parser("validate-dataset", help="Independently verify dataset bytes, truth and optional replay")
    dataset_check.add_argument("directory")
    dataset_check.add_argument("--replay", action="store_true")
    rollouts = commands.add_parser("collect-trajectories", help="Export ordinary-policy training rewards from ten stored train episodes")
    rollouts.add_argument("directory")
    rollouts.add_argument("--output", required=True)
    rollouts.add_argument("--policy", choices=["random", "flag-all", "reconciliation"], default="reconciliation")
    rollouts.add_argument("--policy-seed", type=int, default=17)
    rollout_check = commands.add_parser("validate-trajectories", help="Replay saved training actions, observations and rewards")
    rollout_check.add_argument("directory")
    rollout_check.add_argument("rollouts")
    suite = commands.add_parser("evaluate-dataset", help="Evaluate all stored episodes with external policies and host-only oracle")
    suite.add_argument("directory")
    suite.add_argument("--output", required=True)
    suite.add_argument("--backend", choices=["docker", "development"], default="docker")
    suite.add_argument("--image", default="genesis-audit-worker:0.6.0")
    suite.add_argument("--policy-seed", type=int, default=17)
    suite.add_argument("--replay", action="store_true")
    generate = commands.add_parser("generate-clean", help="Generate and independently check a clean company")
    generate.add_argument("--seed", type=int, required=True)
    generate.add_argument("--output", required=True)
    generate.add_argument("--config", help="Strict clean-generation JSON config, e.g. configs/clean.json")
    generate.add_argument("--invoices", type=int, help="Override invoice_count (1..60)")
    validate = commands.add_parser("validate-clean", help="Independently validate a public clean-data directory")
    validate.add_argument("public_directory")
    for name, description in [("generate-scenario", "Generate a validated company with configurable error families"),
                              ("demo", "Run an evaluator-only oracle through the development environment")]:
        command = commands.add_parser(name, help=description)
        command.add_argument("--seed", type=int, required=True)
        command.add_argument("--output", required=True)
        command.add_argument("--config", help="Strict scenario config, e.g. configs/scenario.json")
    scenario_check = commands.add_parser("validate-scenario", help="Host-side validation of private truth against public records")
    scenario_check.add_argument("episode_directory")
    scorer = commands.add_parser("score", help="Host-side findings evaluation; not a policy-visible tool")
    scorer.add_argument("episode_directory")
    scorer.add_argument("--findings", required=True)
    scorer.add_argument("--inspection-steps", type=int, default=0)
    benchmark = commands.add_parser("benchmark", help="Compare observation-only baselines with a privileged oracle")
    benchmark.add_argument("--seeds", type=int, nargs="+", default=list(range(42, 52)))
    benchmark.add_argument("--policy-seed", type=int, default=0)
    benchmark.add_argument("--output", required=True)
    external = commands.add_parser("run-policy", help="Run an external JSON-line policy; Docker by default")
    external.add_argument("--seed", type=int, required=True)
    external.add_argument("--output", required=True)
    external.add_argument("--config")
    external.add_argument("--policy", choices=["random", "flag-all", "reconciliation"], default="reconciliation")
    external.add_argument("--policy-seed", type=int, default=0)
    external.add_argument("--backend", choices=["docker", "development"], default="docker")
    external.add_argument("--image", default="genesis-audit-worker:0.6.0")
    external.add_argument("--wall-time", type=int, default=60)
    external.add_argument("--max-steps", type=int, default=100)
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

    if args.command not in {"info", "doctor"}:
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
            if args.command in {"collect-trajectories", "validate-trajectories"}:
                from .evaluation.rollouts import collect_trajectories, validate_trajectories
                result = (collect_trajectories(args.directory, args.output, policy=args.policy, policy_seed=args.policy_seed)
                          if args.command == "collect-trajectories" else validate_trajectories(args.directory, args.rollouts))
                print(json.dumps(result, indent=2))
                return 0
            if args.command == "evaluate-dataset":
                from .evaluation.suite import evaluate_dataset
                result = evaluate_dataset(Path(args.directory), Path(args.output), backend=args.backend,
                                          image=args.image, policy_seed=args.policy_seed, replay=args.replay)
                print(json.dumps(result, indent=2))
                return 0
            if args.command in {"generate-dataset", "validate-dataset"}:
                from .generation.datasets import generate_dataset, validate_dataset
                result = (generate_dataset(read_json(Path(args.spec)), Path(args.output))
                          if args.command == "generate-dataset" else validate_dataset(Path(args.directory), replay=args.replay))
                print(json.dumps(result, indent=2))
                return 0
            if args.command == "serve":
                from .web.server import serve
                serve(args.port)
                return 0
            if args.command == "run-policy":
                from .evaluation.external import run_external
                from .generation.scenario import ScenarioConfig
                config = ScenarioConfig.from_dict(read_json(Path(args.config))) if args.config else ScenarioConfig()
                result = run_external(args.seed, config, Path(args.output), policy=args.policy,
                                      policy_seed=args.policy_seed, backend=args.backend, image=args.image,
                                      wall_time_seconds=args.wall_time, max_steps=args.max_steps)
                print(json.dumps(result, indent=2))
                return 0 if result["ok"] else 1
            if args.command == "benchmark":
                from .evaluation.benchmark import run_benchmark
                result = run_benchmark(args.seeds, Path(args.output), policy_seed=args.policy_seed)
                print(json.dumps(result, indent=2))
                return 0
            if args.command in {"generate-scenario", "demo"}:
                from .generation.scenario import ScenarioConfig, generate_scenario
                from .generation.storage import load_scenario, write_scenario
                config = ScenarioConfig.from_dict(read_json(Path(args.config))) if args.config else ScenarioConfig()
                if args.command == "demo":
                    from .evaluation.demo import run_demo
                    result = run_demo(args.seed, config, Path(args.output))
                else:
                    write_scenario(generate_scenario(args.seed, config), Path(args.output))
                    public, truth = load_scenario(Path(args.output))
                    result = {"ok": True, "episode_id": public.manifest.episode_id, "issues": len(truth.issues)}
                print(json.dumps(result, indent=2))
                return 0
            if args.command in {"validate-scenario", "score"}:
                from .generation.storage import load_scenario
                public, truth = load_scenario(Path(args.episode_directory))
                if args.command == "validate-scenario":
                    print(json.dumps({"ok": True, "issues": len(truth.issues)}, indent=2))
                    return 0
                from .evaluation.scoring import evaluate_submission
                result = evaluate_submission(read_json(Path(args.findings)), truth, public, args.inspection_steps)
                print(json.dumps(result.to_dict(), indent=2))
                return 0 if result.valid_submission else 1
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
        "status": "submission_candidate",
        "implemented": ["project_info", "python_version_check", "interface_protocols", "public_record_validation",
                        "decimal_conversion", "clean_generation", "public_private_export", "independent_clean_checker",
                        "four_error_families", "fx_payment_history", "boundary_decoys", "interaction_scenarios",
                        "truth_validation", "reward_matching", "development_reset_step", "oracle_demo",
                        "observation_only_baselines", "baseline_benchmark", "development_failure_analysis",
                        "bounded_worker_ipc", "external_policy_runner", "docker_worker_backend", "local_audit_ui",
                        "frozen_train_dev_datasets", "stored_episode_evaluation", "corpus_conformance_checks",
                        "worker_cgroup_measurements", "reproducible_source_bundle", "offline_wheel_installation",
                        "training_trajectory_export", "training_action_reward_replay"],
        "planned": [],
        "end_to_end_available": True,
        "security_mode": "development_in_process",
        "external_backends": ["docker", "development"],
    }, indent=2))
    return 0
