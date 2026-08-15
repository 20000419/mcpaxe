from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from mcpaxe import usage


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _old_iso(days: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


def _tool_line(name: str, ts: str) -> str:
    return json.dumps(
        {"timestamp": ts, "message": {"content": [{"type": "tool_use", "name": name, "input": {}}]}}
    )


def test_collect_usage_tallies_mcp_servers(tmp_path):
    root = tmp_path / "projects" / "-code-web"
    root.mkdir(parents=True)
    log = root / "session.jsonl"
    log.write_text(
        "\n".join(
            [
                _tool_line("mcp__github__create_issue", _now_iso()),
                _tool_line("mcp__github__create_issue", _now_iso()),
                _tool_line("mcp__filesystem__read_file", _now_iso()),
                _tool_line("Bash", _now_iso()),
                json.dumps({"timestamp": _now_iso(), "message": {"content": "plain text"}}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    report = usage.collect_usage(root, days=30)
    assert report.files_scanned == 1
    assert report.server_used("github")
    assert report.calls_for("github") == 2
    assert report.server_used("filesystem")
    assert not report.server_used("never-installed")
    assert report.tool_calls["Bash"] == 1
    assert report.tool_calls["mcp__github__create_issue"] == 2


def test_window_filters_old_entries(tmp_path):
    root = tmp_path / "projects"
    root.mkdir()
    (root / "old.jsonl").write_text(
        _tool_line("mcp__old-server__tool", _old_iso(90)) + "\n", encoding="utf-8"
    )
    (root / "new.jsonl").write_text(
        _tool_line("mcp__fresh-server__tool", _old_iso(2)) + "\n", encoding="utf-8"
    )

    report = usage.collect_usage(root, days=30)
    assert report.files_scanned == 2
    assert not report.server_used("old-server")
    assert report.server_used("fresh-server")


def test_malformed_lines_are_ignored(tmp_path):
    root = tmp_path / "projects"
    root.mkdir()
    (root / "messy.jsonl").write_text(
        "\n".join(
            [
                "not json at all",
                json.dumps(["unexpected", "shape"]),
                _tool_line("mcp__ok__tool", _now_iso()),
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    report = usage.collect_usage(root, days=30)
    assert report.files_scanned == 1
    assert report.server_used("ok")


def test_missing_root_is_graceful(tmp_path):
    report = usage.collect_usage(tmp_path / "does-not-exist", days=30)
    assert report.files_scanned == 0
    assert report.tool_calls == {}
