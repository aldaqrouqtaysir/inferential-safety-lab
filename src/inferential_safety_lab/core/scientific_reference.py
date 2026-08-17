"""Typed comparison for the cross-platform scientific reference contract."""

from __future__ import annotations

import math
from numbers import Integral, Real
from typing import Any

SCIENTIFIC_RTOL = 1.0e-12
SCIENTIFIC_ATOL = 1.0e-12

_NONSCIENTIFIC_TOP_LEVEL_KEYS = {
    "environment",
    "replay_hash",
    "runtime_diagnostics",
    "timing",
}
_NONSCIENTIFIC_TIMING_KEYS = {
    "runtime_seconds",
    "wall_seconds",
    "repetitions_per_second",
    "median_runtime_seconds",
}


class ScientificReferenceMismatch(AssertionError):
    """Raised with the first exact scientific path that violates the contract."""


def _pointer(parent: str, key: str) -> str:
    escaped = key.replace("~", "~0").replace("/", "~1")
    return f"{parent}/{escaped}"


def _scientific_projection(value: Any, *, top_level: bool = False) -> Any:
    if isinstance(value, dict):
        projected = {}
        for key, child in value.items():
            if not isinstance(key, str):
                raise ScientificReferenceMismatch("/: scientific mappings require string keys")
            if top_level and key in _NONSCIENTIFIC_TOP_LEVEL_KEYS:
                continue
            if key in _NONSCIENTIFIC_TIMING_KEYS:
                continue
            projected[key] = _scientific_projection(child)
        return projected
    if isinstance(value, (list, tuple)):
        return [_scientific_projection(child) for child in value]
    return value


def _mismatch(path: str, message: str) -> None:
    raise ScientificReferenceMismatch(f"{path or '/'}: {message}")


def _compare(expected: Any, actual: Any, path: str, *, rtol: float, atol: float) -> None:
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            _mismatch(path, f"expected object, received {type(actual).__name__}")
        expected_keys = set(expected)
        actual_keys = set(actual)
        if expected_keys != actual_keys:
            missing = sorted(expected_keys - actual_keys)
            extra = sorted(actual_keys - expected_keys)
            _mismatch(path, f"scientific path identity differs; missing={missing}, extra={extra}")
        for key in sorted(expected):
            _compare(expected[key], actual[key], _pointer(path, key), rtol=rtol, atol=atol)
        return

    if isinstance(expected, list):
        if not isinstance(actual, list):
            _mismatch(path, f"expected array, received {type(actual).__name__}")
        if len(expected) != len(actual):
            _mismatch(path, f"array length differs; expected={len(expected)}, actual={len(actual)}")
        for index, (expected_child, actual_child) in enumerate(zip(expected, actual, strict=True)):
            _compare(
                expected_child,
                actual_child,
                _pointer(path, str(index)),
                rtol=rtol,
                atol=atol,
            )
        return

    if expected is None:
        if actual is not None:
            _mismatch(path, f"expected null, received {actual!r}")
        return

    if isinstance(expected, bool):
        if not isinstance(actual, bool) or actual is not expected:
            _mismatch(path, f"boolean differs; expected={expected!r}, actual={actual!r}")
        return

    if isinstance(expected, int):
        if isinstance(actual, bool) or not isinstance(actual, Integral):
            _mismatch(path, f"expected integer, received {type(actual).__name__}")
        if int(actual) != expected:
            _mismatch(path, f"integer differs; expected={expected}, actual={int(actual)}")
        return

    if isinstance(expected, float):
        if isinstance(actual, (bool, Integral)) or not isinstance(actual, Real):
            _mismatch(path, f"expected finite float, received {type(actual).__name__}")
        expected_float = float(expected)
        actual_float = float(actual)
        if not math.isfinite(expected_float) or not math.isfinite(actual_float):
            _mismatch(
                path,
                f"non-finite floats are forbidden; expected={expected_float!r}, actual={actual_float!r}",
            )
        if not math.isclose(actual_float, expected_float, rel_tol=rtol, abs_tol=atol):
            absolute = abs(actual_float - expected_float)
            scale = max(abs(actual_float), abs(expected_float))
            relative = absolute / scale if scale else 0.0
            _mismatch(
                path,
                "float exceeds portability tolerance; "
                f"expected={expected_float!r}, actual={actual_float!r}, "
                f"absolute_difference={absolute:.17g}, relative_difference={relative:.17g}, "
                f"rtol={rtol:.1e}, atol={atol:.1e}",
            )
        return

    if isinstance(expected, str):
        if not isinstance(actual, str):
            _mismatch(path, f"expected string, received {type(actual).__name__}")
        if actual != expected:
            _mismatch(path, f"string differs; expected={expected!r}, actual={actual!r}")
        return

    _mismatch(path, f"unsupported reference type {type(expected).__name__}")


def assert_scientific_reference(
    expected: dict[str, Any],
    actual: dict[str, Any],
    *,
    rtol: float = SCIENTIFIC_RTOL,
    atol: float = SCIENTIFIC_ATOL,
) -> None:
    """Require exact scientific structure/states and bounded finite floats.

    Environment identity, raw replay hashes, and timing fields are intentionally
    outside this cross-platform comparison. Signed zeros are scientifically
    equivalent; canonical serialization separately normalizes them to ``0.0``.
    """

    if rtol < 0.0 or atol < 0.0 or not math.isfinite(rtol) or not math.isfinite(atol):
        raise ValueError("scientific tolerances must be finite and non-negative")
    expected_scientific = _scientific_projection(expected, top_level=True)
    actual_scientific = _scientific_projection(actual, top_level=True)
    _compare(expected_scientific, actual_scientific, "", rtol=rtol, atol=atol)
