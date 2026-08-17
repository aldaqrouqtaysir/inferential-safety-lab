from __future__ import annotations

import socket

import pytest


@pytest.fixture(autouse=True)
def block_unexpected_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Core and reporting tests must remain offline after installation."""

    def blocked(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise AssertionError("unexpected network access")

    monkeypatch.setattr(socket, "create_connection", blocked)
