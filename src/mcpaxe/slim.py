"""Evidence-based config slimming.

mcpaxe never edits your real config. It writes a *suggestion* file containing
only the servers worth keeping, next to the original (or in --out). Back up
the original, review the suggestion, then swap it in yourself.

A server is a removal candidate only when there is positive evidence you can
live without it: Claude Code logs covering the window exist and the server
was never invoked during it. Broken servers are flagged, not auto-removed.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from .audit import STATUS_ERROR, STATUS_OK

if TYPE_CHECKING:  # pragma: no cover
    from .audit import AuditResult
    from .config import HostConfig
    from .usage import UsageReport


@dataclass
class SlimDecision:
    name: str
    action: str  # "keep" | "remove"
    reason: str
    tokens: int


@dataclass
class SlimResult:
    host_label: str
    source_path: Path
    kept: dict = field(default_factory=dict)  # server name -> raw entry
    decisions: list[SlimDecision] = field(default_factory=list)
    removed: dict = field(default_factory=dict)
    saved_tokens: int = 0

    @property
    def output_name(self) -> str:
        return f"{self.source_path.stem}-slim.json"


# Usage evidence comes from Claude Code logs, so absence-of-use is only
# proof for configs whose servers you actually drive through Claude Code.
_REMOVAL_HOSTS = ("claude-code", "claude-code-project", "custom")


def build_slim(
    host: HostConfig,
    audit: AuditResult,
    usage: UsageReport | None,
) -> SlimResult:
    result = SlimResult(host_label=host.label, source_path=host.path)
    audits_by_name = {s.name: s for s in audit.servers}

    for name, raw in host.servers.items():
        server = audits_by_name.get(name)
        tokens_ = server.tokens if server and server.status == STATUS_OK else 0
        usage_backed = usage is not None and usage.files_scanned > 0

        if usage_backed and host.host_id.startswith(_REMOVAL_HOSTS) and not usage.server_used(name):
            result.removed[name] = raw
            result.decisions.append(
                SlimDecision(
                    name,
                    "remove",
                    f"0 calls in {usage.window_days} days of Claude Code logs",
                    tokens_,
                )
            )
            result.saved_tokens += tokens_
        elif usage_backed and not host.host_id.startswith(_REMOVAL_HOSTS):
            result.kept[name] = raw
            result.decisions.append(
                SlimDecision(
                    name, "keep", "usage evidence is Claude Code-only — review manually", tokens_
                )
            )
        elif server is not None and server.status == STATUS_ERROR:
            result.kept[name] = raw
            result.decisions.append(
                SlimDecision(name, "keep", f"broken ({server.error}) — fix or remove manually", 0)
            )
        else:
            result.kept[name] = raw
            calls = f"{usage.calls_for(name)} calls" if usage else "no usage data"
            result.decisions.append(SlimDecision(name, "keep", calls, tokens_))

    return result


def write_slim(result: SlimResult, out_dir: Path | None = None) -> Path:
    target_dir = out_dir if out_dir is not None else result.source_path.parent
    target_dir.mkdir(parents=True, exist_ok=True)
    out_path = target_dir / result.output_name
    out_path.write_text(
        json.dumps({"mcpServers": result.kept}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return out_path
