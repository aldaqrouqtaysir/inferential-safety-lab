"""Failure-aware repeated-sampling aggregation with explicit denominators."""

from __future__ import annotations

import math
from collections import Counter
from statistics import median
from typing import Any

import numpy as np

from inferential_safety_lab.domain.results import MethodResult

from .availability import wilson_interval


def _mean(values: list[float]) -> float | None:
    return float(np.mean(values)) if values else None


def summarize(results: list[MethodResult], known_target: float) -> dict[str, Any]:
    attempted = len(results)
    valid = sum(result.fit_valid for result in results)
    points = [
        float(result.point_estimate) for result in results if result.point_estimate is not None
    ]
    errors = [value - known_target for value in points]
    applicable = sum(result.interval_scientifically_applicable for result in results)
    usable = [
        result
        for result in results
        if result.interval_scientifically_applicable
        and result.interval_computed
        and result.interval_lower is not None
        and result.interval_upper is not None
    ]
    covered = 0
    lengths: list[float] = []
    for result in usable:
        assert result.interval_lower is not None
        assert result.interval_upper is not None
        covered += result.interval_lower <= known_target <= result.interval_upper
        lengths.append(result.interval_upper - result.interval_lower)
    availability_ci = wilson_interval(len(usable), attempted)
    coverage_ci = wilson_interval(covered, len(usable))
    failure_counts = Counter(
        result.fit_failure_code.value for result in results if not result.fit_valid
    )
    warning_counts = Counter(warning for result in results for warning in result.warnings)
    bias = _mean(errors)
    return {
        "attempted_runs": attempted,
        "completed_runs": attempted,
        "valid_fits": valid,
        "valid_fit_rate": valid / attempted if attempted else None,
        "point_estimate_available_runs": len(points),
        "point_estimate_availability": len(points) / attempted if attempted else None,
        "interval_applicable_attempts": applicable,
        "interval_applicability": applicable / attempted if attempted else None,
        "interval_available_runs": len(usable),
        "interval_availability": len(usable) / attempted if attempted else None,
        "interval_availability_wilson": {"lower": availability_ci[0], "upper": availability_ci[1]},
        "bias": bias,
        "bias_mcse": (
            float(np.std(errors, ddof=1) / math.sqrt(len(errors))) if len(errors) > 1 else None
        ),
        "absolute_bias": abs(bias) if bias is not None else None,
        "rmse": float(np.sqrt(np.mean(np.square(errors)))) if errors else None,
        "median_absolute_error": float(median(abs(value) for value in errors)) if errors else None,
        "conditional_coverage": covered / len(usable) if usable else None,
        "conditional_coverage_numerator": covered,
        "conditional_coverage_denominator": len(usable),
        "conditional_coverage_wilson": {"lower": coverage_ci[0], "upper": coverage_ci[1]},
        "valid_and_cover_rate": covered / attempted if attempted else None,
        "valid_and_cover_numerator": covered,
        "valid_and_cover_denominator": attempted,
        "mean_interval_length": _mean(lengths),
        "median_interval_length": float(median(lengths)) if lengths else None,
        "mean_row_retention": _mean([result.retained_row_fraction for result in results]),
        "mean_filled_missing_fraction": _mean(
            [result.filled_missing_fraction for result in results]
        ),
        "mean_changed_observed_fraction": _mean(
            [result.changed_observed_fraction for result in results]
        ),
        "mean_explicit_deletion_fraction": _mean(
            [result.explicit_deletion_fraction for result in results]
        ),
        "failure_code_counts": dict(sorted(failure_counts.items())),
        "warning_counts": dict(sorted(warning_counts.items())),
        "denominator_note": "All availability and valid-and-cover rates use attempted runs.",
    }
