"""Rich terminal reports and JSON output for audits and usage."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from . import __version__, tokens
from .audit import STATUS_ERROR, STATUS_OK, STATUS_SKIPPED_HTTP, STATUS_SKIPPED_INVALID

if TYPE_CHECKING:  # pragma: no cover
    from .audit import AuditResult
    from .usage import UsageReport

_STATUS_LABEL = {
    STATUS_OK: "",
    STATUS_ERROR: "[red]error[/red]",
    STATUS_SKIPPED_HTTP: "[dim]skip (remote)[/dim]",
    STATUS_SKIPPED_INVALID: "[dim]skip (invalid)[/dim]",
}


def _status_cell(server) -> str:
    base = _STATUS_LABEL[server.status]
    if server.status == STATUS_ERROR:
        return f"{base} {server.error}"
    return base


def make_console(no_color: bool = False) -> Console:
    return Console(no_color=no_color or not sys.stdout.isatty(), highlight=False)


def render_audit(
    audit: AuditResult,
    usage: UsageReport | None,
    model: str,
    console: Console,
    verbose: bool = False,
) -> None:
    table = Table(title="MCP context tax report", title_style="bold")
    for col, kwargs in [
        ("Server", {"style": "bold"}),
        ("Host", {}),
        ("Tools", {"justify": "right"}),
        ("Tokens/turn", {"justify": "right"}),
        ("Grade", {"justify": "center"}),
        ("Used", {"justify": "right"}),
        (f"$/1k turns ({model})", {"justify": "right"}),
        ("Status", {}),
    ]:
        table.add_column(col, **kwargs)

    for server in audit.servers:
        if server.status == STATUS_OK:
            used = _used_cell(usage, server.name)
            table.add_row(
                server.name,
                server.host_label,
                str(len(server.tools)),
                f"{server.tokens:,}",
                f"[{server.grade_color}]{server.grade}[/]",
                used,
                f"${tokens.cost_per_1k_turns(server.tokens, model):,.2f}",
                f"[dim]{server.latency_ms:.0f} ms[/dim]",
            )
        else:
            table.add_row(
                server.name,
                server.host_label,
                "-",
                "-",
                "-",
                _used_cell(usage, server.name),
                "-",
                _status_cell(server),
            )
    console.print(table)

    lines = [
        f"Total: [bold]{audit.total_tokens:,} tokens[/bold] of tool definitions across "
        f"[bold]{audit.total_tools}[/bold] tools — "
        f"{tokens.context_percent(audit.total_tokens):.1f}% of a "
        f"{tokens.DEFAULT_CONTEXT_WINDOW // 1000}k-token context window, every turn."
    ]
    if usage is not None:
        lines.append(
            f"Usage evidence: {usage.files_scanned} Claude Code session files over "
            f"{usage.window_days} days."
        )
    accuracy = "exact (o200k_base)" if tokens.using_exact() else "APPROXIMATE (tiktoken offline)"
    lines.append(
        f"[dim]Counts are {accuracy}; Claude/Gemini tokenizations differ by ~±10%. "
        "Prices are indicative list prices.[/dim]"
    )
    console.print("\n".join(lines))

    if audit.duplicates:
        dup = Text()
        for tool, owners in audit.duplicates.items():
            dup.append(f"  {tool}", style="yellow")
            dup.append(f"  ← {', '.join(owners)}\n")
        console.print(
            Panel(dup, title="Duplicate tool names across servers", border_style="yellow")
        )

    if verbose:
        _render_tools(audit, console)


def _used_cell(usage: UsageReport | None, server: str) -> str:
    if usage is None:
        return "[dim]—[/dim]"
    calls = usage.calls_for(server)
    return f"{calls} calls" if calls else "[red]never[/red]"


def _render_tools(audit: AuditResult, console: Console) -> None:
    all_tools = sorted(
        (t for s in audit.measured for t in s.tools), key=lambda t: t.tokens, reverse=True
    )
    table = Table(title="Per-tool breakdown (heaviest first)", title_style="bold")
    for col, kwargs in [
        ("Tool", {}),
        ("Server", {}),
        ("Tokens", {"justify": "right"}),
        ("Grade", {"justify": "center"}),
    ]:
        table.add_column(col, **kwargs)
    for tool in all_tools[:50]:
        table.add_row(
            tool.name, tool.server, f"{tool.tokens:,}", f"[{tool.grade_color}]{tool.grade}[/]"
        )
    console.print(table)


def render_usage(usage: UsageReport, console: Console) -> None:
    if usage.files_scanned == 0:
        console.print(
            "[yellow]No Claude Code session logs found (~/.claude/projects). "
            "Usage evidence requires Claude Code.[/yellow]"
        )
        return
    table = Table(title=f"MCP usage — last {usage.window_days} days", title_style="bold")
    table.add_column("Server", style="bold")
    table.add_column("Calls", justify="right")
    table.add_column("Last activity window", style="dim")
    table.add_row(
        f"{len(usage.mcp_server_calls)} server(s) used",
        str(sum(usage.mcp_server_calls.values())),
        f"{usage.first_seen or '?'} … {usage.last_seen or '?'}",
    )
    console.print(table)

    detail = Table(show_header=True)
    detail.add_column("Server", style="bold")
    detail.add_column("Tool", style="dim")
    detail.add_column("Calls", justify="right")
    mcp_tools = [
        (name, count) for name, count in usage.tool_calls.most_common() if name.startswith("mcp__")
    ]
    for name, count in mcp_tools:
        rest = name[len("mcp__") :]
        server, _, tool = rest.partition("__")
        detail.add_row(server or "?", tool or "?", str(count))
    console.print(detail)


def audit_to_json(audit: AuditResult, usage: UsageReport | None, model: str) -> str:
    import json as _json

    payload = {
        "generator": f"mcpaxe {__version__}",
        "exact": tokens.using_exact(),
        "model": model,
        "totals": {
            "tokens_per_turn": audit.total_tokens,
            "tools": audit.total_tools,
            "context_percent": round(tokens.context_percent(audit.total_tokens), 2),
            "cost_per_1k_turns": round(tokens.cost_per_1k_turns(audit.total_tokens, model), 4),
        },
        "servers": [
            {
                "name": s.name,
                "host": s.host_label,
                "status": s.status,
                "error": s.error or None,
                "latency_ms": round(s.latency_ms),
                "tools": len(s.tools),
                "tokens": s.tokens,
                "grade": s.grade or None,
                "used_calls": usage.calls_for(s.name) if usage else None,
                "tool_detail": [
                    {"name": t.name, "tokens": t.tokens, "grade": t.grade} for t in s.tools
                ],
            }
            for s in audit.servers
        ],
        "duplicates": audit.duplicates,
        "usage": (
            {
                "window_days": usage.window_days,
                "files_scanned": usage.files_scanned,
                "server_calls": dict(usage.mcp_server_calls),
            }
            if usage
            else None
        ),
    }
    return _json.dumps(payload, indent=2)
