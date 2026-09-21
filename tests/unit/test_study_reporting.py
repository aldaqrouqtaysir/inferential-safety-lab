from __future__ import annotations

import copy
import xml.etree.ElementTree as ET
from typing import Any

from inferential_safety_lab.core.configuration import ScenarioId
from inferential_safety_lab.reporting.study import render_study_chart, render_study_report
from inferential_safety_lab.services.presets import get_preset


def study_summary() -> dict[str, Any]:
    config = get_preset(ScenarioId.MCAR_SMALL_EFFECTIVE_SAMPLE).as_dict()
    rows = []
    for run_id, seed, available, covered in (("run-001", 11, 80, 76), ("run-002", 22, 40, 38)):
        row = {
            **config,
            "run_id": run_id,
            "master_seed": seed,
            "repetitions": 80,
            "method_id": "complete_case_ols_hc3",
            "display_name": "Complete-case OLS",
            "attempted_runs": 80,
            "point_estimate_available_runs": available,
            "bias": 0.01,
            "bias_mcse": 0.02,
            "rmse": 0.2,
            "interval_scientifically_applicable": True,
            "interval_unavailability_reason": None,
            "interval_applicable_attempts": 80,
            "interval_available_runs": available,
            "interval_availability": available / 80,
            "conditional_coverage": covered / available,
            "conditional_coverage_numerator": covered,
            "conditional_coverage_denominator": available,
            "valid_and_cover_rate": covered / 80,
            "valid_and_cover_numerator": covered,
            "valid_and_cover_denominator": 80,
            "interval_availability_wilson": {"lower": 0.8, "upper": 1.0},
            "conditional_coverage_wilson": {"lower": 0.85, "upper": 0.99},
            "failure_code_counts": {} if available == 80 else {"INSUFFICIENT_ROWS": 40},
        }
        rows.append(row)
    return {
        "schema_version": "inferential_safety_lab.study-results.v1",
        "study_id": "a" * 64,
        "configuration": {
            "schema_version": "inferential_safety_lab.study.v1",
            "base_config": config,
            "grid": {"master_seed": [11, 22]},
        },
        "runs": [
            {
                "run_id": row["run_id"],
                "configuration": {**config, "master_seed": row["master_seed"], "repetitions": 80},
                "replay_hash": str(index) * 64,
                "aggregate_sha256": "f" * 64,
                "artifact_directory": f"runs/{row['run_id']}",
            }
            for index, row in enumerate(rows)
        ],
        "comparisons": rows,
    }


def test_study_report_keeps_each_cell_and_its_denominators() -> None:
    summary = study_summary()
    original = copy.deepcopy(summary)
    report = render_study_report(summary)
    assert "95.0% · 76/80" in report
    assert "95.0% · 38/40" in report
    assert "50.0% · 40/80" in report
    assert "47.5% · 38/80" in report
    assert "INSUFFICIENT_ROWS): 40" in report
    assert "Bias Monte Carlo SE" in report
    assert "conditional on runs that passed the guard" in report
    assert "runs/run-001/run-config.json" in report
    assert "runs/run-002/aggregate.canonical.json" in report
    assert "No pooling across cells" in report
    assert summary == original
    assert report == render_study_report(summary)


def test_study_chart_has_accessible_metadata_and_fixed_percent_scale() -> None:
    chart = render_study_chart(study_summary())
    root = ET.fromstring(chart)
    assert root.attrib["role"] == "img"
    assert root.attrib["aria-labelledby"] == "study-chart-title study-chart-description"
    description = root.find("{http://www.w3.org/2000/svg}desc")
    assert description is not None and "76/80" in str(description.text)
    for label in ("0%", "25%", "50%", "75%", "100%", "Seed 11", "Seed 22", "38/40"):
        assert label in chart
    assert '<rect x="420" y=' in chart
    assert 'width="240.000"' in chart  # 40/80 availability on a 480-unit axis.
    assert chart == render_study_chart(study_summary())


def test_study_distinguishes_inapplicable_from_zero_available_intervals() -> None:
    summary = study_summary()
    first, second = summary["comparisons"]
    first.update(
        {
            "interval_scientifically_applicable": False,
            "interval_applicable_attempts": 0,
            "interval_unavailability_reason": "Uncertainty not propagated.",
            "interval_available_runs": 0,
            "interval_availability": 0.0,
            "conditional_coverage": None,
            "conditional_coverage_numerator": 0,
            "conditional_coverage_denominator": 0,
        }
    )
    second.update(
        {
            "interval_available_runs": 0,
            "interval_availability": 0.0,
            "conditional_coverage": None,
            "conditional_coverage_numerator": 0,
            "conditional_coverage_denominator": 0,
            "conditional_coverage_wilson": {"lower": None, "upper": None},
        }
    )
    chart = render_study_chart(summary)
    report = render_study_report(summary)
    assert "N/A - scientifically inapplicable" in chart
    assert "Not available | 0/0" in chart
    assert "0.0% | 0/80" in chart
    assert "Applicable but unavailable" in report
    assert "Uncertainty not propagated." in report
    assert "<td>N/A</td>" in report


def test_study_report_escapes_labels_and_keeps_assets_offline() -> None:
    summary = study_summary()
    summary["comparisons"][0].update(
        {
            "method_id": "custom",
            "display_name": '<script>alert("label")</script>',
        }
    )
    summary["runs"][0]["artifact_directory"] = "https://example.invalid/redirect"
    report = render_study_report(summary)
    chart = render_study_chart(summary)
    ET.fromstring(chart)
    assert "&lt;script&gt;" in report
    assert "<script" not in report
    assert "https://" not in report
    assert "link unavailable" in report
    assert "http://" not in report.replace("http://www.w3.org/2000/svg", "")
