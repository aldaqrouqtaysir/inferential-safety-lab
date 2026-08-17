"""Stable domain-separated random-stream derivation."""

from __future__ import annotations

import hashlib
from typing import Any

import numpy as np

from .serialization import canonical_bytes

BIT_GENERATOR_ID = "numpy.random.PCG64"
SEED_SCHEMA = "inferential_safety_lab.seed.v1"
_SEED_PROTOCOL = b"inferential-safety-lab/seed-derivation/v1\x00"


def derive_seed(master_seed: int, domain: str, *parts: Any) -> int:
    """Derive one replayable 128-bit seed without sharing mutable RNG state."""

    if isinstance(master_seed, bool) or not isinstance(master_seed, int):
        raise TypeError("master_seed must be an integer")
    if master_seed < 0:
        raise ValueError("master_seed must be non-negative")
    if not isinstance(domain, str) or not domain:
        raise ValueError("seed domain must be a non-empty string")
    payload = canonical_bytes(
        {"schema": SEED_SCHEMA, "master_seed": master_seed, "domain": domain, "parts": parts}
    )
    return int.from_bytes(hashlib.sha256(_SEED_PROTOCOL + payload).digest()[:16], "big")


def rng_for(master_seed: int, domain: str, *parts: Any) -> np.random.Generator:
    return np.random.Generator(np.random.PCG64(derive_seed(master_seed, domain, *parts)))
