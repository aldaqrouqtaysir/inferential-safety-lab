"""Runtime diagnostics kept outside the replay-stable aggregate."""

from __future__ import annotations

from statistics import median
from typing import Any

from inferential_safety_lab.domain.results import MethodResult


def runtime_summary(results: dict[str, list[MethodResult]]) -> dict[str, Any]:
    return {
        method_id: {
            "median_runtime_seconds": median(item.runtime_seconds for item in items),
            "attempts": len(items),
        }
        for method_id, items in results.items()
    }
