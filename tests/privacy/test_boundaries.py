from __future__ import annotations

import ast
import socket
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[2]


def test_streamlit_has_no_upload_url_or_external_data_widgets() -> None:
    source = (ROOT / "src/inferential_safety_lab/ui/app.py").read_text(encoding="utf-8")
    forbidden = ("file_uploader", "url_input", "read_csv", "read_excel", "requests.")
    assert all(token not in source for token in forbidden)


def test_methods_cannot_import_evaluator_truth_or_metrics() -> None:
    methods = ROOT / "src/inferential_safety_lab/methods"
    forbidden = ("inferential_safety_lab.core.dgp", "inferential_safety_lab.metrics")
    for path in methods.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imported = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.append(node.module)
        assert not any(name.startswith(forbidden) for name in imported), path


def test_network_guard_is_active() -> None:
    with pytest.raises(AssertionError, match="unexpected network"):
        socket.create_connection(("example.com", 443))


def test_no_historical_result_artifacts_or_old_git_history() -> None:
    forbidden_names = {
        "final_decision.canonical.json",
        "TERMINAL_DECISION.txt",
        "confirmatory",
        "selector_results.csv",
    }
    paths = {
        path.name
        for path in ROOT.rglob("*")
        if ".git" not in path.parts and ".venv" not in path.parts
    }
    assert not paths.intersection(forbidden_names)
    assert not (ROOT / ".git/refs/remotes").exists()
