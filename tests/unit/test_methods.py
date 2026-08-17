from __future__ import annotations

import numpy as np
import pytest

from inferential_safety_lab.domain.datasets import ObservedData
from inferential_safety_lab.domain.failures import FailureCode
from inferential_safety_lab.methods.huber import fit_huber
from inferential_safety_lab.methods.interventions import (
    guarded_delete,
    median_imputation,
    regression_imputation,
    winsorize,
)
from inferential_safety_lab.methods.ols_hc3 import design_matrix, fit_ols_hc3


def observed(n: int = 150, *, missing_every: int | None = None) -> ObservedData:
    rng = np.random.Generator(np.random.PCG64(42))
    z = rng.normal(size=n)
    treatment = (rng.random(n) < 0.5).astype(np.int8)
    outcome = 1.0 + 0.25 * treatment + 0.8 * z + 0.5 * treatment * z + rng.normal(size=n)
    if missing_every is not None:
        z[::missing_every] = np.nan
    return ObservedData(np.arange(n), treatment, outcome, z)


def test_ols_hc3_matches_independent_matrix_calculation() -> None:
    data = observed()
    result = fit_ols_hc3(data, confidence_level=0.95, compute_interval=True)
    y, matrix = design_matrix(data)
    beta = np.linalg.solve(matrix.T @ matrix, matrix.T @ y)
    inverse = np.linalg.solve(matrix.T @ matrix, np.eye(matrix.shape[1]))
    residual = y - matrix @ beta
    leverage = np.diag(matrix @ inverse @ matrix.T)
    meat = sum(
        np.outer(row, row) * (error / (1.0 - hat)) ** 2
        for row, error, hat in zip(matrix, residual, leverage, strict=True)
    )
    covariance = inverse @ meat @ inverse
    assert result.valid
    assert result.point_estimate == pytest.approx(beta[1], abs=1e-12)
    assert result.interval_lower is not None and result.interval_upper is not None
    assert covariance[1, 1] > 0.0


def test_ols_distinguishes_point_and_interval_availability() -> None:
    result = fit_ols_hc3(observed(), confidence_level=0.95, compute_interval=False)
    assert result.valid and result.point_estimate is not None
    assert result.interval_lower is None and result.interval_upper is None


def test_ols_types_rank_and_insufficient_row_failures() -> None:
    data = observed(6)
    rank_deficient = ObservedData(
        data.row_id,
        np.zeros(data.n, dtype=np.int8),
        data.outcome,
        data.observed_z,
    )
    assert (
        fit_ols_hc3(rank_deficient, confidence_level=0.95, compute_interval=True).failure_code
        is FailureCode.RANK_DEFICIENT_DESIGN
    )
    mostly_missing = observed(10)
    z = mostly_missing.observed_z.copy()
    z[4:] = np.nan
    sparse = mostly_missing.with_z(z)
    assert (
        fit_ols_hc3(sparse, confidence_level=0.95, compute_interval=True).failure_code
        is FailureCode.INSUFFICIENT_ROWS
    )


def test_median_imputation_fills_only_missing_cells() -> None:
    data = observed(missing_every=5)
    result = median_imputation(data)
    assert result.valid and result.data is not None
    assert result.filled_missing_count == 30
    assert not np.isnan(result.data.observed_z).any()
    assert np.array_equal(result.data.observed_z[1:5], data.observed_z[1:5])


def test_median_imputation_types_all_missing_failure() -> None:
    data = observed().with_z(np.full(150, np.nan))
    result = median_imputation(data)
    assert not result.valid
    assert result.failure_code is FailureCode.NO_OBSERVED_VALUES_FOR_IMPUTATION


def test_regression_imputation_is_deterministic() -> None:
    data = observed(missing_every=7)
    first = regression_imputation(data)
    second = regression_imputation(data)
    assert first.valid and second.valid
    assert first.filled_missing_count == second.filled_missing_count
    assert np.array_equal(first.data.observed_z, second.data.observed_z)


def test_regression_imputation_types_rank_failure() -> None:
    data = observed(missing_every=5)
    rank_deficient = ObservedData(
        data.row_id,
        np.zeros(data.n, dtype=np.int8),
        data.outcome,
        data.observed_z,
    )
    assert regression_imputation(rank_deficient).failure_code is FailureCode.IMPUTATION_RANK_FAILURE


def test_winsorization_changes_observed_values_and_preserves_missingness() -> None:
    data = observed(100)
    z = data.observed_z.copy()
    z[:4] = (-9.0, -3.0, 3.0, 10.0)
    z[4] = np.nan
    result = winsorize(data.with_z(z), (-3.0, 3.0))
    assert result.changed_observed_count == 2
    assert result.data.observed_z[0] == -3.0
    assert result.data.observed_z[3] == 3.0
    assert np.isnan(result.data.observed_z[4])


def test_guarded_deletion_reports_explicit_deletion_and_contract_failure() -> None:
    data = observed(missing_every=4)
    success = guarded_delete(data, contamination=False)
    assert success.valid
    assert success.explicit_deletion_count == 38
    z = data.observed_z.copy()
    z[:100] = np.nan
    failure = guarded_delete(data.with_z(z), contamination=False)
    assert failure.failure_code is FailureCode.INSUFFICIENT_ROWS
    assert failure.explicit_deletion_count >= 100


def test_guarded_deletion_types_treatment_arm_support() -> None:
    data = observed()
    z = data.observed_z.copy()
    z[data.treatment == 1] = np.nan
    result = guarded_delete(data.with_z(z), contamination=False)
    assert result.failure_code is FailureCode.TREATMENT_ARM_SUPPORT


def test_huber_point_estimate_is_stable_under_one_large_outcome_outlier() -> None:
    data = observed()
    baseline = fit_huber(data)
    outcome = data.outcome.copy()
    outcome[0] += 1000.0
    contaminated = ObservedData(data.row_id, data.treatment, outcome, data.observed_z)
    robust = fit_huber(contaminated)
    assert baseline.valid and robust.valid
    assert baseline.point_estimate is not None and robust.point_estimate is not None
    assert abs(robust.point_estimate - baseline.point_estimate) < 0.25
    assert robust.interval_lower is None


def test_huber_scale_failure_is_typed() -> None:
    data = observed()
    exact = ObservedData(
        data.row_id,
        data.treatment,
        1.0
        + 0.25 * data.treatment
        + 0.8 * data.observed_z
        + 0.5 * data.treatment * data.observed_z,
        data.observed_z,
    )
    assert fit_huber(exact).failure_code is FailureCode.HUBER_SCALE_FAILURE
