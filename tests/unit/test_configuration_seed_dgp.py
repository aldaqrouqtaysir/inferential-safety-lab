from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest

from inferential_safety_lab.core.configuration import (
    CONFIG_SCHEMA_VERSION,
    RunConfig,
    ScenarioId,
    load_config,
)
from inferential_safety_lab.core.corruption import calibrate_mar_intercept, corrupt
from inferential_safety_lab.core.dgp import expit, generate_truth, original_target
from inferential_safety_lab.core.seeds import BIT_GENERATOR_ID, derive_seed, rng_for
from inferential_safety_lab.core.serialization import canonical_json, stable_hash
from inferential_safety_lab.services.presets import all_presets, get_preset


def demo() -> RunConfig:
    return load_config("configs/demo_mcar_stress.json")


def test_exact_three_versioned_presets_load() -> None:
    presets = all_presets()
    assert tuple(item.scenario_id for item in presets) == tuple(ScenarioId)
    assert all(item.schema_version == CONFIG_SCHEMA_VERSION for item in presets)


def test_embedded_presets_match_versioned_json_examples() -> None:
    files = {
        ScenarioId.MCAR_SMALL_EFFECTIVE_SAMPLE: "configs/demo_mcar_stress.json",
        ScenarioId.OUTCOME_DEPENDENT_MAR: "configs/outcome_dependent_mar.json",
        ScenarioId.GROSS_CONTAMINATION: "configs/gross_contamination.json",
    }
    for scenario, path in files.items():
        assert get_preset(scenario) == load_config(path)


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"sample_size": 151}, "sample_size"),
        ({"tau": 0.1}, "tau"),
        ({"repetitions": 250}, "repetitions"),
        ({"master_seed": -1}, "master_seed"),
        ({"missingness_rate": 0.55}, "missingness_rate"),
        ({"confidence_level": 1.0}, "confidence_level"),
        ({"winsorization_limits": (3.0, -3.0)}, "winsorization_limits"),
    ],
)
def test_configuration_rejects_unbounded_or_unsupported_values(
    changes: dict[str, object], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        replace(demo(), **changes)


def test_scenario_specific_bounds() -> None:
    mar = get_preset(ScenarioId.OUTCOME_DEPENDENT_MAR)
    contamination = get_preset(ScenarioId.GROSS_CONTAMINATION)
    with pytest.raises(ValueError, match="MAR"):
        replace(mar, missingness_rate=0.6)
    with pytest.raises(ValueError, match="contamination_fraction"):
        replace(contamination, contamination_fraction=0.5)
    with pytest.raises(ValueError, match="contamination_displacement"):
        replace(contamination, contamination_displacement=20.0)


def test_from_dict_rejects_unknown_or_missing_fields() -> None:
    payload = demo().as_dict()
    payload["unexpected"] = True
    with pytest.raises(ValueError, match="unexpected"):
        RunConfig.from_dict(payload)
    payload = demo().as_dict()
    del payload["tau"]
    with pytest.raises(ValueError, match="missing"):
        RunConfig.from_dict(payload)


def test_canonical_json_is_order_stable_and_hash_domain_separated() -> None:
    left = {"z": 1, "a": [0.25, -0.0]}
    right = {"a": [0.25, 0.0], "z": 1}
    assert canonical_json(left) == canonical_json(right)
    assert stable_hash(left, domain="a") != stable_hash(left, domain="b")


def test_seed_derivation_is_stable_separated_and_explicit() -> None:
    assert BIT_GENERATOR_ID == "numpy.random.PCG64"
    assert derive_seed(10, "dgp", 1) == derive_seed(10, "dgp", 1)
    assert derive_seed(10, "dgp", 1) != derive_seed(10, "corruption", 1)
    assert derive_seed(10, "dgp", 1) != derive_seed(11, "dgp", 1)
    with pytest.raises(ValueError):
        derive_seed(-1, "dgp")
    with pytest.raises(ValueError):
        derive_seed(1, "")


def test_dgp_equations_and_original_target() -> None:
    truth = generate_truth(n=150, tau=0.25, rng=rng_for(9, "dgp"))
    assert original_target(0.25) == 0.25
    assert np.allclose(truth.y0, 1.0 + 0.8 * truth.latent_z + truth.epsilon)
    assert np.allclose(truth.y1, 1.0 + 0.25 + 1.3 * truth.latent_z + truth.epsilon)
    assert np.allclose(truth.y1 - truth.y0, 0.25 + 0.5 * truth.latent_z)
    assert np.array_equal(truth.outcome, np.where(truth.treatment == 1, truth.y1, truth.y0))


def test_truth_and_observed_are_structurally_separate_and_immutable() -> None:
    truth = generate_truth(n=100, tau=0.0, rng=rng_for(7, "dgp"))
    observed = truth.clean_observed()
    assert observed.field_names == ("row_id", "treatment", "outcome", "observed_z")
    assert "tau" not in observed.field_names
    assert "latent_z" not in observed.field_names
    with pytest.raises(ValueError):
        observed.observed_z.setflags(write=True)
    with pytest.raises(ValueError):
        truth.latent_z.setflags(write=True)


def test_mcar_corruption_is_deterministic_and_near_target() -> None:
    config = demo()
    truth = generate_truth(n=config.sample_size, tau=config.tau, rng=rng_for(2, "dgp"))
    first, first_record = corrupt(truth, config, rng_for(2, "corruption"))
    second, second_record = corrupt(truth, config, rng_for(2, "corruption"))
    assert np.array_equal(first_record.missing_mask, second_record.missing_mask)
    assert np.array_equal(first.observed_z, second.observed_z, equal_nan=True)
    assert 0.45 < float(first_record.missing_mask.mean()) < 0.75


def test_outcome_dependent_mar_calibrates_expected_rate() -> None:
    config = get_preset(ScenarioId.OUTCOME_DEPENDENT_MAR)
    truth = generate_truth(n=config.sample_size, tau=config.tau, rng=rng_for(3, "dgp"))
    alpha = calibrate_mar_intercept(truth, config.missingness_rate)
    probability = expit(alpha + 0.5 * truth.treatment + 0.35 * truth.outcome)
    assert float(probability.mean()) == pytest.approx(config.missingness_rate, abs=1e-12)
    assert np.corrcoef(probability, truth.outcome)[0, 1] > 0.5


def test_gross_contamination_is_deterministic_and_uses_fixed_displacement() -> None:
    config = get_preset(ScenarioId.GROSS_CONTAMINATION)
    truth = generate_truth(n=config.sample_size, tau=config.tau, rng=rng_for(4, "dgp"))
    first, record = corrupt(truth, config, rng_for(4, "corruption"))
    second, record_two = corrupt(truth, config, rng_for(4, "corruption"))
    assert np.array_equal(record.contamination_mask, record_two.contamination_mask)
    assert np.array_equal(first.observed_z, second.observed_z)
    displacement = first.observed_z - truth.latent_z
    assert np.all(
        np.isclose(displacement, 0.0)
        | np.isclose(np.abs(displacement), config.contamination_displacement)
    )
