"""Exactly three user-facing configuration presets."""

from __future__ import annotations

from inferential_safety_lab.core.configuration import (
    CONFIG_SCHEMA_VERSION,
    RunConfig,
    ScenarioId,
)


def _preset(
    scenario_id: ScenarioId,
    sample_size: int,
    master_seed: int,
    missingness_rate: float,
    contamination_fraction: float,
) -> RunConfig:
    return RunConfig(
        schema_version=CONFIG_SCHEMA_VERSION,
        scenario_id=scenario_id,
        sample_size=sample_size,
        tau=0.25,
        repetitions=160,
        master_seed=master_seed,
        missingness_rate=missingness_rate,
        contamination_fraction=contamination_fraction,
        contamination_displacement=8.0,
        confidence_level=0.95,
        winsorization_limits=(-3.0, 3.0),
    )


PRESETS = {
    ScenarioId.MCAR_SMALL_EFFECTIVE_SAMPLE: _preset(
        ScenarioId.MCAR_SMALL_EFFECTIVE_SAMPLE,
        150,
        2026081701,
        0.60,
        0.05,
    ),
    ScenarioId.OUTCOME_DEPENDENT_MAR: _preset(
        ScenarioId.OUTCOME_DEPENDENT_MAR,
        300,
        2026081711,
        0.30,
        0.05,
    ),
    ScenarioId.GROSS_CONTAMINATION: _preset(
        ScenarioId.GROSS_CONTAMINATION,
        300,
        2026081721,
        0.25,
        0.08,
    ),
}


def get_preset(scenario_id: ScenarioId) -> RunConfig:
    return PRESETS[scenario_id]


def all_presets() -> tuple[RunConfig, ...]:
    return tuple(get_preset(scenario) for scenario in ScenarioId)
