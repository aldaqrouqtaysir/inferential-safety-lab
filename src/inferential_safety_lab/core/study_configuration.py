"""A bounded, explicit grid of existing run configurations."""

from __future__ import annotations

import itertools
import json
import math
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from inferential_safety_lab.core.configuration import RunConfig, ScenarioId

STUDY_SCHEMA_VERSION = "inferential_safety_lab.study.v1"
MAX_STUDY_RUNS = 32
# Stable execution order does not depend on the order of keys in a JSON object.
AXIS_ORDER = (
    "sample_size",
    "missingness_rate",
    "contamination_fraction",
    "contamination_displacement",
    "master_seed",
)
INTEGER_FIELDS = ("sample_size", "repetitions", "master_seed")
FLOAT_FIELDS = (
    "tau",
    "missingness_rate",
    "contamination_fraction",
    "contamination_displacement",
    "confidence_level",
)


def _finite_number(value: Any, label: str) -> None:
    if type(value) not in (int, float):
        raise ValueError(f"{label} must be a finite number (not a boolean)")
    try:
        finite = math.isfinite(value)
    except OverflowError:
        finite = False
    if not finite:
        raise ValueError(f"{label} must be a finite number")


def _strict_config(payload: Any) -> RunConfig:
    if not isinstance(payload, dict):
        raise ValueError("base_config must be a complete run configuration object")
    values = dict(payload)
    for key in INTEGER_FIELDS:
        if key in values and type(values[key]) is not int:
            raise ValueError(f"base_config.{key} must be an integer (not a boolean)")
    for key in FLOAT_FIELDS:
        if key in values:
            _finite_number(values[key], f"base_config.{key}")
            values[key] = float(values[key])
    limits = values.get("winsorization_limits")
    if not isinstance(limits, (list, tuple)) or len(limits) != 2:
        raise ValueError("base_config.winsorization_limits must contain two finite numbers")
    for value in limits:
        _finite_number(value, "base_config.winsorization_limits")
    return RunConfig.from_dict(values)


@dataclass(frozen=True, slots=True)
class StudyConfig:
    base_config: RunConfig
    grid: tuple[tuple[str, tuple[int | float, ...]], ...]
    schema_version: str = STUDY_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != STUDY_SCHEMA_VERSION:
            raise ValueError(f"schema_version must be {STUDY_SCHEMA_VERSION!r}")
        _strict_config(self.base_config.as_dict())
        allowed = {"sample_size", "master_seed"}
        if self.base_config.scenario_id is ScenarioId.GROSS_CONTAMINATION:
            allowed.update(("contamination_fraction", "contamination_displacement"))
        else:
            allowed.add("missingness_rate")
        names = [key for key, _ in self.grid]
        if not names or len(set(names)) != len(names):
            raise ValueError("grid must contain at least one axis with unique axis names")
        if set(names) - allowed:
            raise ValueError(f"grid axes for this scenario must be chosen from {sorted(allowed)}")
        count = 1
        for key, values in self.grid:
            if not values:
                raise ValueError(f"grid.{key} must contain at least one value")
            for value in values:
                _finite_number(value, f"grid.{key}")
                if key in INTEGER_FIELDS and type(value) is not int:
                    raise ValueError(f"grid.{key} values must be integers")
            if len(set(values)) != len(values):
                raise ValueError(f"grid.{key} must not contain duplicate values")
            count *= len(values)
        if count > MAX_STUDY_RUNS:
            raise ValueError(f"study expands to {count} runs; maximum is {MAX_STUDY_RUNS}")
        # Validate even the last cell before the caller starts any simulation or export.
        self.expand()

    def expand(self) -> tuple[RunConfig, ...]:
        axes = sorted(self.grid, key=lambda item: AXIS_ORDER.index(item[0]))
        names = [key for key, _ in axes]
        cells = []
        for values in itertools.product(*(values for _, values in axes)):
            changes: dict[str, Any] = dict(zip(names, values, strict=True))
            cells.append(replace(self.base_config, **changes))
        return tuple(cells)

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "base_config": self.base_config.as_dict(),
            "grid": dict(self.grid),
        }

    @classmethod
    def from_dict(cls, payload: Any) -> StudyConfig:
        if not isinstance(payload, dict):
            raise ValueError("study configuration root must be a JSON object")
        if set(payload) != {"schema_version", "base_config", "grid"}:
            raise ValueError("study requires exactly schema_version, base_config, and grid")
        grid = payload["grid"]
        if not isinstance(grid, dict):
            raise ValueError("grid must be an object of axis names and value arrays")
        for key, values in grid.items():
            if not isinstance(values, list):
                raise ValueError(f"grid.{key} must be an array")
        return cls(
            base_config=_strict_config(payload["base_config"]),
            grid=tuple((key, tuple(values)) for key, values in sorted(grid.items())),
            schema_version=payload["schema_version"],
        )


def load_study(path: str | Path) -> StudyConfig:
    return StudyConfig.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))
