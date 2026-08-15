# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Roadmap

- Remote server support (`http` / `sse` transports)
- Usage logs from more hosts (Cursor, VS Code)
- Per-tool allowlists in slim configs
- PyPI package
- `mcpaxe watch`

## [0.1.0] - 2026-08-15

### Added

- `mcpaxe` — audit command: auto-discovers MCP configs for Claude Code
  (global + per-project), Claude Desktop, Cursor, Windsurf and `./.mcp.json`;
  launches every stdio server via MCP `initialize` → `tools/list` (with cursor
  pagination); measures per-tool and per-server token cost with `o200k_base`;
  grades A–F; flags duplicate tool names and broken/slow servers;
  `--verbose`, `--json`, `--model`, `--timeout`, `--config` flags.
- `mcpaxe usage` — parses Claude Code session logs and reports which MCP
  servers were actually invoked within a `--days` window.
- `mcpaxe slim` — combines audit + usage evidence and writes a reviewed-then-
  apply `*-slim.json` config suggestion; original configs are never modified.
- Indicative price table for cost-per-1k-turns estimates.
- CI on Ubuntu/Windows/macOS × Python 3.10–3.13, ruff lint + format checks,
  42 tests including an end-to-end JSON-RPC integration test against a fake
  MCP server.
- Bilingual README (English / 简体中文), MIT license, issue templates,
  Dependabot.

[Unreleased]: https://github.com/20000419/mcpaxe/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/20000419/mcpaxe/releases/tag/v0.1.0
