"""Audit orchestration: measure every configured server, aggregate results."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from . import mcp_client, tokens

if TYPE_CHECKING:  # pragma: no cover
    from .config import ServerSpec

STATUS_OK = "ok"
STATUS_ERROR = "error"
STATUS_SKIPPED_HTTP = "skipped-http"
STATUS_SKIPPED_INVALID = "skipped-invalid"


@dataclass
class ToolAudit:
    name: str
    tokens: int
    grade: str
    server: str = ""

    @property
    def grade_color(self) -> str:
        return {
            "A": "green",
            "B": "cyan",
            "C": "yellow",
            "D": "bright_red",
            "E": "bright_red",
            "F": "bold red",
        }[self.grade]


@dataclass
class ServerAudit:
    name: str
    host_label: str
    status: str = STATUS_OK
    error: str = ""
    latency_ms: float = 0.0
    tools: list[ToolAudit] = field(default_factory=list)
    tokens: int = 0
    grade: str = ""

    @property
    def grade_color(self) -> str:
        return {
            "A": "green",
            "B": "cyan",
            "C": "yellow",
            "D": "bright_red",
            "E": "bright_red",
            "F": "bold red",
        }.get(self.grade, "white")


@dataclass
class AuditResult:
    servers: list[ServerAudit] = field(default_factory=list)
    duplicates: dict[str, list[str]] = field(default_factory=dict)  # tool name -> server names
    total_tokens: int = 0
    total_tools: int = 0

    @property
    def measured(self) -> list[ServerAudit]:
        return [s for s in self.servers if s.status == STATUS_OK]

    @property
    def ok_tokens(self) -> int:
        return sum(s.tokens for s in self.measured)


def audit_specs(specs: list[ServerSpec], timeout: float = 30.0) -> AuditResult:
    """Launch every stdio server, list its tools, and measure token cost."""
    result = AuditResult()

    for spec in specs:
        entry = ServerAudit(name=spec.name, host_label=spec.host_label)

        if spec.transport == "invalid":
            entry.status = STATUS_SKIPPED_INVALID
            entry.error = "entry has no 'command' or 'url'"
        elif spec.transport != "stdio":
            entry.status = STATUS_SKIPPED_HTTP
            entry.error = f"{spec.transport} transport not measured yet (v0.1 audits stdio servers)"
        else:
            assert spec.command is not None
            try:
                tools, latency = mcp_client.list_tools(
                    spec.command, spec.args, spec.env, timeout=timeout
                )
            except mcp_client.McpClientError as exc:
                entry.status = STATUS_ERROR
                entry.error = str(exc)
            else:
                entry.latency_ms = latency
                entry.tokens = 0
                for tool in tools:
                    cost = tokens.measure_tool(tool)
                    entry.tools.append(
                        ToolAudit(
                            name=tool.name,
                            tokens=cost,
                            grade=tokens.grade(cost, "tool"),
                            server=spec.name,
                        )
                    )
                    entry.tokens += cost
                entry.tools.sort(key=lambda t: t.tokens, reverse=True)
                entry.grade = tokens.grade(entry.tokens, "server") if entry.tools else "A"

        result.servers.append(entry)

    _find_duplicates(result)
    result.total_tools = sum(len(s.tools) for s in result.measured)
    result.total_tokens = result.ok_tokens
    return result


def _find_duplicates(result: AuditResult) -> None:
    """Flag tool names exposed by more than one server (confuses models)."""
    seen: dict[str, list[str]] = {}
    for server in result.measured:
        for tool in server.tools:
            seen.setdefault(tool.name, []).append(server.name)
    result.duplicates = {name: owners for name, owners in sorted(seen.items()) if len(owners) > 1}
