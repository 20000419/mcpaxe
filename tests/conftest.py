from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


def fake_server_args(*extra: str) -> list[str]:
    return [str(FIXTURES / "fake_server.py"), *extra]


@pytest.fixture
def write_config(tmp_path):
    """Return a helper writing a config file with the given mcpServers map."""

    def _write(servers: dict, name: str = "config.json") -> Path:
        path = tmp_path / name
        path.write_text(json.dumps({"mcpServers": servers}, indent=2), encoding="utf-8")
        return path

    return _write


@pytest.fixture
def ok_entry():
    return {
        "command": sys.executable,
        "args": fake_server_args(),
        "env": {"FAKE_SERVER": "1"},
    }
