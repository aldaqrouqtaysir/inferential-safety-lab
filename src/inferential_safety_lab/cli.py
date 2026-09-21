"""Thin CLI over the same lab service used by Streamlit."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from inferential_safety_lab.core.configuration import ScenarioId
from inferential_safety_lab.core.study_configuration import load_study
from inferential_safety_lab.services.presets import get_preset
from inferential_safety_lab.services.run_lab import (
    canonical_config,
    run_lab,
    run_path,
    validate_config,
    write_run_artifacts,
)
from inferential_safety_lab.services.run_study import STUDY_FILES, run_study


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="inferential-safety",
        description="Run bounded failure-aware known-truth simulations.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate = subparsers.add_parser("validate-config", help="Validate a versioned JSON config")
    validate.add_argument("--config", required=True, type=Path)
    run = subparsers.add_parser("run", help="Run one benchmark configuration")
    run.add_argument("--config", required=True, type=Path)
    run.add_argument("--output", required=True, type=Path)
    demo = subparsers.add_parser("demo", help="Run the frozen MCAR demo")
    demo.add_argument("--output", required=True, type=Path)
    validate_study = subparsers.add_parser(
        "validate-study", help="Validate every cell of a bounded study without running it"
    )
    validate_study.add_argument("--config", required=True, type=Path)
    study = subparsers.add_parser("study", help="Compare a grid of reproducible benchmarks")
    study.add_argument("--config", required=True, type=Path)
    study.add_argument("--output", required=True, type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if args.command in ("validate-study", "study"):
        try:
            config = load_study(args.config)
            cells = config.expand()
            if args.command == "validate-study":
                print(f"runs={len(cells)}")
                print(f"simulated_datasets={sum(cell.repetitions for cell in cells)}")
            else:
                summary = run_study(config, args.output)
                print(f"study_id={summary['study_id']}")
                for name, filename in STUDY_FILES.items():
                    print(f"{name}={args.output / filename}")
        except (OSError, ValueError) as exc:
            parser.error(str(exc))
        return 0
    if args.command == "validate-config":
        print(canonical_config(validate_config(args.config)), end="")
        return 0
    if args.command == "run":
        result = run_path(args.config)
    else:
        result = run_lab(get_preset(ScenarioId.MCAR_SMALL_EFFECTIVE_SAMPLE))
    paths = write_run_artifacts(result, args.output)
    print(f"replay_hash={result.replay_hash}")
    for name, path in paths.items():
        print(f"{name}={path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
