from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import replace

import pytest

from inferential_safety_lab.core.configuration import ScenarioId
from inferential_safety_lab.domain.failures import FailureCode
from inferential_safety_lab.domain.results import MethodResult
from inferential_safety_lab.metrics.availability import wilson_interval
from inferential_safety_lab.metrics.repeated_sampling import summarize
from inferential_safety_lab.reporting.charts import architecture_svg, grouped_bar_svg
from inferential_safety_lab.reporting.safety_card import render_safety_card
from inferential_safety_lab.services.presets import get_preset
from inferential_safety_lab.services.run_lab import run_lab


def result(**changes: object) -> MethodResult:
    base = MethodResult(
        "method",
        "prep",
        "estimator",
        1,
        True,
        FailureCode.NONE,
        True,
        0.25,
        True,
        True,
        None,
        0.0,
        0.5,
        80,
        0.8,
        10,
        1.0,
        2,
        0.025,
        20,
        0.2,
        0.001,
        (),
        {"engine": "test"},
    )
    return replace(base, **changes)


def test_wilson_interval_known_value_and_empty_denominator() -> None:
    low, high = wilson_interval(5, 10)
    assert low == pytest.approx(0.2366, abs=1e-4)
    assert high == pytest.approx(0.7634, abs=1e-4)
    assert wilson_interval(0, 0) == (None, None)
    with pytest.raises(ValueError):
        wilson_interval(2, 1)


def test_failure_aware_metrics_keep_every_denominator() -> None:
    values = [
        result(point_estimate=0.35, interval_lower=0.1, interval_upper=0.6),
        result(point_estimate=0.05, interval_lower=0.3, interval_upper=0.7),
        result(
            fit_valid=False,
            fit_failure_code=FailureCode.INSUFFICIENT_ROWS,
            point_estimate_available=False,
            point_estimate=None,
            interval_computed=False,
            interval_lower=None,
            interval_upper=None,
            warnings=("low support",),
        ),
        result(
            interval_scientifically_applicable=False,
            interval_computed=False,
            interval_lower=None,
            interval_upper=None,
        ),
    ]
    metrics = summarize(values, 0.25)
    assert metrics["attempted_runs"] == 4
    assert metrics["point_estimate_available_runs"] == 3
    assert metrics["interval_applicable_attempts"] == 3
    assert metrics["interval_available_runs"] == 2
    assert metrics["conditional_coverage_numerator"] == 1
    assert metrics["conditional_coverage_denominator"] == 2
    assert metrics["conditional_coverage"] == 0.5
    assert metrics["valid_and_cover_rate"] == 0.25
    assert metrics["failure_code_counts"] == {"INSUFFICIENT_ROWS": 1}
    assert metrics["warning_counts"] == {"low support": 1}
    assert metrics["mean_explicit_deletion_fraction"] == pytest.approx(0.2)


def test_accessible_svg_charts_are_self_contained() -> None:
    rows = [{"display_name": "A", "x": 0.5, "y": 0.75}]
    chart = grouped_bar_svg(
        rows,
        title="Coverage",
        description="Coverage beside availability.",
        first_key="x",
        first_label="Coverage",
        second_key="y",
        second_label="Availability",
        percentage=True,
    )
    root = ET.fromstring(chart)
    assert root.attrib["role"] == "img"
    assert "<title" in chart and "<desc" in chart
    assert "http://" not in chart.replace("http://www.w3.org/2000/svg", "")
    assert "<script" not in chart
    assert ET.fromstring(architecture_svg()).attrib["role"] == "img"


def test_safety_card_has_required_content_and_no_external_assets() -> None:
    run = run_lab(get_preset(ScenarioId.MCAR_SMALL_EFFECTIVE_SAMPLE))
    card = render_safety_card(run.aggregate)
    for text in (
        "Inferential Safety Card",
        "Known average effect",
        "Conditional coverage",
        "Interval availability",
        "Valid-and-cover",
        run.replay_hash,
        run.aggregate["replay_command"],
        "No row-level data",
    ):
        assert text in card
    assert "<script" not in card
    assert "https://" not in card
