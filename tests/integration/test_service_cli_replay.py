from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

from inferential_safety_lab.cli import main
from inferential_safety_lab.core.configuration import ScenarioId
from inferential_safety_lab.reporting.safety_card import render_safety_card
from inferential_safety_lab.services.presets import get_preset
from inferential_safety_lab.services.run_lab import (
    estimated_runtime_seconds,
    preview_scenario,
    run_lab,
    write_run_artifacts,
)


def test_service_runs_all_three_fixed_panels() -> None:
    for scenario in ScenarioId:
        run = run_lab(get_preset(scenario))
        assert run.aggregate["scenario_id"] == scenario.value
        assert len(run.aggregate["method_contracts"]) == 4
        assert len(run.aggregate["method_metrics"]) == 4
        assert "winner" not in run.aggregate["headline_observation"].lower()


def test_preview_is_ephemeral_and_runtime_is_bounded() -> None:
    config = get_preset(ScenarioId.MCAR_SMALL_EFFECTIVE_SAMPLE)
    preview = preview_scenario(config, rows=5)
    assert len(preview["rows"]) == 5
    assert estimated_runtime_seconds(config) < 30.0
    run = run_lab(config)
    assert "clean_z" not in run.canonical_json
    assert '"row_id"' not in run.canonical_json
    assert "python_executable" not in run.runtime_diagnostics
    assert all("\\Users\\" not in str(value) for value in run.runtime_diagnostics.values())


def test_changed_seed_changes_replay_hash() -> None:
    config = get_preset(ScenarioId.MCAR_SMALL_EFFECTIVE_SAMPLE)
    assert run_lab(config).replay_hash != run_lab(replace(config, master_seed=99)).replay_hash


def test_same_service_result_is_byte_identical() -> None:
    config = get_preset(ScenarioId.MCAR_SMALL_EFFECTIVE_SAMPLE)
    first = run_lab(config)
    second = run_lab(config)
    assert first.canonical_json.encode() == second.canonical_json.encode()
    assert first.replay_hash == second.replay_hash


def test_cli_and_service_equivalence(tmp_path: Path) -> None:
    output = tmp_path / "cli"
    assert main(["run", "--config", "configs/demo_mcar_stress.json", "--output", str(output)]) == 0
    service = run_lab(get_preset(ScenarioId.MCAR_SMALL_EFFECTIVE_SAMPLE))
    assert (output / "aggregate.canonical.json").read_bytes() == service.canonical_json.encode()
    assert render_safety_card(service.aggregate) == (
        output / "inferential-safety-card.html"
    ).read_text(encoding="utf-8")


def test_validate_and_demo_commands(tmp_path: Path, capsys: object) -> None:
    del capsys
    assert main(["validate-config", "--config", "configs/demo_mcar_stress.json"]) == 0
    assert main(["demo", "--output", str(tmp_path / "demo")]) == 0


def test_write_artifacts_contains_only_aggregate_and_replay_material(tmp_path: Path) -> None:
    run = run_lab(get_preset(ScenarioId.GROSS_CONTAMINATION))
    paths = write_run_artifacts(run, tmp_path)
    assert set(paths) == {"configuration", "aggregate", "safety_card", "runtime"}
    aggregate = json.loads(paths["aggregate"].read_text(encoding="utf-8"))
    assert aggregate["privacy"]["row_level_data_exported"] is False
    assert "row_id" not in paths["aggregate"].read_text(encoding="utf-8")


def test_fresh_process_replay_is_byte_identical(tmp_path: Path) -> None:
    first, second = tmp_path / "one", tmp_path / "two"
    command = [
        sys.executable,
        "-m",
        "inferential_safety_lab.cli",
        "run",
        "--config",
        "configs/demo_mcar_stress.json",
        "--output",
    ]
    subprocess.run([*command, str(first)], check=True, capture_output=True, text=True)
    subprocess.run([*command, str(second)], check=True, capture_output=True, text=True)
    first_bytes = (first / "aggregate.canonical.json").read_bytes()
    second_bytes = (second / "aggregate.canonical.json").read_bytes()
    assert first_bytes == second_bytes
    assert json.loads(first_bytes)["replay_hash"] == json.loads(second_bytes)["replay_hash"]
