"""Single deterministic benchmark engine shared by UI and CLI."""

from __future__ import annotations

import platform
from collections.abc import Callable
from importlib import metadata
from time import perf_counter
from typing import Any

import numpy as np

from inferential_safety_lab import __version__
from inferential_safety_lab.domain.datasets import ObservedData
from inferential_safety_lab.domain.results import RESULT_SCHEMA_VERSION, LabRun, MethodResult
from inferential_safety_lab.methods.contracts import MethodContract, method_panel
from inferential_safety_lab.methods.huber import fit_huber
from inferential_safety_lab.methods.interventions import preprocess
from inferential_safety_lab.methods.ols_hc3 import fit_ols_hc3
from inferential_safety_lab.metrics.intervention import runtime_summary
from inferential_safety_lab.metrics.repeated_sampling import summarize

from .configuration import RunConfig, ScenarioId
from .corruption import corrupt
from .dgp import generate_truth
from .seeds import BIT_GENERATOR_ID, rng_for
from .serialization import canonical_json, stable_hash

ProgressCallback = Callable[[int, int], None]


SCENARIO_DESCRIPTIONS = {
    ScenarioId.MCAR_SMALL_EFFECTIVE_SAMPLE: (
        "The covariate is missing completely at random, shrinking the effective fitting sample."
    ),
    ScenarioId.OUTCOME_DEPENDENT_MAR: (
        "Covariate missingness depends on observed treatment and outcome through a calibrated logistic law."
    ),
    ScenarioId.GROSS_CONTAMINATION: (
        "A bounded fraction of observed covariates receives an independent signed displacement."
    ),
}


