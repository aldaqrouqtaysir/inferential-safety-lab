"""Versioned, bounded configuration model."""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

CONFIG_SCHEMA_VERSION = "inferential_safety_lab.config.v1"
ALLOWED_SAMPLE_SIZES = (100, 150, 300, 500)
ALLOWED_EFFECTS = (0.0, 0.25, 0.5)


class ScenarioId(StrEnum):
    MCAR_SMALL_EFFECTIVE_SAMPLE = "MCAR_SMALL_EFFECTIVE_SAMPLE"
    OUTCOME_DEPENDENT_MAR = "OUTCOME_DEPENDENT_MAR"
    GROSS_CONTAMINATION = "GROSS_CONTAMINATION"


@dataclass(frozen=True, slots=True)
class RunConfig:
    schema_version: str
    scenario_id: ScenarioId
    sample_size: int
    tau: float
    repetitions: int
    master_seed: int
    missingness_rate: float
    contamination_fraction: float
    contamination_displacement: float
    confidence_level: float
    winsorization_limits: tuple[float, float]

    def __post_init__(self) -> None:
        if self.schema_version != CONFIG_SCHEMA_VERSION:
            raise ValueError(f"schema_version must be {CONFIG_SCHEMA_VERSION!r}")
        if self.sample_size not in ALLOWED_SAMPLE_SIZES:
            raise ValueError(f"sample_size must be one of {ALLOWED_SAMPLE_SIZES}")
        if self.tau not in ALLOWED_EFFECTS:
            raise ValueError(f"tau must be one of {ALLOWED_EFFECTS}")
        if not (80 <= self.repetitions <= 160 or 300 <= self.repetitions <= 500):
            raise ValueError("repetitions must be Quick (80-160) or Reference (300-500)")
        if isinstance(self.master_seed, bool) or self.master_seed < 0:
            raise ValueError("master_seed must be a non-negative integer")
        if not 0.0 < self.confidence_level < 1.0:
            raise ValueError("confidence_level must lie strictly between zero and one")
        lower, upper = self.winsorization_limits
        if not all(math.isfinite(value) for value in (lower, upper)) or lower >= upper:
            raise ValueError("winsorization_limits must be finite and increasing")
        if self.scenario_id is ScenarioId.MCAR_SMALL_EFFECTIVE_SAMPLE:
            if self.missingness_rate not in (0.5, 0.6, 0.7):
                raise ValueError("MCAR missingness_rate must be 0.50, 0.60, or 0.70")
        elif self.scenario_id is ScenarioId.OUTCOME_DEPENDENT_MAR:
            if not 0.15 <= self.missingness_rate <= 0.45:
                raise ValueError("MAR missingness_rate must be in [0.15, 0.45]")
        else:
            if not 0.01 <= self.contamination_fraction <= 0.15:
                raise ValueError("contamination_fraction must be in [0.01, 0.15]")
            if not 4.0 <= self.contamination_displacement <= 12.0:
                raise ValueError("contamination_displacement must be in [4, 12]")

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> RunConfig:
        allowed = {field for field in cls.__dataclass_fields__}
        extra = set(payload) - allowed
        missing = allowed - set(payload)
        if extra:
            raise ValueError(f"unexpected configuration fields: {sorted(extra)}")
        if missing:
            raise ValueError(f"missing configuration fields: {sorted(missing)}")
        values = dict(payload)
        values["scenario_id"] = ScenarioId(values["scenario_id"])
        limits = values["winsorization_limits"]
        if not isinstance(limits, (list, tuple)) or len(limits) != 2:
            raise ValueError("winsorization_limits must contain exactly two values")
        values["winsorization_limits"] = (float(limits[0]), float(limits[1]))
        return cls(**values)


def load_config(path: str | Path) -> RunConfig:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("configuration root must be a JSON object")
    return RunConfig.from_dict(payload)
