"""Execute existing benchmarks in a validated grid and publish complete local reports."""

from __future__ import annotations

import csv
import hashlib
import io
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from inferential_safety_lab.core.serialization import canonical_json, stable_hash
from inferential_safety_lab.core.study_configuration import StudyConfig
from inferential_safety_lab.domain.results import LabRun
from inferential_safety_lab.reporting.study import render_study_chart, render_study_report
from inferential_safety_lab.services.run_lab import run_lab, write_run_artifacts

STUDY_RESULTS_SCHEMA_VERSION = "inferential_safety_lab.study-results.v1"
STUDY_FILES = {
    "configuration": "study-config.json",
    "summary": "study.canonical.json",
    "comparison": "comparison.csv",
    "chart": "comparison.svg",
    "report": "study-report.html",
}


def _comparison_rows(run: LabRun, run_id: str) -> list[dict[str, Any]]:
    config = run.aggregate["configuration"]
    contracts = {row["method_id"]: row for row in run.aggregate["method_contracts"]}
    return [
        {
            "run_id": run_id,
            **{
                key: config[key]
                for key in (
                    "scenario_id",
                    "sample_size",
                    "missingness_rate",
                    "contamination_fraction",
                    "contamination_displacement",
                    "master_seed",
                    "repetitions",
                    "tau",
                )
            },
            **row,
            "interval_scientifically_applicable": contracts[row["method_id"]][
                "interval_scientifically_applicable"
            ],
            "interval_unavailability_reason": contracts[row["method_id"]][
                "interval_unavailability_reason"
            ],
        }
        for row in run.aggregate["method_metrics"]
    ]


def _comparison_csv(rows: list[dict[str, Any]]) -> str:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    for row in rows:
        values = dict(row)
        if not row["interval_scientifically_applicable"]:
            # Keep attempt counts but do not label a scientifically meaningless rate as zero.
            for key in (
                "interval_availability",
                "interval_availability_wilson",
                "conditional_coverage",
                "conditional_coverage_wilson",
                "valid_and_cover_rate",
                "mean_interval_length",
                "median_interval_length",
            ):
                values[key] = None
        writer.writerow(
            {
                key: canonical_json(value) if isinstance(value, (dict, list, bool)) else value
                for key, value in values.items()
            }
        )
    return stream.getvalue()


def run_study(config: StudyConfig, output: str | Path) -> dict[str, Any]:
    """Write a complete study to a new directory, leaving no partial study on failure.

    Expected method failures remain ordinary benchmark outcomes. Unexpected execution or
    filesystem errors propagate; a directory is published only after all artifacts exist.
    """

    cells = config.expand()
    requested = Path(output).absolute()
    if requested.exists() or requested.is_symlink():
        raise FileExistsError(f"study output already exists: {requested}; choose a new directory")
    destination = requested.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    runs: list[dict[str, Any]] = []
    comparisons: list[dict[str, Any]] = []
    with TemporaryDirectory(prefix=f".{destination.name}-", dir=destination.parent) as temporary:
        # TemporaryDirectory owns only this fresh sibling; it never removes prior study output.
        staging = Path(temporary) / "result"
        staging.mkdir()
        for index, cell in enumerate(cells, start=1):
            run_id = f"run-{index:03d}"
            run = run_lab(cell)
            relative = f"runs/{run_id}"
            paths = write_run_artifacts(run, staging / relative)
            runs.append(
                {
                    "run_id": run_id,
                    "configuration": cell.as_dict(),
                    "replay_hash": run.replay_hash,
                    "aggregate_sha256": hashlib.sha256(paths["aggregate"].read_bytes()).hexdigest(),
                    "artifact_directory": relative,
                }
            )
            comparisons.extend(_comparison_rows(run, run_id))
        summary = {
            "schema_version": STUDY_RESULTS_SCHEMA_VERSION,
            "study_id": stable_hash(
                {"configuration": config.as_dict(), "runs": runs}, domain="study-results"
            ),
            "configuration": config.as_dict(),
            "runs": runs,
            "comparisons": comparisons,
        }
        artifacts = {
            "configuration": canonical_json(config.as_dict()) + "\n",
            "summary": canonical_json(summary) + "\n",
            "comparison": _comparison_csv(comparisons),
            "chart": render_study_chart(summary),
            "report": render_study_report(summary),
        }
        for key, content in artifacts.items():
            (staging / STUDY_FILES[key]).write_text(content, encoding="utf-8", newline="\n")
        if destination.exists() or destination.is_symlink():
            raise FileExistsError(f"study output was created during execution: {destination}")
        staging.rename(destination)
    return summary
