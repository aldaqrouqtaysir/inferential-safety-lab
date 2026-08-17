"""Compact method, aggregate, and service result schemas."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .failures import FailureCode

RESULT_SCHEMA_VERSION = "inferential_safety_lab.aggregate.v1"


@dataclass(frozen=True, slots=True)
class FitOutcome:
    valid: bool
    failure_code: FailureCode
    point_estimate: float | None
    interval_lower: float | None
    interval_upper: float | None
    n_observations: int
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class PreprocessOutcome:
    data: Any | None
    valid: bool
    failure_code: FailureCode
    retained_row_count: int
    filled_missing_count: int
    changed_observed_count: int
    explicit_deletion_count: int
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class MethodResult:
    method_id: str
    preprocessing_id: str
    estimator_id: str
    attempt_count: int
    fit_valid: bool
    fit_failure_code: FailureCode
    point_estimate_available: bool
    point_estimate: float | None
    interval_computed: bool
    interval_scientifically_applicable: bool
    interval_unavailability_reason: str | None
    interval_lower: float | None
    interval_upper: float | None
    retained_row_count: int
    retained_row_fraction: float
    filled_missing_count: int
    filled_missing_fraction: float
    changed_observed_count: int
    changed_observed_fraction: float
    explicit_deletion_count: int
    explicit_deletion_fraction: float
    runtime_seconds: float
    warnings: tuple[str, ...]
    provenance: dict[str, str]


@dataclass(frozen=True, slots=True)
class LabRun:
    aggregate: dict[str, Any]
    canonical_json: str
    replay_hash: str
    runtime_diagnostics: dict[str, Any]
