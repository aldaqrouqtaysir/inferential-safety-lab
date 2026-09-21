from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from inferential_safety_lab.cli import main
from inferential_safety_lab.core.configuration import RunConfig, ScenarioId
from inferential_safety_lab.core.serialization import canonical_json
from inferential_safety_lab.core.study_configuration import STUDY_SCHEMA_VERSION, StudyConfig
from inferential_safety_lab.domain.results import LabRun
from inferential_safety_lab.services import run_study as study_service
from inferential_safety_lab.services.presets import get_preset
from inferential_safety_lab.services.run_lab import run_lab
from inferential_safety_lab.services.run_study import STUDY_FILES, run_study


def study(scenario: ScenarioId = ScenarioId.MCAR_SMALL_EFFECTIVE_SAMPLE) -> StudyConfig:
    return StudyConfig.from_dict(
        {
            "schema_version": STUDY_SCHEMA_VERSION,
            "base_config": replace(get_preset(scenario), repetitions=80).as_dict(),
            "grid": {"sample_size": [100, 300], "master_seed": [31]},
        }
    )


@pytest.mark.parametrize("scenario", list(ScenarioId))
def test_study_matches_individual_runs_and_preserves_denominators(
    tmp_path: Path, scenario: ScenarioId
) -> None:
    config = study(scenario)
    output = tmp_path / "study"
    summary = run_study(config, output)
    assert len(summary["runs"]) == 2
    assert len(summary["comparisons"]) == 8
    assert {row["attempted_runs"] for row in summary["comparisons"]} == {80}
    assert all(row["conditional_coverage_denominator"] <= 80 for row in summary["comparisons"])
    for cell, record in zip(config.expand(), summary["runs"], strict=True):
        expected = run_lab(cell)
        content = (output / record["artifact_directory"] / "aggregate.canonical.json").read_bytes()
        assert content == expected.canonical_json.encode("utf-8")
        assert hashlib.sha256(content).hexdigest() == record["aggregate_sha256"]
        assert expected.replay_hash == record["replay_hash"]
        comparisons = [row for row in summary["comparisons"] if row["run_id"] == record["run_id"]]
        for row, metric in zip(comparisons, expected.aggregate["method_metrics"], strict=True):
            assert {key: row[key] for key in metric} == metric
    with (output / "comparison.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 8
    for row in rows:
        assert int(row["attempted_runs"]) == 80
        assert isinstance(json.loads(row["failure_code_counts"]), dict)
        if row["interval_scientifically_applicable"] == "false":
            assert row["conditional_coverage"] == row["interval_availability"] == ""
            assert row["interval_available_runs"] == "0"
    assert "N/A" in (output / "study-report.html").read_text(encoding="utf-8")
    assert json.loads((output / "study.canonical.json").read_text()) == json.loads(
        canonical_json(summary)
    )


def test_no_overwrite_and_no_partial_result_after_unexpected_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "study"
    output.mkdir()
    sentinel = output / "keep.txt"
    sentinel.write_text("prior result")
    with pytest.raises(FileExistsError, match="already exists"):
        run_study(study(), output)
    assert sentinel.read_text() == "prior result"
    calls = 0

    def fail_second(config: RunConfig) -> LabRun:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("unexpected runner failure")
        return run_lab(config)

    monkeypatch.setattr(study_service, "run_lab", fail_second)
    failed = tmp_path / "failed"
    with pytest.raises(RuntimeError, match="unexpected runner failure"):
        run_study(study(), failed)
    assert calls == 2
    assert not failed.exists()
    assert list(tmp_path.iterdir()) == [output]


def test_output_created_during_run_is_preserved(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "study"

    def competing_output(config: RunConfig) -> LabRun:
        output.mkdir(exist_ok=True)
        (output / "keep.txt").write_text("concurrent result")
        return run_lab(config)

    monkeypatch.setattr(study_service, "run_lab", competing_output)
    with pytest.raises(FileExistsError, match="during execution"):
        run_study(study(), output)
    assert (output / "keep.txt").read_text() == "concurrent result"
    assert list(output.iterdir()) == [output / "keep.txt"]


def test_validation_does_not_run_and_bad_last_cell_creates_no_output(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    config_path = tmp_path / "study.json"
    config_path.write_text(canonical_json(study().as_dict()), encoding="utf-8")

    def unexpected_run(*args: Any, **kwargs: Any) -> None:
        pytest.fail("validation must not execute a benchmark")

    monkeypatch.setattr(study_service, "run_lab", unexpected_run)
    assert main(["validate-study", "--config", str(config_path)]) == 0
    assert capsys.readouterr().out == "runs=2\nsimulated_datasets=160\n"
    payload = study().as_dict()
    payload["grid"] = {"sample_size": [100, 250]}
    config_path.write_text(canonical_json(payload), encoding="utf-8")
    output = tmp_path / "invalid"
    with pytest.raises(SystemExit) as error:
        main(["study", "--config", str(config_path), "--output", str(output)])
    assert error.value.code == 2
    assert "sample_size must be one of" in capsys.readouterr().err
    assert not output.exists()
    with pytest.raises(SystemExit):
        main(["validate-study", "--config", str(tmp_path / "missing.json")])


def test_fresh_process_study_replay_and_aggregate_only_exports(tmp_path: Path) -> None:
    config = tmp_path / "study.json"
    config.write_text(canonical_json(study().as_dict()), encoding="utf-8")
    command = [
        sys.executable,
        "-m",
        "inferential_safety_lab.cli",
        "study",
        "--config",
        str(config),
        "--output",
    ]
    first, second = tmp_path / "one", tmp_path / "two"
    for output in (first, second):
        result = subprocess.run([*command, str(output)], check=True, capture_output=True, text=True)
        assert "study_id=" in result.stdout
    files = [path.relative_to(first) for path in first.rglob("*") if path.is_file()]
    assert set(STUDY_FILES.values()) <= {str(path) for path in files}
    assert len(files) == 13
    for relative in files:
        content = (first / relative).read_bytes()
        if relative.name != "runtime-diagnostics.json":
            assert content == (second / relative).read_bytes()
        text = content.decode("utf-8")
        for forbidden in ('"row_id"', '"clean_z"', "python_executable", str(tmp_path), "https://"):
            assert forbidden not in text
    # Re-running into the same output is a clear CLI error and leaves the export intact.
    before = (first / "study.canonical.json").read_bytes()
    result = subprocess.run([*command, str(first)], capture_output=True, text=True)
    assert result.returncode == 2
    assert "already exists" in result.stderr
    assert (first / "study.canonical.json").read_bytes() == before
