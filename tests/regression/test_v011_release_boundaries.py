from __future__ import annotations

import hashlib
import json
import math
import subprocess
from pathlib import Path
from statistics import NormalDist
from typing import Any

import numpy as np

from inferential_safety_lab.core.configuration import ScenarioId
from inferential_safety_lab.core.corruption import corrupt
from inferential_safety_lab.core.dgp import generate_truth
from inferential_safety_lab.core.scientific_reference import assert_scientific_reference
from inferential_safety_lab.core.seeds import rng_for
from inferential_safety_lab.methods.contracts import method_panel
from inferential_safety_lab.methods.interventions import guarded_delete
from inferential_safety_lab.methods.ols_hc3 import design_matrix, fit_ols_hc3
from inferential_safety_lab.reporting.charts import (
    completion_chart_spec,
    completion_rows,
    coverage_availability_rows,
    coverage_availability_svg,
    estimation_error_chart_spec,
    estimation_error_rows,
    paired_percentage_chart_spec,
)
from inferential_safety_lab.reporting.public import (
    DETERMINISTIC_IMPUTATION_REASON,
    GUARD_FAILURE_LABEL,
    GUARDED_CONDITIONAL_WARNING,
    SEVERE_STRESS_EXPLANATION,
    SEVERE_STRESS_LABEL,
    WHY_AVAILABILITY_DIFFERS,
    interval_display,
    public_failure_label,
)
from inferential_safety_lab.reporting.safety_card import render_safety_card
from inferential_safety_lab.services.presets import get_preset
from inferential_safety_lab.services.run_lab import run_lab

ROOT = Path(__file__).parents[2]
WINDOWS_REFERENCE_NUMERIC_LEAF_COUNT = 184
WINDOWS_REFERENCE_NUMERIC_FINGERPRINT = (
    "ab232be3ea0d25ceb4e1459be82ac34760237d565df875aea89250a869a905aa"
)


def _independent_hc3(
    outcome: np.ndarray[Any, Any], design: np.ndarray[Any, Any], confidence: float
) -> tuple[float, np.ndarray[Any, Any], float, float]:
    cross_product = design.T @ design
    inverse = np.linalg.solve(cross_product, np.eye(design.shape[1]))
    coefficients = inverse @ design.T @ outcome
    residual = outcome - design @ coefficients
    leverage = np.einsum("ij,jk,ik->i", design, inverse, design)
    adjusted = np.square(residual / (1.0 - leverage))
    covariance = inverse @ (design.T @ (design * adjusted[:, None])) @ inverse
    half_width = NormalDist().inv_cdf((1.0 + confidence) / 2.0) * math.sqrt(covariance[1, 1])
    return (
        float(coefficients[1]),
        covariance,
        float(coefficients[1] - half_width),
        float(coefficients[1] + half_width),
    )


def _numeric_leaves(value: object, prefix: str = "") -> dict[str, int | float]:
    leaves: dict[str, int | float] = {}
    if isinstance(value, dict):
        for key, child in value.items():
            leaves.update(_numeric_leaves(child, f"{prefix}/{key}"))
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            leaves.update(_numeric_leaves(child, f"{prefix}/{index}"))
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        leaves[prefix] = value
    return leaves


