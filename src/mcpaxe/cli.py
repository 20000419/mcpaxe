"""Command-line interface."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__, config, report, tokens, usage
from . import audit as audit_mod
from . import slim as slim_mod


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0].startswith("-"):
        argv = ["audit", *argv]
    cmd, rest = argv[0], argv[1:]

    if cmd in ("version", "--version", "-V"):
        mode = "exact (tiktoken)" if tokens.using_exact() else "approximate (tiktoken unavailable)"
        print(f"mcpaxe {__version__} — token counting: {mode}")
        return 0
    if cmd == "audit":
        return _cmd_audit(rest)
    if cmd == "usage":
        return _cmd_usage(rest)
    if cmd == "slim":
        return _cmd_slim(rest)
    print(f"mcpaxe: unknown command '{cmd}' (try audit, usage, slim, version)", file=sys.stderr)
    return 2


def _hosts_from_args(configs: list[str] | None) -> list[config.HostConfig]:
    if configs:
        return [config.load_custom_config(Path(p)) for p in configs]
    return config.discover()


def _cmd_audit(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="mcpaxe", description="Measure the context tax of your MCP servers."
    )
    parser.add_argument(
        "--config",
        action="append",
        metavar="PATH",
        help="audit this config file instead of auto-discovery (repeatable)",
    )
    parser.add_argument(
        "--model",
        default=tokens.DEFAULT_MODEL,
        choices=sorted(tokens.PRICES),
        help="model whose input price is used for cost (default: %(default)s)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        metavar="SEC",
        help="per-server handshake timeout (default: %(default)s)",
    )
    parser.add_argument(
        "--usage",
        action="store_true",
        help="scan Claude Code logs to show which servers you actually use",
    )
    parser.add_argument("--verbose", action="store_true", help="also list every tool's cost")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument("--no-color", action="store_true")
    args = parser.parse_args(argv)

    hosts = _hosts_from_args(args.config)
    if not hosts:
        print("mcpaxe: no MCP configs found (Claude Code/Desktop, Cursor, Windsurf, ./.mcp.json)")
        print("        Pass one explicitly with --config PATH")
        return 2

    specs = [spec for host in hosts for spec in config.specs_for_host(host)]
    result = audit_mod.audit_specs(specs, timeout=args.timeout)

    usage_report = None
    if args.usage:
        usage_report = usage.collect_usage(days=30)

    if args.json:
        print(report.audit_to_json(result, usage_report, args.model))
    else:
        console = report.make_console(args.no_color)
        report.render_audit(result, usage_report, args.model, console, verbose=args.verbose)
    return 0


def _cmd_usage(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="mcpaxe usage", description="Which MCP servers did you actually use?"
    )
    parser.add_argument(
        "--days", type=int, default=30, help="look-back window (default: %(default)s)"
    )
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--no-color", action="store_true")
    args = parser.parse_args(argv)

    collected = usage.collect_usage(days=args.days)
    if args.json:
        import json

        print(
            json.dumps(
                {
                    "window_days": collected.window_days,
                    "files_scanned": collected.files_scanned,
                    "server_calls": dict(collected.mcp_server_calls),
                    "tool_calls": dict(collected.tool_calls),
                },
                indent=2,
            )
        )
    else:
        report.render_usage(collected, report.make_console(args.no_color))
    return 0


def _cmd_slim(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="mcpaxe slim",
        description="Generate a slimmed config suggestion from audit + usage evidence.",
    )
    parser.add_argument(
        "--config",
        action="append",
        metavar="PATH",
        help="slim this config file instead of auto-discovery (repeatable)",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="usage window; servers unused this long are removal candidates (default: %(default)s)",
    )
    parser.add_argument(
        "--out", metavar="DIR", help="write suggestion files here (default: beside the original)"
    )
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--no-color", action="store_true")
    args = parser.parse_args(argv)

    hosts = _hosts_from_args(args.config)
    if not hosts:
        print(
            "mcpaxe: no MCP configs found; pass one explicitly with --config PATH", file=sys.stderr
        )
        return 2

    console = report.make_console(args.no_color)
    collected = usage.collect_usage(days=args.days)
    out_dir = Path(args.out) if args.out else None
    any_written = False

    for host in hosts:
        result = audit_mod.audit_specs(config.specs_for_host(host), timeout=args.timeout)
        slim = slim_mod.build_slim(host, result, collected)
        for decision in slim.decisions:
            style = "red strike" if decision.action == "remove" else "green"
            console.print(
                f"  [{style}]{decision.action:<6}[/] {decision.name:<24} "
                f"[dim]{decision.reason}[/dim]"
            )
        if slim.removed:
            out_path = slim_mod.write_slim(slim, out_dir)
            any_written = True
            console.print(
                f"\n  [bold]{host.label}[/bold]: dropping {len(slim.removed)} server(s) saves "
                f"~{slim.saved_tokens:,} tokens/turn → "
                f"suggestion written to [underline]{out_path}[/underline]"
            )
            console.print(
                "  Original [bold]not touched[/bold]. Back it up, review, then replace:\n"
            )
        else:
            console.print(f"\n  [bold]{host.label}[/bold]: nothing safe to trim.\n")

    if not any_written:
        console.print(
            "No suggestion files written — every server earned its keep (or lacks usage evidence)."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
