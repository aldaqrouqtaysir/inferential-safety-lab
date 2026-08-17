# Reproducibility

A run identity includes package version, complete versioned configuration,
ordered method contracts, master seed, Python identity, direct dependency
versions, and `numpy.random.PCG64`.

Random streams use domain-separated SHA-256 derivation. DGP and corruption
streams are independent for every scenario and repetition. There is no mutable
module-level generator or run state.

The aggregate result schema is
`inferential_safety_lab.aggregate.v1`. Canonical JSON uses sorted keys, UTF-8,
compact separators, stable finite numbers, and JSON null for unavailable
metrics. The replay hash uses a separate SHA-256 domain and excludes itself.

## Two-level replay contract

### Level 1: exact environment replay

Within the same platform, architecture, Python version, NumPy build, dependency
environment, configuration, and seed, two fresh processes must produce
byte-identical canonical aggregate JSON and identical raw replay hashes. Every
supported CI matrix job tests this independently. A changed master seed must
change the replay hash.

### Level 2: cross-platform scientific equivalence

Across supported Windows/Python 3.12 and Ubuntu/Python 3.12–3.13 environments,
the typed scientific reference comparison requires identical scientific paths
and exact integers, booleans, nulls, strings, identifiers, classifications,
method order, failure/applicability states, numerators, and denominators. Finite
scientific floats must match the checked-in reference with `rtol = 1e-12` and
`atol = 1e-12`. NaN is rejected.

The canonical aggregate intentionally records environment identity, and its raw
replay hash includes that identity. Raw canonical bytes and raw replay hashes
are therefore environment-specific and are not expected to match across unlike
operating systems, Python versions, CPU dispatch, or numerical-library builds.
Tolerance-based scientific equivalence is not an exact hash match.

Wall-clock and per-method runtime measurements are emitted in
`runtime-diagnostics.json`, outside the canonical result and replay identity.
This preserves honest performance measurements without pretending that process
scheduling is deterministic.

The lock file records the tested local Windows/Python 3.12 dependency
environment. Public CI retains Windows/Python 3.12, Ubuntu/Python 3.12, and
Ubuntu/Python 3.13 coverage using the bounded compatibility ranges in
`pyproject.toml`. NumPy does not promise bit-identical linear-algebra or
transcendental results across all platform builds; the two-level contract states
the exact and tolerance-based guarantees this project actually tests.
