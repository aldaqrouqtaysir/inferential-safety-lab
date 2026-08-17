"""Fixed scenario-specific method contracts."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from inferential_safety_lab.core.configuration import ScenarioId

DETERMINISTIC_IMPUTATION_REASON = "Deterministic single-imputation uncertainty was not propagated."
HUBER_INTERVAL_REASON = "Portable Huber covariance is not implemented."


@dataclass(frozen=True, slots=True)
class MethodContract:
    method_id: str
    display_name: str
    preprocessing_id: str
    estimator_id: str
    interval_scientifically_applicable: bool
    interval_unavailability_reason: str | None
    limitations: str

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


_COMPLETE_CASE = MethodContract(
    "complete_case_ols_hc3",
    "Complete-case OLS with HC3",
    "complete_case",
    "ols_hc3",
    True,
    None,
    "Targets the selected-data projection when missingness changes the fitting population.",
)
_MEDIAN = MethodContract(
    "median_imputation_ols",
    "Median single imputation + OLS",
    "median_single_imputation",
    "ols",
    False,
    DETERMINISTIC_IMPUTATION_REASON,
    "Single imputation treats filled values as known and does not propagate imputation uncertainty.",
)
_REGRESSION = MethodContract(
    "regression_imputation_ols",
    "Deterministic regression imputation + OLS",
    "deterministic_regression_single_imputation",
    "ols",
    False,
    DETERMINISTIC_IMPUTATION_REASON,
    "The deterministic model can overstate precision and its uncertainty is not propagated.",
)
_MISSING_DELETE = MethodContract(
    "guarded_deletion_ols_hc3",
    "Complete-case OLS with minimum-evidence reporting guard",
    "guarded_row_deletion_missing",
    "ols_hc3",
    True,
    None,
    "Requires at least 43% row retention and 12% of original rows in each treatment arm.",
)
_NO_REPAIR = MethodContract(
    "no_repair_ols_hc3",
    "No-repair OLS with HC3",
    "no_repair",
    "ols_hc3",
    True,
    None,
    "Uses the contaminated covariate directly and does not correct measurement error.",
)
_WINSOR = MethodContract(
    "fixed_winsorization_ols_hc3",
    "Fixed-limit winsorization + OLS with HC3",
    "fixed_limit_winsorization",
    "ols_hc3",
    True,
    None,
    "Clipping changes observed values and does not recover the latent covariate.",
)
_CONTAM_DELETE = MethodContract(
    "guarded_deletion_ols_hc3",
    "Guarded row deletion + OLS with HC3",
    "guarded_row_deletion_contamination",
    "ols_hc3",
    True,
    None,
    "Deletes observable extreme rows and requires 75% retention plus treatment-arm support.",
)
_HUBER = MethodContract(
    "huber_regression",
    "Huber robust regression",
    "no_repair",
    "huber_irls",
    False,
    HUBER_INTERVAL_REASON,
    "Does not generally correct covariate measurement error or establish causal validity.",
)


MISSINGNESS_METHODS = (_COMPLETE_CASE, _MEDIAN, _REGRESSION, _MISSING_DELETE)
CONTAMINATION_METHODS = (_NO_REPAIR, _WINSOR, _CONTAM_DELETE, _HUBER)


def method_panel(scenario_id: ScenarioId) -> tuple[MethodContract, ...]:
    if scenario_id is ScenarioId.GROSS_CONTAMINATION:
        return CONTAMINATION_METHODS
    return MISSINGNESS_METHODS
