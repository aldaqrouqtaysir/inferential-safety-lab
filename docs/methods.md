# Methods

Every model fits `Y ~ 1 + T + Z + T:Z` and reports the coefficient of `T`, which
corresponds to the target at `Z = 0`.

## Missingness panels

1. **Complete-case OLS with HC3.** Fits finite rows and reports a normal-Wald
   HC3 interval. Retention captures implicit exclusion. The estimate may be a
   selected-data projection.
2. **Median single imputation followed by OLS.** Fills each missing covariate
   with the observed median. It reports a point estimate only; the original
   target interval is inapplicable because deterministic imputation uncertainty
   is not propagated.
3. **Deterministic regression single imputation followed by OLS.** Regresses
   observed `Z` on `1, T, Y, T:Y`, fills missing values deterministically, and
   reports a point estimate only for the same uncertainty reason.
4. **Complete-case OLS with minimum-evidence reporting guard.** Uses exactly
   the same observed-covariate rows, design matrix, outcome vector, OLS
   estimate, HC3 covariance, and interval as ordinary complete-case OLS when
   the guard passes. It additionally requires at least 43% row retention and at
   least 12% of the original rows in each treatment arm. A failed guard
   withholds the result under the reporting contract; it does not define a
   different estimator.

Why availability differs: Both complete-case pipelines use rows with observed
analysis covariates. The guarded version additionally withholds a result unless
its predeclared row-retention and treatment-arm-support requirements are met.
Its lower availability reflects that reporting contract, not a different
estimator.

Bias and RMSE for the guarded version are conditional on runs that passed the
guard and are not an all-attempt superiority comparison.

## Contamination panel

1. **No-repair OLS with HC3.** Uses contaminated `Z` directly.
2. **Fixed-limit winsorization followed by OLS with HC3.** Clips observed `Z`
   at the configured fixed limits; changed observed cells are reported.
3. **Guarded row deletion followed by OLS with HC3.** Deletes missing or
   absolute `Z > 3` rows and requires 75% retention plus 15% of original rows
   in each arm.
4. **Huber robust regression.** Portable deterministic IRLS with tuning constant
   1.345. V0.2.0 provides the point estimate only. It does not generally correct
   covariate measurement error or establish causal validity.

No method outside the selected scenario panel is exposed. The evaluator-only
clean-data fit appears separately and cannot be selected.
