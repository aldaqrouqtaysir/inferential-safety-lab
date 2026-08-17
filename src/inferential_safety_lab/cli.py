"""Thin CLI over the same lab service used by Streamlit."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from inferential_safety_lab.core.configuration import ScenarioId
from inferential_safety_lab.services.presets import get_preset
from inferential_safety_lab.services.run_lab import (
    canonical_config,
    run_lab,
    run_path,
    validate_config,
    write_run_artifacts,
)


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
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
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
