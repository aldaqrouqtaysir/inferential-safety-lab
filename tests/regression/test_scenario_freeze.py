from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from inferential_safety_lab.core.configuration import ScenarioId
from inferential_safety_lab.services.presets import get_preset
from inferential_safety_lab.services.run_lab import run_lab


def _availability(run: object, method_id: str) -> float:
    aggregate = run.aggregate  # type: ignore[attr-defined]
    row = next(item for item in aggregate["method_metrics"] if item["method_id"] == method_id)
    return float(row["interval_availability"])


@pytest.mark.regression
def test_prospective_candidate_rule_freezes_lowest_qualifying_rate() -> None:
    base = get_preset(ScenarioId.MCAR_SMALL_EFFECTIVE_SAMPLE)
    qualifying = []
    for rate in (0.50, 0.60, 0.70):
        run = run_lab(replace(base, missingness_rate=rate))
        guarded = _availability(run, "guarded_deletion_ols_hc3")
        complete = _availability(run, "complete_case_ols_hc3")
        burden = max(
            float(row["mean_explicit_deletion_fraction"]) for row in run.aggregate["method_metrics"]
        )
        if 0.20 <= guarded <= 0.80 and complete - guarded >= 0.20 and burden >= 0.30:
            qualifying.append(rate)
    assert qualifying and min(qualifying) == 0.60


@pytest.mark.regression
def test_held_out_seed_direction_visible_in_at_least_two_blocks() -> None:
    base = get_preset(ScenarioId.MCAR_SMALL_EFFECTIVE_SAMPLE)
    visible = 0
    for seed in (2026081702, 2026081703, 2026081704):
        run = run_lab(replace(base, master_seed=seed))
        gap = _availability(run, "complete_case_ols_hc3") - _availability(
            run, "guarded_deletion_ols_hc3"
        )
        visible += gap >= 0.20
    assert visible >= 2


@pytest.mark.regression
def test_public_provenance_records_portable_release_invariants() -> None:
    provenance = (Path(__file__).parents[2] / "docs" / "public-provenance.md").read_text(
        encoding="utf-8"
    )
    normalized = " ".join(provenance.split())
    assert "explicitly allowlisted source tree" in normalized
    assert "not a simulated or backdated development history" in normalized
    assert "Private repository metadata" in normalized
    assert "earlier Git history" in normalized
    assert "were not copied" in normalized
    assert "184 numeric leaves" in normalized
    assert "ab232be3ea0d25ceb4e1459be82ac34760237d565df875aea89250a869a905aa" in normalized
