"""Discovery and parsing of MCP host configurations.

mcpaxe is read-only: it never modifies host config files. Slimmed configs are
written to separate files the user can review and apply manually.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

INVALID_TRANSPORT = "invalid"
URL_TRANSPORTS = ("http", "sse", "streamable-http")


@dataclass
class ServerSpec:
    """One configured MCP server entry, normalized across host formats."""

    name: str
    transport: str  # "stdio" | "http" | "sse" | INVALID_TRANSPORT
    command: str | None = None
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    url: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)
    host_id: str = ""
    host_label: str = ""
    source_path: Path | None = None


@dataclass
class HostConfig:
    """All MCP servers registered by one host (Claude Code, Cursor, ...)."""

    host_id: str
    label: str
    path: Path
    servers: dict[str, Any]


def _spec_from_entry(
    name: str, entry: Any, host_id: str, host_label: str, path: Path
) -> ServerSpec | None:
    """Normalize one ``mcpServers`` entry into a ServerSpec."""
    if not isinstance(entry, dict):
        return None
    declared = str(entry.get("type", "")).lower()
    command = entry.get("command")
    url = entry.get("url")

    if isinstance(command, str) and command.strip():
        env: dict[str, str] = {}
        raw_env = entry.get("env") or {}
        if isinstance(raw_env, dict):
            for key, value in raw_env.items():
                env[str(key)] = os.path.expandvars(str(value))
        args = [str(a) for a in entry.get("args", []) if isinstance(a, (str, int, float))]
        return ServerSpec(
            name=name,
            transport="stdio",
            command=command,
            args=args,
            env=env,
            raw=entry,
            host_id=host_id,
            host_label=host_label,
            source_path=path,
        )

    if isinstance(url, str) and url.strip():
        transport = declared if declared in URL_TRANSPORTS else "http"
        return ServerSpec(
            name=name,
            transport=transport,
            url=url,
            raw=entry,
            host_id=host_id,
            host_label=host_label,
            source_path=path,
        )

    return ServerSpec(
        name=name,
        transport=INVALID_TRANSPORT,
        raw=entry,
        host_id=host_id,
        host_label=host_label,
        source_path=path,
    )


def _read_mcp_servers(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    servers = data.get("mcpServers") if isinstance(data, dict) else None
    return servers if isinstance(servers, dict) else {}


def _claude_code_hosts(claude_json: Path) -> list[HostConfig]:
    """Claude Code keeps global servers plus per-project servers in ~/.claude.json."""
    hosts: list[HostConfig] = []
    global_servers = _read_mcp_servers(claude_json)
    if global_servers:
        hosts.append(HostConfig("claude-code", "Claude Code (global)", claude_json, global_servers))
    try:
        data = json.loads(claude_json.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return hosts
    projects = data.get("projects") if isinstance(data, dict) else None
    if isinstance(projects, dict):
        for project_path, pdata in sorted(projects.items()):
            if not isinstance(pdata, dict):
                continue
            servers = pdata.get("mcpServers")
            if isinstance(servers, dict) and servers:
                label = Path(str(project_path)).name or str(project_path)
                hosts.append(
                    HostConfig(
                        "claude-code-project",
                        f"Claude Code ({label})",
                        claude_json,
                        servers,
                    )
                )
    return hosts


def _claude_desktop_path(home: Path) -> Path | None:
    if os.name == "nt":
        appdata = os.environ.get("APPDATA")
        if appdata:
            return Path(appdata) / "Claude" / "claude_desktop_config.json"
        return home / "AppData" / "Roaming" / "Claude" / "claude_desktop_config.json"
    if sys.platform == "darwin":
        return home / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    return home / ".config" / "Claude" / "claude_desktop_config.json"


def discover(home: Path | None = None, cwd: Path | None = None) -> list[HostConfig]:
    """Find every well-known MCP host config that exists and has servers."""
    home = home or Path.home()
    cwd = cwd or Path.cwd()
    candidates: list[HostConfig] = []

    candidates.extend(_claude_code_hosts(home / ".claude.json"))

    desktop = _claude_desktop_path(home)
    if desktop is not None:
        servers = _read_mcp_servers(desktop)
        if servers:
            candidates.append(HostConfig("claude-desktop", "Claude Desktop", desktop, servers))

    for host_id, label, rel in [
        ("cursor", "Cursor", home / ".cursor" / "mcp.json"),
        ("windsurf", "Windsurf", home / ".codeium" / "windsurf" / "mcp_config.json"),
        ("project", "Project (.mcp.json)", cwd / ".mcp.json"),
    ]:
        servers = _read_mcp_servers(rel)
        if servers:
            candidates.append(HostConfig(host_id, label, rel, servers))

    return candidates


def specs_for_host(host: HostConfig) -> list[ServerSpec]:
    specs = []
    for name, entry in host.servers.items():
        spec = _spec_from_entry(name, entry, host.host_id, host.label, host.path)
        if spec is not None:
            specs.append(spec)
    return specs


def load_custom_config(path: Path) -> HostConfig:
    """Load an explicit config file (any JSON with an mcpServers map)."""
    servers = _read_mcp_servers(path)
    if not servers:
        raise SystemExit(f"mcpaxe: no 'mcpServers' object found in {path}")
    return HostConfig("custom", path.name, path, servers)
