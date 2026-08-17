"""Availability and binomial interval helpers."""

from __future__ import annotations

import math
from statistics import NormalDist


def wilson_interval(
    successes: int, total: int, confidence_level: float = 0.95
) -> tuple[float | None, float | None]:
    if successes < 0 or total < 0 or successes > total:
        raise ValueError("successes must lie in [0, total]")
    if not total:
        return None, None
    z = NormalDist().inv_cdf((1.0 + confidence_level) / 2.0)
    proportion = successes / total
    denominator = 1.0 + z * z / total
    center = (proportion + z * z / (2.0 * total)) / denominator
    half = (
        z
        * math.sqrt(proportion * (1.0 - proportion) / total + z * z / (4.0 * total * total))
        / denominator
    )
    return max(0.0, center - half), min(1.0, center + half)
