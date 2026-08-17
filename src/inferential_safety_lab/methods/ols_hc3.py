"""Portable NumPy OLS for Y ~ 1 + T + Z + T:Z with exact HC3 covariance."""

from __future__ import annotations

import math
from statistics import NormalDist

import numpy as np

from inferential_safety_lab.domain.datasets import ObservedData
from inferential_safety_lab.domain.failures import FailureCode
from inferential_safety_lab.domain.results import FitOutcome


def design_matrix(data: ObservedData) -> tuple[np.ndarray, np.ndarray]:
    mask = np.isfinite(data.outcome) & np.isfinite(data.treatment) & np.isfinite(data.observed_z)
    t = data.treatment[mask].astype(np.float64)
    z = data.observed_z[mask]
    matrix = np.column_stack((np.ones(int(mask.sum())), t, z, t * z))
    return data.outcome[mask], matrix


def fit_ols_hc3(
    data: ObservedData,
    *,
    confidence_level: float,
    compute_interval: bool,
) -> FitOutcome:
    y, design = design_matrix(data)
    n_obs, width = design.shape
    if n_obs <= width:
        return FitOutcome(False, FailureCode.INSUFFICIENT_ROWS, None, None, None, n_obs)
    if np.linalg.matrix_rank(design) != width:
        return FitOutcome(False, FailureCode.RANK_DEFICIENT_DESIGN, None, None, None, n_obs)
    try:
        inverse = np.linalg.inv(design.T @ design)
    except np.linalg.LinAlgError:
        return FitOutcome(False, FailureCode.SINGULAR_CROSSPRODUCT, None, None, None, n_obs)
    coefficients = inverse @ design.T @ y
    residual = y - design @ coefficients
    leverage = np.einsum("ij,jk,ik->i", design, inverse, design)
    denominator = 1.0 - leverage
    if np.any(denominator <= 64.0 * np.finfo(np.float64).eps):
        return FitOutcome(
            False, FailureCode.HC3_UNDEFINED_PERFECT_LEVERAGE, None, None, None, n_obs
        )
    adjusted = np.square(residual / denominator)
    meat = design.T @ (design * adjusted[:, None])
    covariance = inverse @ meat @ inverse
    estimate = float(coefficients[1])
    variance = float(covariance[1, 1])
    if not math.isfinite(estimate) or not math.isfinite(variance) or variance < 0.0:
        return FitOutcome(False, FailureCode.NONFINITE_ESTIMATE, None, None, None, n_obs)
    if not compute_interval:
        return FitOutcome(True, FailureCode.NONE, estimate, None, None, n_obs)
    critical = NormalDist().inv_cdf((1.0 + confidence_level) / 2.0)
    half_width = critical * math.sqrt(max(variance, 0.0))
    return FitOutcome(
        True,
        FailureCode.NONE,
        estimate,
        estimate - half_width,
        estimate + half_width,
        n_obs,
    )
