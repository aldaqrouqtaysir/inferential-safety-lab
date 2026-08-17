from __future__ import annotations

import ast
import re
import socket
import subprocess
from pathlib import Path
from urllib.parse import parse_qsl, unquote, urlsplit

import pytest

ROOT = Path(__file__).parents[2]
_GITHUB_COMPONENT = re.compile(r"[A-Za-z0-9_.-]+")
_WINDOWS_DRIVE_PATH = re.compile(r"^[A-Za-z]:[\\/]")
_GITHUB_SCP_REMOTE = re.compile(r"^git@github\.com:(?P<path>[^?#]+)$", re.IGNORECASE)
_CREDENTIAL_QUERY_KEYS = {
    "access_token",
    "auth",
    "credential",
    "key",
    "password",
    "signature",
    "token",
}


def _github_path_safety_reason(path: str) -> str | None:
    decoded = unquote(path)
    if decoded != path:
        return "percent-encoded repository paths are not normal GitHub remotes"
    components = decoded.strip("/").split("/")
    if len(components) != 2:
        return "GitHub remotes must identify exactly one owner and repository"
    owner, repository = components
    if repository.endswith(".git"):
        repository = repository[:-4]
    if not repository or not all(_GITHUB_COMPONENT.fullmatch(item) for item in (owner, repository)):
        return "GitHub owner or repository contains unsupported characters"
    if "n3-inferential-safety-spike" in repository.lower():
        return "historical N3 repository paths are forbidden"
    return None


def _remote_safety_reason(remote_url: str) -> str | None:
    value = remote_url.strip()
    lowered = value.lower()
    if not value or any(character in value for character in "\r\n\x00"):
        return "empty or control-character remote"
    if (
        lowered.startswith(("file://", "~/", "/home/", "/users/", "./", "../"))
        or value.startswith(("\\\\", "//"))
        or _WINDOWS_DRIVE_PATH.match(value)
    ):
        return "local filesystem and user-home remotes are forbidden"
    if "n3-inferential-safety-spike" in lowered:
        return "historical N3 repository paths are forbidden"

    scp_match = _GITHUB_SCP_REMOTE.fullmatch(value)
    if scp_match:
        return _github_path_safety_reason(scp_match.group("path"))

    parsed = urlsplit(value)
    if parsed.scheme not in {"https", "ssh"}:
        return "only normal GitHub HTTPS or SSH remotes are allowed"
    if (parsed.hostname or "").lower() != "github.com":
        return "remote host is not the approved public GitHub host"
    try:
        if parsed.port is not None:
            return "custom remote ports are not allowed"
    except ValueError:
        return "invalid remote port"
    if parsed.fragment:
        return "remote fragments are not allowed"
    if parsed.query:
        query_keys = {key.lower() for key, _ in parse_qsl(parsed.query, keep_blank_values=True)}
        if query_keys.intersection(_CREDENTIAL_QUERY_KEYS):
            return "credential query parameters are forbidden"
        return "query parameters are not normal GitHub remotes"
    if parsed.scheme == "https":
        if parsed.username is not None or parsed.password is not None:
            return "embedded HTTPS credentials are forbidden"
    elif parsed.username != "git" or parsed.password is not None:
        return "GitHub SSH remotes must use the credential-free git user"
    return _github_path_safety_reason(parsed.path)


def _unsafe_remote_reasons(remote_urls: list[str]) -> list[str]:
    return [reason for url in remote_urls if (reason := _remote_safety_reason(url)) is not None]


def _repository_remote_urls() -> list[str]:
    if not (ROOT / ".git").exists():
        return []
    names = subprocess.run(
        ["git", "remote"], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.splitlines()
    urls: list[str] = []
    for name in names:
        for mode in ((), ("--push",)):
            result = subprocess.run(
                ["git", "remote", "get-url", *mode, "--all", name],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            urls.extend(result.stdout.splitlines())
    return list(dict.fromkeys(urls))


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


@pytest.mark.parametrize(
    "remote_url",
    [
        "https://github.com/example-user/inferential-safety-lab.git",
        "git@github.com:example-user/inferential-safety-lab.git",
        "ssh://git@github.com/example-user/inferential-safety-lab.git",
    ],
)
def test_public_remote_safety_predicate_allows_normal_github_remotes(remote_url: str) -> None:
    assert _remote_safety_reason(remote_url) is None


def test_public_remote_safety_predicate_allows_no_remote() -> None:
    assert _unsafe_remote_reasons([]) == []


@pytest.mark.parametrize(
    "remote_url",
    [
        "https://oauth-token@github.com/example-user/inferential-safety-lab.git",
        "https://user:password@github.com/example-user/inferential-safety-lab.git",
        "https://github.com/example-user/inferential-safety-lab.git?token=secret",
        "file:///home/example/inferential-safety-lab",
        r"C:\Users\example\inferential-safety-lab",
        "/home/example/inferential-safety-lab",
        "https://git.example.internal/example-user/inferential-safety-lab.git",
        "../inferential-safety-lab",
        "https://github.com/example-user/n3-inferential-safety-spike.git",
    ],
)
def test_public_remote_safety_predicate_rejects_private_or_credentialed_remotes(
    remote_url: str,
) -> None:
    assert _remote_safety_reason(remote_url) is not None


@pytest.mark.privacy
def test_public_repository_has_only_sanitized_public_remotes() -> None:
    reasons = _unsafe_remote_reasons(_repository_remote_urls())
    assert not reasons, "unsafe Git remote configuration: " + "; ".join(
        f"remote URL #{index + 1}: {reason}" for index, reason in enumerate(reasons)
    )