def _numeric_fingerprint(aggregate: dict[str, Any]) -> tuple[int, str]:
    leaves = _numeric_leaves(aggregate)
    serialized = json.dumps(leaves, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return len(leaves), hashlib.sha256(serialized).hexdigest()


def test_complete_case_and_reporting_guard_are_identical_when_guard_passes() -> None:
    config = get_preset(ScenarioId.MCAR_SMALL_EFFECTIVE_SAMPLE)
    passed = 0
    withheld = 0
    for repetition in range(config.repetitions):
        truth = generate_truth(
            n=config.sample_size,
            tau=config.tau,
            rng=rng_for(config.master_seed, "dgp", config.scenario_id.value, repetition),
        )
        observed, _ = corrupt(
            truth,
            config,
            rng_for(config.master_seed, "corruption", config.scenario_id.value, repetition),
        )
        complete_mask = np.isfinite(observed.observed_z)
        complete_rows = observed.row_id[complete_mask]
        complete_y, complete_design = design_matrix(observed)
        guarded = guarded_delete(observed, contamination=False)
        if not guarded.valid:
            withheld += 1
            continue

        passed += 1
        guarded_data = guarded.data
        assert guarded_data is not None
        guarded_y, guarded_design = design_matrix(guarded_data)
        np.testing.assert_array_equal(complete_rows, guarded_data.row_id)
        np.testing.assert_array_equal(complete_design, guarded_design)
        np.testing.assert_array_equal(complete_y, guarded_y)

        complete_details = _independent_hc3(complete_y, complete_design, config.confidence_level)
        guarded_details = _independent_hc3(guarded_y, guarded_design, config.confidence_level)
        for complete_value, guarded_value in zip(complete_details, guarded_details, strict=True):
            np.testing.assert_allclose(complete_value, guarded_value, rtol=0.0, atol=1e-12)

        complete_fit = fit_ols_hc3(
            observed, confidence_level=config.confidence_level, compute_interval=True
        )
        guarded_fit = fit_ols_hc3(
            guarded_data, confidence_level=config.confidence_level, compute_interval=True
        )
        assert complete_fit == guarded_fit

    assert (passed, withheld) == (43, 117)


def test_checked_in_windows_reference_retains_historical_numeric_fingerprint() -> None:
    reference = json.loads((ROOT / "artifacts/demo/aggregate.canonical.json").read_text())
    assert _numeric_fingerprint(reference) == (
        WINDOWS_REFERENCE_NUMERIC_LEAF_COUNT,
        WINDOWS_REFERENCE_NUMERIC_FINGERPRINT,
    )


def test_frozen_v010_scientific_reference_is_portably_equivalent() -> None:
    current = run_lab(get_preset(ScenarioId.MCAR_SMALL_EFFECTIVE_SAMPLE)).aggregate
    reference = json.loads((ROOT / "artifacts/demo/aggregate.canonical.json").read_text())
    assert_scientific_reference(reference, current)

    tagged = subprocess.run(
        ["git", "show", "v0.1.0:artifacts/demo/aggregate.canonical.json"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if tagged.returncode == 0:
        tagged_reference = json.loads(tagged.stdout)
        assert _numeric_fingerprint(tagged_reference) == (
            WINDOWS_REFERENCE_NUMERIC_LEAF_COUNT,
            WINDOWS_REFERENCE_NUMERIC_FINGERPRINT,
        )
        assert_scientific_reference(reference, tagged_reference)


def test_guard_failure_is_a_reporting_contract_state_with_a_public_label() -> None:
    contract = next(
        item
        for item in method_panel(ScenarioId.MCAR_SMALL_EFFECTIVE_SAMPLE)
        if item.method_id == "guarded_deletion_ols_hc3"
    )
    assert contract.display_name == ("Complete-case OLS with minimum-evidence reporting guard")
    assert contract.preprocessing_id == "guarded_row_deletion_missing"
    assert contract.estimator_id == "ols_hc3"
    assert public_failure_label("INSUFFICIENT_ROWS") == GUARD_FAILURE_LABEL


def test_interval_display_distinguishes_all_three_states() -> None:
    metrics = run_lab(get_preset(ScenarioId.MCAR_SMALL_EFFECTIVE_SAMPLE)).aggregate[
        "method_metrics"
    ]
    complete = next(row for row in metrics if row["method_id"] == "complete_case_ols_hc3")
    inapplicable = next(row for row in metrics if row["method_id"] == "median_imputation_ols")
    unavailable = dict(complete)
    unavailable.update(
        interval_available_runs=0,
        interval_availability=0.0,
        conditional_coverage=None,
        conditional_coverage_numerator=0,
        conditional_coverage_denominator=0,
        valid_and_cover_rate=0.0,
        valid_and_cover_numerator=0,
    )

    assert interval_display(complete)["status"] == "Applicable and available"
    assert interval_display(unavailable) == {
        "status": "Applicable but unavailable",
        "conditional_coverage": "Not available · 0/0",
        "interval_availability": "0.0% · 0/160",
        "valid_and_cover": "0.0% · 0/160",
    }
    assert interval_display(inapplicable) == {
        "status": "Not applicable",
        "conditional_coverage": "N/A",
        "interval_availability": "N/A",
        "valid_and_cover": "N/A",
    }


def test_public_chart_semantics_exclude_inapplicable_and_never_stack() -> None:
    metrics = run_lab(get_preset(ScenarioId.MCAR_SMALL_EFFECTIVE_SAMPLE)).aggregate[
        "method_metrics"
    ]
    method_order = [str(row["display_name"]) for row in metrics]
    coverage = coverage_availability_rows(metrics)
    assert {row["method"] for row in coverage} == {
        "Complete-case OLS with HC3",
        "Complete-case OLS with minimum-evidence reporting guard",
    }
    assert len(coverage) == 4
    assert len(estimation_error_rows(metrics)) == 8
    assert len(completion_rows(metrics)) == 8
    for spec in (
        paired_percentage_chart_spec(method_order),
        estimation_error_chart_spec(method_order),
        completion_chart_spec(method_order, 160),
    ):
        assert spec["encoding"]["x"]["stack"] is None
    svg = coverage_availability_svg(metrics)
    assert "Median single imputation" not in svg
    assert "0%" in svg and "100%" in svg
    assert "153/160" in svg and "41/43" in svg
    completion = completion_rows(metrics)
    assert {
        (row["method"], row["status"], row["count"], row["reason"])
        for row in completion
        if row["method"] == "Complete-case OLS with minimum-evidence reporting guard"
    } == {
        (
            "Complete-case OLS with minimum-evidence reporting guard",
            "Reported",
            43,
            "Point estimate reported",
        ),
        (
            "Complete-case OLS with minimum-evidence reporting guard",
            "Withheld or failed",
            117,
            GUARD_FAILURE_LABEL,
        ),
    }


def test_release_surfaces_preserve_scientific_boundaries_without_raw_public_labels() -> None:
    run = run_lab(get_preset(ScenarioId.MCAR_SMALL_EFFECTIVE_SAMPLE))
    card = render_safety_card(run.aggregate)
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    app_source = (ROOT / "src/inferential_safety_lab/ui/app.py").read_text(encoding="utf-8")

    for text in (
        WHY_AVAILABILITY_DIFFERS,
        GUARDED_CONDITIONAL_WARNING,
        SEVERE_STRESS_LABEL,
        SEVERE_STRESS_EXPLANATION,
    ):
        assert text in card
    for plain_language_boundary in (
        "intentionally severe 60% missingness rate",
        "minimum-evidence rule withheld 117 results",
        "conditional on the datasets where it reported",
        "accuracy and availability",
    ):
        assert plain_language_boundary in readme.replace("\n", " ")
    assert "WHY_AVAILABILITY_DIFFERS" in app_source
    assert "GUARDED_CONDITIONAL_WARNING" in app_source
    assert "SEVERE_STRESS_LABEL" not in app_source

    assert DETERMINISTIC_IMPUTATION_REASON in card
    assert "Interval status: Not applicable" not in card
    assert ">Not applicable<" in card
    for raw_label in (
        "INSUFFICIENT_ROWS",
        "conditional_coverage",
        "interval_availability",
        "valid_and_cover_rate",
        "guarded_deletion_ols_hc3",
    ):
        assert raw_label not in card
