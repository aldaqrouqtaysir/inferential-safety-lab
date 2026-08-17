"""Scenario corruption mechanisms with evaluator-only masks."""

from __future__ import annotations

import numpy as np

from inferential_safety_lab.core.configuration import RunConfig, ScenarioId
from inferential_safety_lab.domain.datasets import CorruptionRecord, EvaluatorTruth, ObservedData

from .dgp import expit


def calibrate_mar_intercept(truth: EvaluatorTruth, target_rate: float) -> float:
    """Solve the finite-population mean missingness equation by bisection."""

    if not 0.0 < target_rate < 1.0:
        raise ValueError("target_rate must lie strictly between zero and one")
    linear = 0.5 * truth.treatment + 0.35 * truth.outcome
    lower, upper = -30.0, 30.0
    for _ in range(100):
        midpoint = (lower + upper) / 2.0
        if float(np.mean(expit(midpoint + linear))) < target_rate:
            lower = midpoint
        else:
            upper = midpoint
    return (lower + upper) / 2.0


def corrupt(
    truth: EvaluatorTruth,
    config: RunConfig,
    rng: np.random.Generator,
) -> tuple[ObservedData, CorruptionRecord]:
    """Create observed analysis data while retaining masks only for evaluation."""

    n = truth.n
    missing = np.zeros(n, dtype=np.bool_)
    contaminated = np.zeros(n, dtype=np.bool_)
    observed_z = truth.latent_z.copy()
    parameter = 0.0
    if config.scenario_id is ScenarioId.MCAR_SMALL_EFFECTIVE_SAMPLE:
        missing = rng.random(n) < config.missingness_rate
        observed_z[missing] = np.nan
        parameter = config.missingness_rate
    elif config.scenario_id is ScenarioId.OUTCOME_DEPENDENT_MAR:
        alpha = calibrate_mar_intercept(truth, config.missingness_rate)
        probability = expit(alpha + 0.5 * truth.treatment + 0.35 * truth.outcome)
        missing = rng.random(n) < probability
        observed_z[missing] = np.nan
        parameter = alpha
    else:
        contaminated = rng.random(n) < config.contamination_fraction
        signs = np.where(rng.random(n) < 0.5, -1.0, 1.0)
        observed_z += config.contamination_displacement * contaminated * signs
        parameter = config.contamination_displacement
    observed = ObservedData(truth.row_id, truth.treatment, truth.outcome, observed_z)
    return observed, CorruptionRecord(missing, contaminated, float(parameter))
