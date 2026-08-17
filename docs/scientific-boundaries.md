# Scientific boundaries

This project is an educational repeated-sampling simulator using synthetic data
with known truth. It is not a universal recommender, an arbitrary-data causal
engine, a medical or government decision system, or a publication-grade final
experiment.

The data-generating mechanism fixes one estimand and one four-column analysis
model. Results therefore describe behavior under the chosen mechanism,
settings, and software versions. They do not establish identification,
transportability, or causal validity for real data.

No practical method can access clean latent covariates, corruption masks, true
effect values, or evaluator metrics. The clean-data fit is an evaluator-only
reference. It is not selectable and is not treated as a winner.

No overall safety score, leaderboard, automatic recommendation, or universal
winner is computed. Plain-language observations are rule-based and always end
with a context-specific conclusion.

Supported environments can use different floating-point kernels for
transcendental functions and BLAS/LAPACK operations. Reproducibility therefore
distinguishes byte-exact replay inside one fixed environment from typed
cross-platform scientific equivalence. Platform variation may affect only
finite low-order floats within the frozen `1e-12` tolerance; discrete data,
states, counts, denominators, method ordering, scenario-freeze decisions, and
displayed conclusions remain exact.

V0.1 is synthetic-only: no upload, URL input, external API, database,
authentication, telemetry, model download, or post-install network path exists.
