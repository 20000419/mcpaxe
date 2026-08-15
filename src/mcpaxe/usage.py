"""Parse Claude Code session logs to learn which MCP tools you actually use.

Claude Code writes one JSONL file per session under ``~/.claude/projects/``.
Each assistant message may contain ``tool_use`` blocks whose names follow the
``mcp__<server>__<tool>`` convention. mcpaxe reads these files locally and
never sends the contents anywhere.

Other hosts (Cursor, Claude Desktop, ...) do not expose comparable local
logs, so usage evidence is Claude Code-only for now — see the roadmap.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path


@dataclass
class UsageReport:
    window_days: int
    files_scanned: int = 0
    tool_calls: Counter = field(
        default_factory=Counter
    )  # full name, e.g. mcp__github__create_issue
    mcp_server_calls: Counter = field(default_factory=Counter)  # server name only
    first_seen: str | None = None
    last_seen: str | None = None

    def server_used(self, server_name: str) -> bool:
        return self.mcp_server_calls.get(server_name, 0) > 0

    def calls_for(self, server_name: str) -> int:
        return self.mcp_server_calls.get(server_name, 0)


def default_root() -> Path:
    return Path.home() / ".claude" / "projects"


def collect_usage(root: Path | None = None, days: int = 30) -> UsageReport:
    """Tally MCP tool invocations from Claude Code logs within ``days``."""
    root = root if root is not None else default_root()
    report = UsageReport(window_days=days)
    if not root.is_dir():
        return report

    cutoff = datetime.now(timezone.utc) - timedelta(days=max(1, days))

    for path in sorted(root.rglob("*.jsonl")):
        try:
            with path.open(encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    _consume_line(line, cutoff, report)
            report.files_scanned += 1
        except OSError:
            continue
    return report


def _consume_line(line: str, cutoff: datetime, report: UsageReport) -> None:
    line = line.strip()
    if not line or "tool_use" not in line:
        return
    try:
        record = json.loads(line)
    except json.JSONDecodeError:
        return
    if not isinstance(record, dict):
        return

    ts = _parse_timestamp(record.get("timestamp"))
    if ts is None or ts < cutoff:
        return
    stamp = ts.isoformat()
    if report.first_seen is None or stamp < report.first_seen:
        report.first_seen = stamp
    if report.last_seen is None or stamp > report.last_seen:
        report.last_seen = stamp

    message = record.get("message")
    if not isinstance(message, dict):
        return
    content = message.get("content")
    if not isinstance(content, list):
        return
    for item in content:
        if isinstance(item, dict) and item.get("type") == "tool_use":
            name = str(item.get("name", ""))
            if not name:
                continue
            report.tool_calls[name] += 1
            if name.startswith("mcp__"):
                server = name[len("mcp__") :].partition("__")[0]
                if server:
                    report.mcp_server_calls[server] += 1


def _parse_timestamp(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed
