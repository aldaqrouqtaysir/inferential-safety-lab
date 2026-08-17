"""Portable Huber M-estimator point fit using deterministic IRLS."""

from __future__ import annotations

import numpy as np

from inferential_safety_lab.domain.datasets import ObservedData
from inferential_safety_lab.domain.failures import FailureCode
from inferential_safety_lab.domain.results import FitOutcome

from .ols_hc3 import design_matrix


def fit_huber(
    data: ObservedData,
    *,
    tuning: float = 1.345,
    tolerance: float = 1.0e-9,
    max_iterations: int = 100,
) -> FitOutcome:
    y, design = design_matrix(data)
    n_obs, width = design.shape
    if n_obs <= width:
        return FitOutcome(False, FailureCode.INSUFFICIENT_ROWS, None, None, None, n_obs)
    if np.linalg.matrix_rank(design) != width:
        return FitOutcome(False, FailureCode.RANK_DEFICIENT_DESIGN, None, None, None, n_obs)
    coefficients, _, _, _ = np.linalg.lstsq(design, y, rcond=None)
    for _ in range(max_iterations):
        residual = y - design @ coefficients
        center = float(np.median(residual))
        scale = float(np.median(np.abs(residual - center)) / 0.6744897501960817)
        if not np.isfinite(scale) or scale <= np.sqrt(np.finfo(np.float64).eps):
            return FitOutcome(False, FailureCode.HUBER_SCALE_FAILURE, None, None, None, n_obs)
        standardized = residual / scale
        weights = np.ones_like(standardized)
        outside = np.abs(standardized) > tuning
        weights[outside] = tuning / np.abs(standardized[outside])
        root_weight = np.sqrt(weights)
        updated, _, rank, _ = np.linalg.lstsq(
            design * root_weight[:, None], y * root_weight, rcond=None
        )
        if rank < width or not np.isfinite(updated).all():
            return FitOutcome(False, FailureCode.NONFINITE_ESTIMATE, None, None, None, n_obs)
        if float(np.max(np.abs(updated - coefficients))) <= tolerance * (
            1.0 + float(np.max(np.abs(coefficients)))
        ):
            return FitOutcome(True, FailureCode.NONE, float(updated[1]), None, None, n_obs)
        coefficients = updated
    return FitOutcome(False, FailureCode.HUBER_NONCONVERGENCE, None, None, None, n_obs)
