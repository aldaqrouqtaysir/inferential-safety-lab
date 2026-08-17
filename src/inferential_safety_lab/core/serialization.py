"""Canonical JSON serialization and domain-separated SHA-256 hashes."""

from __future__ import annotations

import dataclasses
import enum
import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np

_HASH_PROTOCOL = b"inferential-safety-lab/stable-hash/v1\x00"


def canonicalize(value: Any) -> Any:
    """Return a deterministic, human-readable JSON-compatible representation."""

    if value is None or isinstance(value, (bool, str)):
        return value
    if isinstance(value, (int, np.integer)) and not isinstance(value, bool):
        return int(value)
    if isinstance(value, (float, np.floating)):
        number = float(value)
        if not math.isfinite(number):
            return None
        return 0.0 if number == 0.0 else number
    if isinstance(value, enum.Enum):
        return canonicalize(value.value)
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {
            field.name: canonicalize(getattr(value, field.name))
            for field in dataclasses.fields(value)
        }
    if isinstance(value, Mapping):
        if not all(isinstance(key, str) for key in value):
            raise TypeError("canonical mappings require string keys")
        return {key: canonicalize(value[key]) for key in sorted(value)}
    if isinstance(value, np.ndarray):
        return canonicalize(value.tolist())
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        return [canonicalize(item) for item in value]
    raise TypeError(f"unsupported canonical serialization type: {type(value)!r}")


def canonical_json(value: Any) -> str:
    """Serialize with sorted keys, UTF-8 characters, and no insignificant space."""

    return json.dumps(
        canonicalize(value),
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def canonical_bytes(value: Any) -> bytes:
    return canonical_json(value).encode("utf-8")


def stable_hash(value: Any, *, domain: str) -> str:
    """Hash a canonical payload with explicit domain separation."""

    if not domain:
        raise ValueError("hash domain must be non-empty")
    domain_bytes = domain.encode("utf-8")
    payload = canonical_bytes(value)
    digest = hashlib.sha256()
    digest.update(_HASH_PROTOCOL)
    digest.update(len(domain_bytes).to_bytes(4, "big"))
    digest.update(domain_bytes)
    digest.update(len(payload).to_bytes(8, "big"))
    digest.update(payload)
    return digest.hexdigest()
