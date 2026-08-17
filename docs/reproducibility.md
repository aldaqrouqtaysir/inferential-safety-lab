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

Tests execute identical configurations in fresh Python processes and require
byte-identical aggregate JSON and identical replay hashes. A changed master
seed must change the replay hash.

Wall-clock and per-method runtime measurements are emitted in
`runtime-diagnostics.json`, outside the canonical result and replay identity.
This preserves honest performance measurements without pretending that process
scheduling is deterministic.

The lock file records the tested Windows/Python 3.12 dependency environment.
The CI workflow is configured for Python 3.13 on Ubuntu using the bounded
compatibility ranges in `pyproject.toml`; no public CI completion is claimed
before a public remote exists.