def _dependency_versions() -> dict[str, str]:
    identities: dict[str, str] = {}
    for name in ("numpy", "pandas", "streamlit"):
        try:
            identities[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            identities[name] = "not-installed"
    return identities


def _environment() -> dict[str, Any]:
    return {
        "python": platform.python_version(),
        "implementation": platform.python_implementation(),
        "platform": f"{platform.system()}-{platform.machine()}",
        "dependencies": _dependency_versions(),
        "bit_generator": BIT_GENERATOR_ID,
    }


def _method_result(
    contract: MethodContract,
    observed: ObservedData,
    config: RunConfig,
) -> MethodResult:
    start = perf_counter()
    missing_before = int(np.isnan(observed.observed_z).sum())
    observed_before = observed.n - missing_before
    prepared = preprocess(contract.preprocessing_id, observed, config.winsorization_limits)
    fit = None
    if prepared.valid and isinstance(prepared.data, ObservedData):
        if contract.estimator_id == "huber_irls":
            fit = fit_huber(prepared.data)
        else:
            fit = fit_ols_hc3(
                prepared.data,
                confidence_level=config.confidence_level,
                compute_interval=contract.interval_scientifically_applicable,
            )
    elapsed = perf_counter() - start
    if fit is None:
        failure = prepared.failure_code
        fit_valid = False
        estimate = lower = upper = None
        n_fit = prepared.retained_row_count
        warnings = prepared.warnings
    else:
        failure = fit.failure_code
        fit_valid = fit.valid
        estimate, lower, upper = fit.point_estimate, fit.interval_lower, fit.interval_upper
        n_fit = fit.n_observations
        warnings = prepared.warnings + fit.warnings
    interval_computed = lower is not None and upper is not None
    unavailability = contract.interval_unavailability_reason
    if contract.interval_scientifically_applicable and not interval_computed:
        unavailability = f"method failure: {failure.value}"
    return MethodResult(
        contract.method_id,
        contract.preprocessing_id,
        contract.estimator_id,
        1,
        fit_valid,
        failure,
        estimate is not None,
        estimate,
        interval_computed,
        contract.interval_scientifically_applicable,
        unavailability,
        lower,
        upper,
        n_fit,
        n_fit / observed.n,
        prepared.filled_missing_count,
        prepared.filled_missing_count / missing_before if missing_before else 0.0,
        prepared.changed_observed_count,
        prepared.changed_observed_count / observed_before if observed_before else 0.0,
        prepared.explicit_deletion_count,
        prepared.explicit_deletion_count / observed.n,
        elapsed,
        warnings,
        {
            "engine": "inferential_safety_lab.core.engine",
            "package_version": __version__,
            "analysis_columns": "outcome,treatment,observed_z,treatment:observed_z",
        },
    )


def _reference_result(data: ObservedData, config: RunConfig) -> MethodResult:
    contract = MethodContract(
        "clean_data_evaluator_reference",
        "Clean-data evaluator reference",
        "evaluator_only_clean_data",
        "ols_hc3",
        True,
        None,
        "Evaluator-only reference; unavailable to practical methods and never ranked.",
    )
    return _method_result(contract, data, config)


def _observation(metrics: list[dict[str, Any]]) -> str:
    by_id = {row.get("method_id"): row for row in metrics}
    complete = by_id.get("complete_case_ols_hc3")
    guarded = by_id.get("guarded_deletion_ols_hc3")
    if complete is not None and guarded is not None:
        attempted = int(guarded["attempted_runs"])
        reported = int(guarded["interval_available_runs"])
        withheld = attempted - reported
        return (
            "Complete-case OLS returned an applicable interval in "
            f"{complete['interval_available_runs']} of {complete['attempted_runs']} attempts. "
            "Applying the predeclared minimum-evidence reporting guard withheld "
            f"{withheld} results; among the {reported} reported intervals, "
            f"{guarded['conditional_coverage_numerator']} covered the known target."
        )
    interval_rows = [row for row in metrics if row["interval_applicable_attempts"]]
    if not interval_rows:
        return "No practical method had a scientifically applicable interval in this panel."
    row = min(interval_rows, key=lambda item: float(item["interval_availability"] or 0.0))
    coverage = row["conditional_coverage"]
    coverage_text = "undefined" if coverage is None else f"{100 * float(coverage):.0f}%"
    return (
        f"{row['display_name']} covered the known target in {coverage_text} of its usable "
        f"intervals ({row['conditional_coverage_numerator']}/{row['conditional_coverage_denominator']}), "
        f"while producing an applicable interval in {100 * float(row['interval_availability']):.0f}% "
        f"of attempts ({row['interval_available_runs']}/{row['attempted_runs']})."
    )


def run_benchmark(config: RunConfig, progress: ProgressCallback | None = None) -> LabRun:
    """Run bounded repetitions and return replay-stable aggregate plus runtime diagnostics."""

    contracts = method_panel(config.scenario_id)
    by_method: dict[str, list[MethodResult]] = {contract.method_id: [] for contract in contracts}
    reference: list[MethodResult] = []
    run_start = perf_counter()
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
        reference.append(_reference_result(truth.clean_observed(), config))
        for contract in contracts:
            by_method[contract.method_id].append(_method_result(contract, observed, config))
        if progress is not None:
            progress(repetition + 1, config.repetitions)
    wall_seconds = perf_counter() - run_start
    environment = _environment()
    replay_identity = {
        "package_version": __version__,
        "configuration": config.as_dict(),
        "method_contracts": [contract.as_dict() for contract in contracts],
        "environment": environment,
    }
    replay_hash = stable_hash(replay_identity, domain="benchmark-replay")
    metric_rows: list[dict[str, Any]] = []
    for contract in contracts:
        row = summarize(by_method[contract.method_id], config.tau)
        row.update({"method_id": contract.method_id, "display_name": contract.display_name})
        metric_rows.append(row)
    reference_metrics = summarize(reference, config.tau)
    chart_data = {
        "coverage_availability": [
            {
                "method": row["display_name"],
                "conditional_coverage": row["conditional_coverage"],
                "interval_availability": row["interval_availability"],
            }
            for row in metric_rows
        ],
        "estimation_error": [
            {
                "method": row["display_name"],
                "absolute_bias": row["absolute_bias"],
                "rmse": row["rmse"],
                "known_target": config.tau,
            }
            for row in metric_rows
        ],
        "intervention_performance": [
            {
                "method": row["display_name"],
                "intervention_fraction": max(
                    float(row["mean_filled_missing_fraction"] or 0.0),
                    float(row["mean_changed_observed_fraction"] or 0.0),
                    float(row["mean_explicit_deletion_fraction"] or 0.0),
                ),
                "rmse": row["rmse"],
            }
            for row in metric_rows
        ],
        "failures": [
            {
                "method": row["display_name"],
                "failure_code": code,
                "count": count,
            }
            for row in metric_rows
            for code, count in row["failure_code_counts"].items()
        ],
    }
    aggregate: dict[str, Any] = {
        "schema_version": RESULT_SCHEMA_VERSION,
        "software_version": __version__,
        "scenario_id": config.scenario_id.value,
        "scenario_mechanism": SCENARIO_DESCRIPTIONS[config.scenario_id],
        "known_truth": {
            "estimand": "known average effect (original-population average treatment effect)",
            "value": config.tau,
            "formula": "Y = 1 + tau*T + 0.8*Z + 0.5*T*Z + epsilon; E[Z]=0",
        },
        "configuration": config.as_dict(),
        "environment": environment,
        "replay_hash": replay_hash,
        "method_contracts": [contract.as_dict() for contract in contracts],
        "method_metrics": metric_rows,
        "evaluator_reference": {
            "display_name": "Clean-data evaluator reference (not selectable)",
            "metrics": reference_metrics,
        },
        "chart_data": chart_data,
        "headline_observation": _observation(metric_rows),
        "conclusion": (
            "Under this synthetic mechanism and configuration, the methods exhibit different "
            "tradeoffs in estimation error, interval behavior, availability, and data intervention. "
            "These results are conditional on the scenario and do not identify a universal winner."
        ),
        "replay_command": (
            "inferential-safety run --config run-config.json --output replay-output"
        ),
        "privacy": {
            "synthetic_only": True,
            "row_level_data_exported": False,
            "network_required_after_installation": False,
        },
        "runtime_note": (
            "Wall-clock and per-method timing are written separately so replay-stable aggregate bytes "
            "do not depend on machine scheduling."
        ),
    }
    canonical = canonical_json(aggregate) + "\n"
    diagnostics = {
        "wall_seconds": wall_seconds,
        "repetitions_per_second": config.repetitions / wall_seconds,
        "method_runtime": runtime_summary(by_method),
        "machine": platform.platform(),
        "note": "Performance diagnostics are intentionally excluded from the replay hash.",
    }
    return LabRun(aggregate, canonical, replay_hash, diagnostics)
