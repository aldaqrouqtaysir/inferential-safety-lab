from __future__ import annotations

import math

import pytest

from inferential_safety_lab.core.scientific_reference import (
    ScientificReferenceMismatch,
    assert_scientific_reference,
)


def _reference() -> dict[str, object]:
    return {
        "scenario_id": "MCAR_SMALL_EFFECTIVE_SAMPLE",
        "method_metrics": [
            {
                "method_id": "complete_case_ols_hc3",
                "attempted_runs": 160,
                "conditional_coverage_denominator": 160,
                "fit_failure_code": "NONE",
                "bias": -0.04796796180381361,
                "interval": None,
            }
        ],
        "reported": True,
    }


def test_scientific_reference_accepts_exact_match() -> None:
    expected = _reference()
    assert_scientific_reference(expected, expected)


def test_scientific_reference_accepts_allowed_low_order_float_difference() -> None:
    expected = _reference()
    actual = _reference()
    actual["method_metrics"][0]["bias"] += 5.0e-14  # type: ignore[index,operator]
    assert_scientific_reference(expected, actual)


def test_scientific_reference_rejects_excessive_float_difference() -> None:
    expected = _reference()
    actual = _reference()
    actual["method_metrics"][0]["bias"] += 2.0e-12  # type: ignore[index,operator]
    with pytest.raises(ScientificReferenceMismatch, match=r"/method_metrics/0/bias"):
        assert_scientific_reference(expected, actual)


def test_scientific_reference_rejects_changed_integer_count() -> None:
    expected = _reference()
    actual = _reference()
    actual["method_metrics"][0]["attempted_runs"] = 159  # type: ignore[index]
    with pytest.raises(ScientificReferenceMismatch, match=r"/method_metrics/0/attempted_runs"):
        assert_scientific_reference(expected, actual)


def test_scientific_reference_rejects_changed_denominator() -> None:
    expected = _reference()
    actual = _reference()
    actual["method_metrics"][0]["conditional_coverage_denominator"] = 159  # type: ignore[index]
    with pytest.raises(
        ScientificReferenceMismatch,
        match=r"/method_metrics/0/conditional_coverage_denominator",
    ):
        assert_scientific_reference(expected, actual)


def test_scientific_reference_rejects_changed_failure_state() -> None:
    expected = _reference()
    actual = _reference()
    actual["method_metrics"][0]["fit_failure_code"] = "SINGULAR_CROSSPRODUCT"  # type: ignore[index]
    with pytest.raises(ScientificReferenceMismatch, match=r"/method_metrics/0/fit_failure_code"):
        assert_scientific_reference(expected, actual)


def test_scientific_reference_rejects_missing_path() -> None:
    expected = _reference()
    actual = _reference()
    del actual["method_metrics"][0]["bias"]  # type: ignore[index]
    with pytest.raises(ScientificReferenceMismatch, match=r"missing=\['bias'\]"):
        assert_scientific_reference(expected, actual)


def test_scientific_reference_rejects_extra_path() -> None:
    expected = _reference()
    actual = _reference()
    actual["method_metrics"][0]["new_metric"] = 1.0  # type: ignore[index]
    with pytest.raises(ScientificReferenceMismatch, match=r"extra=\['new_metric'\]"):
        assert_scientific_reference(expected, actual)


def test_scientific_reference_rejects_null_versus_zero() -> None:
    expected = _reference()
    actual = _reference()
    actual["method_metrics"][0]["interval"] = 0  # type: ignore[index]
    with pytest.raises(ScientificReferenceMismatch, match=r"/method_metrics/0/interval"):
        assert_scientific_reference(expected, actual)


def test_scientific_reference_accepts_signed_zero_as_equivalent() -> None:
    assert_scientific_reference({"value": 0.0}, {"value": -0.0})


def test_scientific_reference_rejects_nan() -> None:
    with pytest.raises(ScientificReferenceMismatch, match="non-finite floats are forbidden"):
        assert_scientific_reference({"value": 1.0}, {"value": math.nan})


def test_scientific_reference_excludes_environment_hash_and_timing_metadata() -> None:
    expected = {
        **_reference(),
        "environment": {"platform": "Windows-AMD64"},
        "replay_hash": "windows-hash",
        "timing": {"wall_seconds": 1.0},
    }
    actual = {
        **_reference(),
        "environment": {"platform": "Linux-x86_64", "numpy": "different-build"},
        "replay_hash": "linux-hash",
        "timing": {"wall_seconds": 9.0},
    }
    assert_scientific_reference(expected, actual)
