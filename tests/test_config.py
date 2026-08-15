from __future__ import annotations

import json
from pathlib import Path

import pytest

from mcpaxe import config


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_discover_finds_all_hosts(tmp_path):
    home, cwd = tmp_path / "home", tmp_path / "cwd"
    _write_json(
        home / ".claude.json",
        {"mcpServers": {"global-one": {"command": "npx", "args": ["-y", "server-a"]}}},
    )
    _write_json(
        home / ".cursor" / "mcp.json",
        {"mcpServers": {"cursor-one": {"command": "node", "args": ["server.js"]}}},
    )
    _write_json(
        home / ".codeium" / "windsurf" / "mcp_config.json",
        {"mcpServers": {"windsurf-one": {"command": "uvx", "args": ["server-b"]}}},
    )
    _write_json(
        cwd / ".mcp.json", {"mcpServers": {"project-one": {"command": "go", "args": ["run", "."]}}}
    )

    hosts = config.discover(home=home, cwd=cwd)
    assert [h.host_id for h in hosts] == [
        "claude-code",
        "cursor",
        "windsurf",
        "project",
    ]


def test_discover_skips_missing_or_empty(tmp_path):
    hosts = config.discover(home=tmp_path / "nowhere", cwd=tmp_path / "nowhere")
    assert hosts == []


def test_claude_code_project_labels(tmp_path):
    home = tmp_path / "home"
    _write_json(
        home / ".claude.json",
        {
            "projects": {
                "/code/website": {"mcpServers": {"web-one": {"command": "b"}}},
                "/code/scratch": {},
            }
        },
    )
    hosts = config.discover(home=home, cwd=tmp_path)
    assert len(hosts) == 1
    assert hosts[0].host_id == "claude-code-project"
    assert "website" in hosts[0].label


def test_stdio_spec_parsing(tmp_path):
    home = tmp_path / "home"
    path = _write_json(
        home / ".claude.json",
        {
            "mcpServers": {
                "mixed": {
                    "command": "npx",
                    "args": ["-y", "@example/server"],
                    "env": {"API_KEY": "abc", "HOME_DIR": "${HOME}"},
                }
            }
        },
    )
    (host,) = config.discover(home=home, cwd=tmp_path)
    (spec,) = config.specs_for_host(host)
    assert spec.transport == "stdio"
    assert spec.command == "npx"
    assert spec.args == ["-y", "@example/server"]
    assert spec.env["API_KEY"] == "abc"
    assert spec.source_path == path


def test_url_and_invalid_specs(tmp_path):
    home = tmp_path / "home"
    _write_json(
        home / ".cursor" / "mcp.json",
        {
            "mcpServers": {
                "remote": {"type": "http", "url": "https://mcp.example.com/sse"},
                "broken": {"command": None},
                "notadict": "oops",
            }
        },
    )
    (host,) = config.discover(home=home, cwd=tmp_path)
    specs = {s.name: s for s in config.specs_for_host(host)}
    assert specs["remote"].transport == "http"
    assert specs["remote"].url == "https://mcp.example.com/sse"
    assert specs["broken"].transport == config.INVALID_TRANSPORT
    assert "notadict" not in specs


def test_load_custom_config(tmp_path):
    path = _write_json(tmp_path / "custom.json", {"mcpServers": {"one": {"command": "x"}}})
    host = config.load_custom_config(path)
    assert host.host_id == "custom"
    assert "one" in host.servers

    empty = _write_json(tmp_path / "empty.json", {"nope": True})
    with pytest.raises(SystemExit):
        config.load_custom_config(empty)
