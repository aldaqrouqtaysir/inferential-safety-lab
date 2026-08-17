"""Explicit UI state contract for draft settings and immutable saved results."""

from __future__ import annotations

import hashlib
from collections.abc import MutableMapping
from typing import Any, Final, Literal, TypedDict

from inferential_safety_lab.core.configuration import RunConfig
from inferential_safety_lab.core.serialization import canonical_json
from inferential_safety_lab.domain.results import LabRun

UiStatus = Literal["idle", "running", "complete", "error"]


class UiProgress(TypedDict):
    completed: int
    total: int
    message: str


REQUIRED_UI_STATE_KEYS: Final[tuple[str, ...]] = (
    "draft_config",
    "draft_fingerprint",
    "status",
    "last_run",
    "last_run_config",
    "last_run_fingerprint",
    "progress",
    "error_message",
)


def config_fingerprint(config: RunConfig) -> str:
    """Hash only the canonical draft configuration for stale-result detection."""

    payload = canonical_json(config.as_dict()).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def initialize_ui_state(state: MutableMapping[str, Any], default_config: RunConfig) -> None:
    """Install the complete UI state contract without overwriting saved state."""

    state.setdefault("draft_config", default_config)
    state.setdefault("draft_fingerprint", config_fingerprint(state["draft_config"]))
    state.setdefault("status", "idle")
    state.setdefault("last_run", None)
    state.setdefault("last_run_config", None)
    state.setdefault("last_run_fingerprint", None)
    state.setdefault(
        "progress",
        UiProgress(completed=0, total=0, message="Ready to run an experiment."),
    )
    state.setdefault("error_message", None)


def store_draft(state: MutableMapping[str, Any], config: RunConfig) -> None:
    state["draft_config"] = config
    state["draft_fingerprint"] = config_fingerprint(config)


def mark_running(state: MutableMapping[str, Any], config: RunConfig) -> None:
    store_draft(state, config)
    state["status"] = "running"
    state["progress"] = UiProgress(
        completed=0,
        total=config.repetitions,
        message="Preparing synthetic samples…",
    )
    state["error_message"] = None


def update_progress(
    state: MutableMapping[str, Any], *, completed: int, total: int, message: str
) -> None:
    state["progress"] = UiProgress(completed=completed, total=total, message=message)


def mark_complete(
    state: MutableMapping[str, Any], run: LabRun, completed_config: RunConfig
) -> None:
    fingerprint = config_fingerprint(completed_config)
    state["last_run"] = run
    state["last_run_config"] = completed_config
    state["last_run_fingerprint"] = fingerprint
    state["status"] = "complete"
    state["progress"] = UiProgress(
        completed=completed_config.repetitions,
        total=completed_config.repetitions,
        message="Experiment complete. Your results are ready.",
    )
    state["error_message"] = None


def mark_error(state: MutableMapping[str, Any], message: str) -> None:
    state["status"] = "error"
    progress = state.get("progress", {})
    state["progress"] = UiProgress(
        completed=int(progress.get("completed", 0)),
        total=int(progress.get("total", 0)),
        message="The experiment stopped before a new result was saved.",
    )
    state["error_message"] = message


def has_stale_result(state: MutableMapping[str, Any]) -> bool:
    return bool(
        state.get("last_run") is not None
        and state.get("draft_fingerprint") != state.get("last_run_fingerprint")
    )
