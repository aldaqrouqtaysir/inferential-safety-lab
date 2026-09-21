# Batch experiment comparisons

A study runs a declared grid of existing benchmark configurations and compares
their aggregate results. Each configuration and seed remains a separate cell,
with the same four method pipelines used by a single run. The CLI writes an
offline HTML report, an SVG chart, CSV, and replay artifacts.

## Run the example

From the repository root, after the normal installation:

```powershell
.\.venv\Scripts\inferential-safety.exe validate-study --config configs/studies/mcar-sensitivity.json
.\.venv\Scripts\inferential-safety.exe study --config configs/studies/mcar-sensitivity.json --output artifacts/mcar-sensitivity
```

Choose an output directory that does not exist. `study` refuses an existing
directory or file rather than overwriting a previous result. It stages the
artifacts and publishes the destination only after the study completes.
Unexpected execution or write errors do not publish a partial study; expected
method failures remain recorded benchmark outcomes.

The [example configuration](../configs/studies/mcar-sensitivity.json) declares
sample sizes `[100, 300]`, missingness rates `[0.5, 0.7]`, and master seeds
`[2026092101, 2026092102]`, with 80 repetitions per cell. Its planned workload is
**8 cells, 640 simulated datasets, and 32 method comparison rows**. Each dataset
is shared by the four methods within its cell; it is not four separate datasets.
Validation prints `runs=8` and `simulated_datasets=640` without running simulations.

This sensitivity example is separate from the frozen demonstration and its
calibration evidence. Its settings describe an experiment, not a claim about
which method performs best.

## Study configuration

The root object has exactly three fields: `schema_version`, `base_config`, and
`grid`. The complete example is:

```json
{
  "schema_version": "inferential_safety_lab.study.v1",
  "base_config": {
    "schema_version": "inferential_safety_lab.config.v1",
    "scenario_id": "MCAR_SMALL_EFFECTIVE_SAMPLE",
    "sample_size": 100,
    "tau": 0.25,
    "repetitions": 80,
    "master_seed": 2026092101,
    "missingness_rate": 0.5,
    "contamination_fraction": 0.05,
    "contamination_displacement": 8.0,
    "confidence_level": 0.95,
    "winsorization_limits": [-3.0, 3.0]
  },
  "grid": {
    "sample_size": [100, 300],
    "missingness_rate": [0.5, 0.7],
    "master_seed": [2026092101, 2026092102]
  }
}
```

`base_config` is a self-contained, complete existing run configuration, including
fields that are inactive for its selected scenario. It does not reference a
second file or inherit omitted defaults. A grid value replaces its corresponding
base value; fields absent from the grid stay fixed. One study uses one scenario.

| Scenario | Allowed grid axes |
|---|---|
| `MCAR_SMALL_EFFECTIVE_SAMPLE` | `sample_size`, `missingness_rate`, `master_seed` |
| `OUTCOME_DEPENDENT_MAR` | `sample_size`, `missingness_rate`, `master_seed` |
| `GROSS_CONTAMINATION` | `sample_size`, `contamination_fraction`, `contamination_displacement`, `master_seed` |

The grid must have at least one axis. Each axis is a nonempty array of unique,
finite numeric values; booleans are rejected. Sample sizes and seeds must be
integers. Expansion takes the Cartesian product, with a maximum of **32 cells**.
Both commands validate the base and every expanded run configuration before
any simulation starts. Existing scenario limits still apply to every cell; for
example, MAR missingness must lie in `[0.15, 0.45]`, so the MCAR example's rates
cannot be reused for MAR. See [scenarios](scenarios.md) for the mechanisms.

Axis order is fixed as `sample_size`, `missingness_rate`,
`contamination_fraction`, `contamination_displacement`, then `master_seed`,
omitting absent axes. JSON object key order does not change execution order.
Values within each axis keep their declared order, and the last axis varies
fastest. Cells receive `run-001`, `run-002`, and subsequent identifiers in that
order. In the example, the first two cells have sample size 100 and missingness
0.5, and differ only in master seed.

## Saved artifacts and replay

Each completed study has five top-level files:

| File | Contents |
|---|---|
| `study-config.json` | Complete saved study configuration |
| `study.canonical.json` | Versioned study summary, separate cell configurations, method rows, replay hashes, and aggregate SHA-256 hashes |
| `comparison.csv` | One row per cell and method, with configuration, metrics, counts, and interval-applicability fields |
| `comparison.svg` | Separate availability and conditional-coverage bars with cell labels and counts |
| `study-report.html` | Offline comparison, Monte Carlo uncertainty, and relative links to cell artifacts |

Each `runs/run-NNN/` directory contains four existing single-run artifacts:
`run-config.json`, `aggregate.canonical.json`, `inferential-safety-card.html`,
and `runtime-diagnostics.json`. Keep the directory tree together so the HTML
report's links continue to work. The example therefore writes 5 study files
plus 32 per-cell files.

Replay the entire study from its saved configuration into a fresh directory:

```powershell
.\.venv\Scripts\inferential-safety.exe validate-study --config artifacts/mcar-sensitivity/study-config.json
.\.venv\Scripts\inferential-safety.exe study --config artifacts/mcar-sensitivity/study-config.json --output artifacts/mcar-sensitivity-replay
```

Replay one cell using the existing single-run command and a separate directory:

```powershell
.\.venv\Scripts\inferential-safety.exe validate-config --config artifacts/mcar-sensitivity/runs/run-001/run-config.json
.\.venv\Scripts\inferential-safety.exe run --config artifacts/mcar-sensitivity/runs/run-001/run-config.json --output artifacts/mcar-cell-001-replay
```

Seeds are explicit integers in the configuration. No seed is derived from the
clock. Exact replay requires the same configuration, platform, architecture,
Python version, NumPy build, dependency environment, and application code.
Within that environment, saved scientific artifacts are intended to reproduce
byte for byte; per-cell runtime diagnostics are excluded because scheduling and
timing vary. Unlike environments can have different raw hashes and low-order
floating-point results. See the [reproducibility contract](reproducibility.md).

## Read the comparison

Each row describes one cell and method. Cells are kept separate: the report
does not pool estimates or denominators across settings or seeds, score methods,
or rank an overall winner. Reusing a master seed across settings can reuse
deterministic streams; those cells are not independent evidence blocks. The
comparison does not perform a paired significance test.

Read error and reporting availability together. Bias and RMSE use available
point estimates. For a guarded method, they are conditional on the subset where
the reporting rule passed; a lower bias cannot by itself establish improvement.
Failures remain in all-attempt denominators. Conditional coverage uses covered
usable applicable intervals divided by usable applicable intervals; availability
uses usable applicable intervals divided by all attempts.

Scientifically inapplicable intervals are **N/A, not zero**. The HTML and SVG
show that distinction; corresponding CSV interval metrics are empty. Machine
readers should always check `interval_scientifically_applicable` and the reason,
including when reading canonical method metrics. An applicable method with no
usable intervals has 0% availability but undefined conditional coverage.

These are finite Monte Carlo experiments. Bias Monte Carlo standard errors and
95% Wilson ranges for coverage and availability describe simulation uncertainty
within each cell. They are not effect intervals, proof of exact population
rates, or tests of differences between methods. The effect interval confidence
level is separately fixed in `base_config.confidence_level`. Undefined metrics
remain unavailable rather than becoming zero. See
[metrics and denominators](metrics-and-denominators.md) and
[scientific boundaries](scientific-boundaries.md).
