"""Known-truth data-generating process."""

from __future__ import annotations

import numpy as np

from inferential_safety_lab.domain.datasets import EvaluatorTruth


def expit(value: np.ndarray) -> np.ndarray:
    positive = value >= 0
    result = np.empty_like(value, dtype=np.float64)
    result[positive] = 1.0 / (1.0 + np.exp(-value[positive]))
    exp_value = np.exp(value[~positive])
    result[~positive] = exp_value / (1.0 + exp_value)
    return result


def conditional_effect(z: np.ndarray, tau: float) -> np.ndarray:
    return np.asarray(tau + 0.5 * np.asarray(z, dtype=np.float64), dtype=np.float64)


def original_target(tau: float) -> float:
    return float(tau)


def generate_truth(*, n: int, tau: float, rng: np.random.Generator) -> EvaluatorTruth:
    """Generate Z, T, epsilon, potential outcomes, and observed Y exactly once."""

    if n <= 4:
        raise ValueError("n must exceed the four-parameter design width")
    row_id = np.arange(n, dtype=np.int64)
    z = rng.standard_normal(n, dtype=np.float64)
    propensity = expit(-0.2 + 0.6 * z)
    treatment = (rng.random(n) < propensity).astype(np.int8)
    epsilon = rng.normal(0.0, 1.0, n).astype(np.float64)
    y0 = 1.0 + 0.8 * z + epsilon
    y1 = 1.0 + tau + 1.3 * z + epsilon
    outcome = np.where(treatment == 1, y1, y0)
    return EvaluatorTruth(
        row_id,
        z,
        treatment,
        epsilon,
        y0,
        y1,
        outcome,
        propensity,
        float(tau),
        original_target(tau),
    )
