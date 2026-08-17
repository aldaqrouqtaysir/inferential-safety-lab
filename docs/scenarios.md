# Scenarios

All scenarios retain the known-truth mechanism:

```text
Z ~ Normal(0,1)
T | Z ~ Bernoulli(expit(-0.2 + 0.6 Z))
epsilon ~ Normal(0,1)
Y = 1 + tau*T + 0.8*Z + 0.5*T*Z + epsilon
```

The heterogeneous conditional effect is `tau + 0.5 Z`. Because the original
population has `E[Z] = 0`, the known target effect is `tau`.

## MCAR_SMALL_EFFECTIVE_SAMPLE

Each covariate value is missing independently with probability 0.50, 0.60, or
0.70. The frozen demo uses 0.60 to expose interval-availability differences
caused by a documented feasibility contract.

## OUTCOME_DEPENDENT_MAR

The missingness probability is
`expit(alpha + 0.5 T + 0.35 Y)`. A deterministic bisection selects `alpha` so
the generated finite population has the requested expected missingness between
0.15 and 0.45.

## GROSS_CONTAMINATION

A bounded fraction between 0.01 and 0.15 receives an independent signed
displacement between four and twelve standard-deviation units. The default is
8% at eight units.

The internally generated clean-data reference is not a fourth headline
scenario.
