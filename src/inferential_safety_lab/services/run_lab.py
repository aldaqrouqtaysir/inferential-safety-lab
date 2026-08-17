"""Shared service for configuration validation, preview, execution, and export."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

from inferential_safety_lab.core.configuration import RunConfig, load_config
from inferential_safety_lab.core.corruption import corrupt
from inferential_safety_lab.core.dgp import generate_truth
from inferential_safety_lab.core.engine import ProgressCallback, run_benchmark
from inferential_safety_lab.core.seeds import rng_for
from inferential_safety_lab.core.serialization import canonical_json
from inferential_safety_lab.domain.results import LabRun
from inferential_safety_lab.reporting.safety_card import render_safety_card


def validate_config(path: str | Path) -> RunConfig:
    return load_config(path)


def estimated_runtime_seconds(config: RunConfig) -> float:
    """Conservative local estimate used before execution; not a scientific result."""

    sample_factor = config.sample_size / 150.0
    scenario_factor = 1.3 if config.scenario_id.value == "GROSS_CONTAMINATION" else 1.0
    return max(0.5, config.repetitions * 0.015 * sample_factor * scenario_factor)


def preview_scenario(config: RunConfig, rows: int = 12) -> dict[str, Any]:
    """Return a small ephemeral before/after preview; never part of exported aggregates."""

    truth = generate_truth(
        n=config.sample_size,
        tau=config.tau,
        rng=rng_for(config.master_seed, "preview-dgp", config.scenario_id.value),
    )
    observed, record = corrupt(
        truth,
        config,
        rng_for(config.master_seed, "preview-corruption", config.scenario_id.value),
    )
    count = min(rows, config.sample_size)
    preview = [
        {
            "row": int(truth.row_id[index]),
            "treatment": int(truth.treatment[index]),
            "outcome": round(float(truth.outcome[index]), 3),
            "clean_z": round(float(truth.latent_z[index]), 3),
            "observed_z": (
                None
                if observed.observed_z[index] != observed.observed_z[index]
                else round(float(observed.observed_z[index]), 3)
            ),
            "status": (
                "missing"
                if bool(record.missing_mask[index])
                else "displaced"
                if bool(record.contamination_mask[index])
                else "unchanged"
            ),
        }
        for index in range(count)
    ]
    return {
        "rows": preview,
        "realized_missing_fraction": float(record.missing_mask.mean()),
        "realized_contamination_fraction": float(record.contamination_mask.mean()),
        "note": "Preview rows are ephemeral and excluded from downloads.",
    }


def run_lab(config: RunConfig, progress: ProgressCallback | None = None) -> LabRun:
    return run_benchmark(config, progress)


def run_path(path: str | Path, progress: ProgressCallback | None = None) -> LabRun:
    return run_lab(load_config(path), progress)


def with_controls(config: RunConfig, **changes: Any) -> RunConfig:
    return replace(config, **changes)


def write_run_artifacts(run: LabRun, output: str | Path) -> dict[str, Path]:
    destination = Path(output)
    destination.mkdir(parents=True, exist_ok=True)
    paths = {
        "configuration": destination / "run-config.json",
        "aggregate": destination / "aggregate.canonical.json",
        "safety_card": destination / "inferential-safety-card.html",
        "runtime": destination / "runtime-diagnostics.json",
    }
    paths["configuration"].write_text(
        json.dumps(run.aggregate["configuration"], indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    paths["aggregate"].write_text(run.canonical_json, encoding="utf-8", newline="\n")
    paths["safety_card"].write_text(
        render_safety_card(run.aggregate), encoding="utf-8", newline="\n"
    )
    paths["runtime"].write_text(
        json.dumps(run.runtime_diagnostics, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return paths


def canonical_config(config: RunConfig) -> str:
    return canonical_json(config.as_dict()) + "\n"
