# Default scenario freeze

The freeze followed the prospective rule exactly. Only missingness rates 0.50,
0.60, and 0.70 and calibration seed `2026081701` were evaluated. No other seed
was searched and no method-performance ranking was used.

## Calibration configuration

- Public scenario: **MCAR: small effective sample**
- Machine ID: `MCAR_SMALL_EFFECTIVE_SAMPLE`
- Sample size: 150
- Known average effect: 0.25
- Repetitions: 160
- Confidence level: 0.95
- Winsorization limits: [-3, 3]

## Calibration table

| Block | Seed | Missingness | Complete-case interval availability | Guarded reporting-contract availability | Maximum explicit deletion burden | Wall time (s) | Rule result |
|---|---:|---:|---:|---:|---:|---:|---|
| Calibration | 2026081701 | 0.50 | 1.0000 | 0.9500 | 0.4950 | 0.8612 | No: no practical interval method in 20–80% range |
| Calibration | 2026081701 | 0.60 | 1.0000 | 0.2687 | 0.5938 | 0.7074 | Yes: lowest qualifying rate |
| Calibration | 2026081701 | 0.70 | 1.0000 | 0.0000 | 0.6962 | 0.7036 | No: guarded availability below 20% |

Every attempt returned a classified method result. At 0.60, the
minimum-evidence reporting guard allowed 26.87% interval availability and
ordinary complete-case analysis was 73.13 percentage points higher. The 117
withheld results were classified as **Minimum-evidence guard not satisfied**.
Explicit deletion exceeded 30%, and the Quick run was well within the
30-second ceiling. The frozen missingness rate is **0.60**.

This is an intentionally severe stress test, selected prospectively from three
fixed missingness levels and checked on three held-out seeds. It exposes an
availability-and-reporting tradeoff and is not presented as a typical
real-world missingness rate.

## Held-out validation

The frozen rate alone was evaluated on the three specified held-out seeds.

| Seed | Complete-case availability | Guarded reporting-contract availability | Availability gap | Direction visible |
|---:|---:|---:|---:|---|
| 2026081702 | 1.0000 | 0.2000 | 0.8000 | Yes |
| 2026081703 | 1.0000 | 0.2625 | 0.7375 | Yes |
| 2026081704 | 1.0000 | 0.1812 | 0.8188 | Yes |

The direction remained visible in three of three blocks, exceeding the required
two. These data demonstrate an availability tradeoff under the frozen synthetic
mechanism; they do not identify a best method.
