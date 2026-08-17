"""Immutable evaluator truth and capability-limited observed analysis data."""

from __future__ import annotations

from dataclasses import dataclass, fields
from typing import Any

import numpy as np
from numpy.typing import NDArray

IntArray = NDArray[np.int64]
BinaryArray = NDArray[np.int8]
FloatArray = NDArray[np.float64]
BoolArray = NDArray[np.bool_]


def _frozen_1d(value: Any, dtype: Any) -> Any:
    copied = np.array(value, dtype=dtype, copy=True, order="C")
    if copied.ndim != 1:
        raise ValueError("dataset arrays must be one-dimensional")
    frozen = np.frombuffer(copied.tobytes(order="C"), dtype=copied.dtype)
    frozen.setflags(write=False)
    return frozen


@dataclass(frozen=True, slots=True, eq=False)
class ObservedData:
    """The complete and only capability passed to practical methods."""

    row_id: IntArray
    treatment: BinaryArray
    outcome: FloatArray
    observed_z: FloatArray

    def __post_init__(self) -> None:
        object.__setattr__(self, "row_id", _frozen_1d(self.row_id, np.int64))
        object.__setattr__(self, "treatment", _frozen_1d(self.treatment, np.int8))
        object.__setattr__(self, "outcome", _frozen_1d(self.outcome, np.float64))
        object.__setattr__(self, "observed_z", _frozen_1d(self.observed_z, np.float64))
        lengths = {len(self.row_id), len(self.treatment), len(self.outcome), len(self.observed_z)}
        if len(lengths) != 1 or not self.row_id.size:
            raise ValueError("observed arrays must have one equal, positive length")
        if len(np.unique(self.row_id)) != len(self.row_id):
            raise ValueError("row_id must be unique")
        if not np.isin(self.treatment, (0, 1)).all():
            raise ValueError("treatment must contain only 0 and 1")
        if not np.isfinite(self.outcome).all() or np.isinf(self.observed_z).any():
            raise ValueError("outcome must be finite and observed_z cannot be infinite")

    @property
    def n(self) -> int:
        return len(self.row_id)

    @property
    def field_names(self) -> tuple[str, ...]:
        return tuple(field.name for field in fields(self))

    def subset(self, mask: NDArray[np.bool_]) -> ObservedData:
        if mask.shape != (self.n,):
            raise ValueError("row mask must align with observed data")
        return ObservedData(
            self.row_id[mask], self.treatment[mask], self.outcome[mask], self.observed_z[mask]
        )

    def with_z(self, values: Any) -> ObservedData:
        return ObservedData(self.row_id, self.treatment, self.outcome, values)


@dataclass(frozen=True, slots=True, eq=False)
class EvaluatorTruth:
    """Clean latent data and estimand; never passed to practical methods."""

    row_id: IntArray
    latent_z: FloatArray
    treatment: BinaryArray
    epsilon: FloatArray
    y0: FloatArray
    y1: FloatArray
    outcome: FloatArray
    propensity: FloatArray
    tau: float
    known_target_effect: float

    def __post_init__(self) -> None:
        for name, dtype in (
            ("row_id", np.int64),
            ("latent_z", np.float64),
            ("treatment", np.int8),
            ("epsilon", np.float64),
            ("y0", np.float64),
            ("y1", np.float64),
            ("outcome", np.float64),
            ("propensity", np.float64),
        ):
            object.__setattr__(self, name, _frozen_1d(getattr(self, name), dtype))
        n = len(self.row_id)
        if n == 0 or any(
            len(getattr(self, name)) != n
            for name in ("latent_z", "treatment", "epsilon", "y0", "y1", "outcome", "propensity")
        ):
            raise ValueError("truth arrays must have one equal, positive length")
        if self.known_target_effect != self.tau:
            raise ValueError("known_target_effect must equal tau")
        if not np.allclose(self.y1 - self.y0, self.tau + 0.5 * self.latent_z):
            raise ValueError("truth violates the heterogeneous effect equation")
        if not np.array_equal(self.outcome, np.where(self.treatment == 1, self.y1, self.y0)):
            raise ValueError("outcome does not match treatment-specific potential outcomes")

    @property
    def n(self) -> int:
        return len(self.row_id)

    def clean_observed(self) -> ObservedData:
        return ObservedData(self.row_id, self.treatment, self.outcome, self.latent_z)


@dataclass(frozen=True, slots=True, eq=False)
class CorruptionRecord:
    missing_mask: BoolArray
    contamination_mask: BoolArray
    mechanism_parameter: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "missing_mask", _frozen_1d(self.missing_mask, np.bool_))
        object.__setattr__(
            self, "contamination_mask", _frozen_1d(self.contamination_mask, np.bool_)
        )
        if len(self.missing_mask) != len(self.contamination_mask):
            raise ValueError("corruption masks must align")
