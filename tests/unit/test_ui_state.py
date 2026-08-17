from __future__ import annotations

from dataclasses import replace
from typing import Any

from inferential_safety_lab.core.configuration import ScenarioId
from inferential_safety_lab.services.presets import get_preset
from inferential_safety_lab.services.run_lab import run_lab
from inferential_safety_lab.ui.state import (
    REQUIRED_UI_STATE_KEYS,
    config_fingerprint,
    has_stale_result,
    initialize_ui_state,
    mark_complete,
    mark_error,
    mark_running,
    store_draft,
)


def test_ui_state_contract_is_complete_and_deterministic() -> None:
    config = get_preset(ScenarioId.MCAR_SMALL_EFFECTIVE_SAMPLE)
    state: dict[str, Any] = {}
    initialize_ui_state(state, config)
    assert set(REQUIRED_UI_STATE_KEYS).issubset(state)
    assert state["draft_config"] == config
    assert state["draft_fingerprint"] == config_fingerprint(config)
    assert state["last_run"] is None
    assert state["last_run_config"] is None
    assert state["last_run_fingerprint"] is None
    assert state["status"] == "idle"


def test_saved_result_remains_immutable_while_draft_changes() -> None:
    completed_config = get_preset(ScenarioId.MCAR_SMALL_EFFECTIVE_SAMPLE)
    run = run_lab(completed_config)
    state: dict[str, Any] = {}
    initialize_ui_state(state, completed_config)
    mark_running(state, completed_config)
    mark_complete(state, run, completed_config)

    changed_draft = replace(completed_config, sample_size=300)
    store_draft(state, changed_draft)

    assert has_stale_result(state)
    assert state["last_run"] is run
    assert state["last_run_config"] == completed_config
    assert state["last_run_fingerprint"] == config_fingerprint(completed_config)
    assert state["draft_config"] == changed_draft


def test_recoverable_error_keeps_last_completed_result() -> None:
    config = get_preset(ScenarioId.MCAR_SMALL_EFFECTIVE_SAMPLE)
    run = run_lab(config)
    state: dict[str, Any] = {}
    initialize_ui_state(state, config)
    mark_complete(state, run, config)
    mark_running(state, config)
    mark_error(state, "example failure")

    assert state["status"] == "error"
    assert state["error_message"] == "example failure"
    assert state["last_run"] is run
    assert state["last_run_config"] == config
