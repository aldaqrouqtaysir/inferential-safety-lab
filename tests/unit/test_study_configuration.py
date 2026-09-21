from __future__ import annotations

from copy import deepcopy
from typing import Any

import pytest

from inferential_safety_lab.core.configuration import ScenarioId
from inferential_safety_lab.core.study_configuration import STUDY_SCHEMA_VERSION, StudyConfig
from inferential_safety_lab.services.presets import get_preset


def manifest(scenario: ScenarioId = ScenarioId.MCAR_SMALL_EFFECTIVE_SAMPLE) -> dict[str, Any]:
    return {
        "schema_version": STUDY_SCHEMA_VERSION,
        "base_config": get_preset(scenario).as_dict(),
        "grid": {"master_seed": [31, 32], "sample_size": [100, 300]},
    }


def test_grid_order_and_explicit_seeds_survive_round_trip() -> None:
    payload = manifest()
    config = StudyConfig.from_dict(payload)
    assert [(cell.sample_size, cell.master_seed) for cell in config.expand()] == [
        (100, 31),
        (100, 32),
        (300, 31),
        (300, 32),
    ]
    # JSON object key order has no scientific or execution-order significance.
    payload["grid"] = dict(reversed(list(payload["grid"].items())))
    assert StudyConfig.from_dict(payload).expand() == config.expand()
    import json

    assert StudyConfig.from_dict(json.loads(json.dumps(config.as_dict()))) == config
    payload["grid"]["master_seed"].append(999)
    assert len(config.expand()) == 4  # No mutable alias to the caller's payload.


@pytest.mark.parametrize("scenario", list(ScenarioId))
def test_each_scenario_accepts_only_its_relevant_intensity_axes(scenario: ScenarioId) -> None:
    payload = manifest(scenario)
    if scenario is ScenarioId.GROSS_CONTAMINATION:
        payload["grid"].update(
            contamination_fraction=[0.01, 0.15], contamination_displacement=[4, 12]
        )
        wrong_axis = "missingness_rate"
    else:
        rates = [0.5, 0.7] if scenario is ScenarioId.MCAR_SMALL_EFFECTIVE_SAMPLE else [0.15, 0.45]
        payload["grid"]["missingness_rate"] = rates
        wrong_axis = "contamination_fraction"
    assert len(StudyConfig.from_dict(payload).expand()) in (8, 16)
    payload["grid"][wrong_axis] = [0.5]
    with pytest.raises(ValueError, match="axes for this scenario"):
        StudyConfig.from_dict(payload)


@pytest.mark.parametrize(
    ("axis", "values", "message"),
    [
        ("sample_size", [], "at least one"),
        ("sample_size", [100, 100], "duplicate"),
        ("sample_size", [100, 250], "sample_size"),
        ("sample_size", [100.0], "integers"),
        ("master_seed", [False], "finite number"),
        ("master_seed", [0, -1], "non-negative"),
        ("master_seed", [1.5], "integers"),
        ("missingness_rate", [float("nan")], "finite"),
        ("missingness_rate", [float("inf")], "finite"),
        ("missingness_rate", ["0.5"], "finite"),
        ("missingness_rate", [0.5, 0.8], "missingness_rate"),
        ("master_seed", 10, "array"),
        ("unknown", [1], "axes"),
    ],
)
def test_invalid_grid_fails_before_execution(axis: str, values: Any, message: str) -> None:
    payload = manifest()
    payload["grid"] = {axis: values}
    with pytest.raises(ValueError, match=message):
        StudyConfig.from_dict(payload)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("sample_size", 100.0),
        ("repetitions", 80.5),
        ("master_seed", True),
        ("missingness_rate", True),
        ("contamination_fraction", float("nan")),
        ("tau", "0.25"),
        ("winsorization_limits", [True, 3.0]),
        ("winsorization_limits", [1.0]),
        ("winsorization_limits", [-(10**1000), 3]),
    ],
)
def test_base_config_is_strict_even_for_overridden_or_inactive_fields(
    field: str, value: Any
) -> None:
    payload = manifest()
    payload["base_config"][field] = value
    with pytest.raises(ValueError):
        StudyConfig.from_dict(payload)


def test_grid_cap_and_manifest_structure() -> None:
    payload = manifest()
    payload["grid"] = {"master_seed": list(range(32))}
    assert len(StudyConfig.from_dict(payload).expand()) == 32
    payload["grid"]["sample_size"] = [100, 300]
    with pytest.raises(ValueError, match="64 runs; maximum is 32"):
        StudyConfig.from_dict(payload)
    invalid: list[Any] = [[], {}, {**payload, "schema_version": "future"}]
    for key, value in (("grid", {}), ("grid", []), ("base_config", [])):
        altered = deepcopy(payload)
        altered[key] = value
        invalid.append(altered)
    for value in invalid:
        with pytest.raises(ValueError):
            StudyConfig.from_dict(value)
