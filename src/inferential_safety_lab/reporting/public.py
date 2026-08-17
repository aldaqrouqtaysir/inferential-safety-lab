"""Human-readable, scientifically explicit public presentation semantics."""

from __future__ import annotations

from typing import Any

WHY_AVAILABILITY_DIFFERS = (
    "Why availability differs: Both complete-case pipelines use rows with observed analysis "
    "covariates. The guarded version additionally withholds a result unless its predeclared "
    "row-retention and treatment-arm-support requirements are met. Its lower availability "
    "reflects that reporting contract, not a different estimator."
)
GUARDED_CONDITIONAL_WARNING = (
    "Bias and RMSE for the guarded version are conditional on runs that passed the guard and are "
    "not an all-attempt superiority comparison."
)
SEVERE_STRESS_LABEL = "Intentionally severe stress test: 60% MCAR missingness"
SEVERE_STRESS_EXPLANATION = (
    "This scenario was selected prospectively from three fixed missingness levels and checked on "
    "three held-out seeds. It is designed to expose an availability-and-reporting tradeoff and is "
    "not presented as a typical real-world missingness rate."
)
DETERMINISTIC_IMPUTATION_REASON = "Deterministic single-imputation uncertainty was not propagated."
GUARD_FAILURE_LABEL = "Minimum-evidence rule not satisfied"

PUBLIC_SCENARIO_NAMES = {
    "MCAR_SMALL_EFFECTIVE_SAMPLE": "MCAR: small effective sample",
    "OUTCOME_DEPENDENT_MAR": "Outcome-dependent MAR",
    "GROSS_CONTAMINATION": "Gross contamination",
}

PUBLIC_FAILURE_LABELS = {
    "INSUFFICIENT_ROWS": GUARD_FAILURE_LABEL,
    "TREATMENT_ARM_SUPPORT": "Insufficient treatment-arm support",
    "RANK_DEFICIENT_DESIGN": "Rank-deficient design",
    "SINGULAR_CROSSPRODUCT": "Singular cross-product matrix",
    "HC3_UNDEFINED_PERFECT_LEVERAGE": "HC3 undefined because of perfect leverage",
    "NONFINITE_ESTIMATE": "Non-finite estimate",
    "NO_OBSERVED_VALUES_FOR_IMPUTATION": "No observed covariate values for imputation",
    "IMPUTATION_RANK_FAILURE": "Imputation design was rank deficient",
    "HUBER_SCALE_FAILURE": "Huber scale could not be estimated",
    "HUBER_NONCONVERGENCE": "Huber regression did not converge",
}

PUBLIC_PREPROCESSING_LABELS = {
    "complete_case": "Complete cases",
    "median_single_imputation": "Median single imputation",
    "deterministic_regression_single_imputation": "Deterministic regression imputation",
    "guarded_row_deletion_missing": "Complete cases with minimum-evidence reporting guard",
    "no_repair": "No repair",
    "fixed_limit_winsorization": "Fixed-limit winsorization",
    "guarded_row_deletion_contamination": "Extreme-row deletion with evidence guard",
    "evaluator_only_clean_data": "Evaluator-only clean data",
}

PUBLIC_ESTIMATOR_LABELS = {
    "ols": "Ordinary least squares point estimate",
    "ols_hc3": "Ordinary least squares with HC3 covariance",
    "huber_irls": "Huber robust regression",
}

PUBLIC_METHOD_LABELS = {
    "complete_case_ols_hc3": "Use rows with complete measurements",
    "median_imputation_ols": "Fill missing values with the median",
    "regression_imputation_ols": "Fill missing values from a prediction",
    "guarded_deletion_ols_hc3": "Use rows that pass the minimum-evidence rule",
    "no_repair_ols_hc3": "Leave extreme measurements unchanged",
    "fixed_winsorization_ols_hc3": "Limit measurements to fixed bounds",
    "huber_regression": "Reduce the influence of extreme measurements",
}


def show_number(value: Any, *, digits: int = 3) -> str:
    """Format a numeric point metric, reserving N/A for scientific inapplicability."""

    return "Not available" if value is None else f"{float(value):.{digits}f}"


def show_percent(value: Any) -> str:
    return "Not available" if value is None else f"{100 * float(value):.1f}%"


def ratio(value: Any, numerator: int, denominator: int) -> str:
    return f"{show_percent(value)} · {numerator}/{denominator}"


def interval_display(row: dict[str, Any]) -> dict[str, str]:
    """Keep inapplicability, applicable unavailability, and availability distinct."""

    if int(row["interval_applicable_attempts"]) == 0:
        return {
            "status": "Not applicable",
            "conditional_coverage": "N/A",
            "interval_availability": "N/A",
            "valid_and_cover": "N/A",
        }
    status = (
        "Applicable and available"
        if int(row["interval_available_runs"]) > 0
        else "Applicable but unavailable"
    )
    return {
        "status": status,
        "conditional_coverage": ratio(
            row["conditional_coverage"],
            int(row["conditional_coverage_numerator"]),
            int(row["conditional_coverage_denominator"]),
        ),
        "interval_availability": ratio(
            row["interval_availability"],
            int(row["interval_available_runs"]),
            int(row["attempted_runs"]),
        ),
        "valid_and_cover": ratio(
            row["valid_and_cover_rate"],
            int(row["valid_and_cover_numerator"]),
            int(row["valid_and_cover_denominator"]),
        ),
    }


def public_scenario_name(scenario_id: str) -> str:
    return PUBLIC_SCENARIO_NAMES.get(scenario_id, scenario_id.replace("_", " ").title())


def public_failure_label(code: str) -> str:
    return PUBLIC_FAILURE_LABELS.get(code, code.replace("_", " ").title())


def public_preprocessing_label(identifier: str) -> str:
    return PUBLIC_PREPROCESSING_LABELS.get(identifier, identifier.replace("_", " ").title())


def public_estimator_label(identifier: str) -> str:
    return PUBLIC_ESTIMATOR_LABELS.get(identifier, identifier.replace("_", " ").title())


def public_method_label(identifier: str, fallback: str) -> str:
    """Return the shared plain-language method name used across public surfaces."""

    return PUBLIC_METHOD_LABELS.get(identifier, fallback)
