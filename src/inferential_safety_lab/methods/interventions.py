"""Deterministic preprocessing methods with exact intervention accounting."""

from __future__ import annotations

import math

import numpy as np

from inferential_safety_lab.domain.datasets import ObservedData
from inferential_safety_lab.domain.failures import FailureCode
from inferential_safety_lab.domain.results import PreprocessOutcome


def _outcome(
    data: ObservedData | None,
    *,
    valid: bool,
    failure: FailureCode = FailureCode.NONE,
    retained: int,
    filled: int = 0,
    changed: int = 0,
    deleted: int = 0,
    warnings: tuple[str, ...] = (),
) -> PreprocessOutcome:
    return PreprocessOutcome(data, valid, failure, retained, filled, changed, deleted, warnings)


def no_repair(data: ObservedData) -> PreprocessOutcome:
    return _outcome(data, valid=True, retained=data.n)


def median_imputation(data: ObservedData) -> PreprocessOutcome:
    missing = np.isnan(data.observed_z)
    if not missing.any():
        return _outcome(data, valid=True, retained=data.n)
    observed = data.observed_z[~missing]
    if not observed.size:
        return _outcome(
            None,
            valid=False,
            failure=FailureCode.NO_OBSERVED_VALUES_FOR_IMPUTATION,
            retained=data.n,
        )
    filled = data.observed_z.copy()
    filled[missing] = float(np.median(observed))
    count = int(missing.sum())
    return _outcome(data.with_z(filled), valid=True, retained=data.n, filled=count)


def regression_imputation(data: ObservedData) -> PreprocessOutcome:
    missing = np.isnan(data.observed_z)
    if not missing.any():
        return _outcome(data, valid=True, retained=data.n)
    observed = ~missing
    if not observed.any():
        return _outcome(
            None,
            valid=False,
            failure=FailureCode.NO_OBSERVED_VALUES_FOR_IMPUTATION,
            retained=data.n,
        )
    t, y = data.treatment.astype(np.float64), data.outcome
    design = np.column_stack(
        (np.ones(int(observed.sum())), t[observed], y[observed], t[observed] * y[observed])
    )
    if design.shape[0] < 4 or np.linalg.matrix_rank(design) < 4:
        return _outcome(
            None,
            valid=False,
            failure=FailureCode.IMPUTATION_RANK_FAILURE,
            retained=data.n,
        )
    coefficients, _, rank, _ = np.linalg.lstsq(design, data.observed_z[observed], rcond=None)
    if rank < 4 or not np.isfinite(coefficients).all():
        return _outcome(
            None,
            valid=False,
            failure=FailureCode.IMPUTATION_RANK_FAILURE,
            retained=data.n,
        )
    missing_design = np.column_stack(
        (np.ones(int(missing.sum())), t[missing], y[missing], t[missing] * y[missing])
    )
    predictions = missing_design @ coefficients
    if not np.isfinite(predictions).all():
        return _outcome(
            None,
            valid=False,
            failure=FailureCode.NONFINITE_ESTIMATE,
            retained=data.n,
        )
    filled = data.observed_z.copy()
    filled[missing] = predictions
    count = int(missing.sum())
    return _outcome(data.with_z(filled), valid=True, retained=data.n, filled=count)


def winsorize(data: ObservedData, limits: tuple[float, float]) -> PreprocessOutcome:
    lower, upper = limits
    clipped = np.clip(data.observed_z, lower, upper)
    changed = int(np.sum(np.isfinite(data.observed_z) & (clipped != data.observed_z)))
    return _outcome(data.with_z(clipped), valid=True, retained=data.n, changed=changed)


def guarded_delete(data: ObservedData, *, contamination: bool) -> PreprocessOutcome:
    if contamination:
        keep = np.isfinite(data.observed_z) & (np.abs(data.observed_z) <= 3.0)
        minimum_rows = math.ceil(0.75 * data.n)
        minimum_arm = math.ceil(0.15 * data.n)
    else:
        keep = np.isfinite(data.observed_z)
        minimum_rows = math.ceil(0.43 * data.n)
        minimum_arm = math.ceil(0.12 * data.n)
    retained = int(keep.sum())
    deleted = data.n - retained
    if retained < minimum_rows:
        return _outcome(
            None,
            valid=False,
            failure=FailureCode.INSUFFICIENT_ROWS,
            retained=retained,
            deleted=deleted,
        )
    arm_counts = np.bincount(data.treatment[keep], minlength=2)
    if int(arm_counts.min()) < minimum_arm:
        return _outcome(
            None,
            valid=False,
            failure=FailureCode.TREATMENT_ARM_SUPPORT,
            retained=retained,
            deleted=deleted,
        )
    return _outcome(data.subset(keep), valid=True, retained=retained, deleted=deleted)


def preprocess(
    preprocessing_id: str,
    data: ObservedData,
    winsorization_limits: tuple[float, float],
) -> PreprocessOutcome:
    if preprocessing_id in ("complete_case", "no_repair", "evaluator_only_clean_data"):
        return no_repair(data)
    if preprocessing_id == "median_single_imputation":
        return median_imputation(data)
    if preprocessing_id == "deterministic_regression_single_imputation":
        return regression_imputation(data)
    if preprocessing_id == "fixed_limit_winsorization":
        return winsorize(data, winsorization_limits)
    if preprocessing_id == "guarded_row_deletion_missing":
        return guarded_delete(data, contamination=False)
    if preprocessing_id == "guarded_row_deletion_contamination":
        return guarded_delete(data, contamination=True)
    raise ValueError(f"unknown preprocessing_id: {preprocessing_id}")
