# Metrics and denominators

Every practical method starts with the same number of attempted repetitions.
Failures remain in that denominator.

| Metric | Numerator / calculation | Denominator |
|---|---|---|
| Valid-fit rate | valid fits | all attempted runs |
| Point availability | finite point estimates | all attempted runs |
| Interval applicability | attempts whose method contract supports the estimand interval | all attempted runs |
| Interval availability | usable computed applicable intervals | all attempted runs |
| Conditional coverage | usable applicable intervals covering truth | usable applicable intervals |
| Valid-and-cover rate | usable applicable intervals covering truth | all attempted runs |
| Bias | mean estimate minus known target | available point estimates |
| Bias Monte Carlo SE | sample SD of errors / square root count | available point estimates |
| RMSE | square root of mean squared error | available point estimates |
| Median absolute error | median absolute error | available point estimates |
| Interval length | mean and median upper minus lower | usable applicable intervals |

Wilson intervals are reported for conditional coverage and interval
availability. An interval-applicable method with a zero usable-interval
denominator is displayed as **Applicable but unavailable**. A scientifically
inapplicable interval is displayed separately as **Not applicable**, with
conditional coverage, interval availability, and valid-and-cover rate all
shown as **N/A**, never 0% or method failure. Deterministic single-imputation
uncertainty was not propagated. Interval-inapplicable methods are excluded from
the coverage-versus-availability chart while remaining visible for point
estimates, bias, absolute bias, RMSE, intervention burden, warnings, and method
contracts.

Coverage and availability use paired, non-stacked 0–100% bars with explicit
numerators and denominators. Absolute bias and RMSE are shown separately and
are never stacked or summed.

Intervention metrics are averaged across all attempts: fitting-row retention,
fraction of originally missing covariates filled, fraction of originally
observed covariates changed, and fraction of original rows explicitly deleted.
Implicit complete-case exclusion is visible through fitting-row retention and
is not mislabeled as explicit deletion.

Per-attempt runtime is measured and aggregated in the separate runtime
diagnostic manifest. Timing is excluded from canonical result bytes and the
replay hash because operating-system scheduling is nondeterministic.
