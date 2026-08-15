from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from mcpaxe import cli


def _session_log_with(tool_names: list[str]) -> str:
    ts = datetime.now(timezone.utc).isoformat()
    return "\n".join(
        json.dumps(
            {
                "timestamp": ts,
                "message": {"content": [{"type": "tool_use", "name": name, "input": {}}]},
            }
        )
        for name in tool_names
    )


def test_version(capsys):
    assert cli.main(["version"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("mcpaxe ")


def test_audit_json_end_to_end(write_config, ok_entry, capsys):
    cfg = write_config(
        {
            "healthy": ok_entry,
            "remote": {"type": "http", "url": "https://mcp.example.com"},
            "broken": {"command": "definitely-not-a-real-command-xyz-123", "args": []},
        }
    )
    assert cli.main(["--config", str(cfg), "--json", "--no-color"]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["exact"] in (True, False)
    assert payload["totals"]["tools"] == 10
    assert payload["totals"]["tokens_per_turn"] > 0

    servers = {s["name"]: s for s in payload["servers"]}
    assert servers["healthy"]["status"] == "ok"
    assert servers["healthy"]["tools"] == 10
    assert servers["healthy"]["grade"] in "ABCDEF"
    assert servers["remote"]["status"] == "skipped-http"
    assert servers["broken"]["status"] == "error"


def test_audit_renders_human_table(write_config, ok_entry, capsys):
    cfg = write_config({"healthy": ok_entry})
    assert cli.main(["--config", str(cfg), "--no-color", "--verbose"]) == 0
    out = capsys.readouterr().out
    assert "healthy" in out
    assert "describe_things" in out  # verbose per-tool table


def test_audit_no_configs(monkeypatch, capsys):
    from mcpaxe import config

    monkeypatch.setattr(config, "discover", lambda **kwargs: [])
    assert cli.main([]) == 2
    assert "no MCP configs found" in capsys.readouterr().out


def test_usage_json(monkeypatch, tmp_path, capsys):
    from mcpaxe import usage

    root = tmp_path / "projects"
    root.mkdir()
    (root / "s.jsonl").write_text(_session_log_with(["mcp__github__x", "mcp__github__x"]) + "\n")
    monkeypatch.setattr(usage, "default_root", lambda: root)

    assert cli.main(["usage", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["server_calls"] == {"github": 2}


def test_slim_removes_unused_servers(write_config, ok_entry, monkeypatch, tmp_path, capsys):
    from mcpaxe import usage

    root = tmp_path / "projects"
    root.mkdir()
    (root / "s.jsonl").write_text(_session_log_with(["mcp__used-one__tool"]) + "\n")
    monkeypatch.setattr(usage, "default_root", lambda: root)

    out_dir = tmp_path / "out"
    cfg = write_config(
        {
            "used-one": ok_entry,
            "never-used": {
                "command": sys.executable,
                "args": [str(Path(__file__).parent / "fixtures" / "fake_server.py")],
            },
        },
        name="claude.json",
    )
    assert cli.main(["slim", "--config", str(cfg), "--out", str(out_dir), "--no-color"]) == 0
    out = capsys.readouterr().out

    slim_path = out_dir / "claude-slim.json"
    assert slim_path.exists()
    slimmed = json.loads(slim_path.read_text(encoding="utf-8"))
    assert list(slimmed["mcpServers"]) == ["used-one"]
    assert "remove" in out and "never-used" in out
    assert "tokens/turn" in out
