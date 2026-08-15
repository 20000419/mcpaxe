<div align="center">

<img src="assets/mcpaxe-logo.svg" width="150" alt="mcpaxe logo" />

# 🪓 mcpaxe

**Weigh your MCP config. Chop the context tax.**

Audit the token cost of every MCP server and tool · find the ones you never use · generate a slim config

[![CI](https://github.com/20000419/mcpaxe/actions/workflows/ci.yml/badge.svg)](https://github.com/20000419/mcpaxe/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

English | [简体中文](README.zh-CN.md)

</div>

---

## The context tax

Every MCP server you install ships its **tool definitions** — names, descriptions, JSON schemas — and your host injects them into the context window of **every single turn**, whether you call those tools or not.

Install a dozen servers "just to try them" and you can easily burn **thousands of tokens per request** on tools the model never touches — slower responses, smaller effective context, and a real line on your API bill. GitHub's own agents team reported cutting agentic token costs by up to **62%** simply by pruning unused MCP tools ([InfoQ, May 2026](https://www.infoq.com/news/2026/05/github-agentic-token-savings/)).

**mcpaxe is `du` for your MCP config** — a local, read-only CLI that shows you what each server really costs, proves which ones you never use, and writes a slimmed config suggestion you can review and apply.

## Quick start

```bash
# any of these works
pipx install git+https://github.com/20000419/mcpaxe
uvx --from git+https://github.com/20000419/mcpaxe mcpaxe   # zero-install tryout
pip install git+https://github.com/20000419/mcpaxe
```

```bash
mcpaxe            # audit every MCP config it can find (Claude Code, Claude
                  # Desktop, Cursor, Windsurf, ./.mcp.json)
```

mcpaxe auto-discovers configs from:

| Host | Location |
|---|---|
| Claude Code | `~/.claude.json` (global + per-project) |
| Claude Desktop | `claude_desktop_config.json` (per-OS app data) |
| Cursor | `~/.cursor/mcp.json` |
| Windsurf | `~/.codeium/windsurf/mcp_config.json` |
| Any project | `./.mcp.json` |

Have a config somewhere else? `mcpaxe --config path/to/file.json`.

## Demo

Real output (five example servers, three of them identical 10-tool stdio servers):

```text
$ mcpaxe --config demo-config.json

                            MCP context tax report
┌────────────┬──────────────────┬───────┬─────────────┬───────┬──────┬──────────────────┬──────────────┐
│ Server     │ Host             │ Tools │ Tokens/turn │ Grade │ Used │ $/1k turns       │ Status       │
├────────────┼──────────────────┼───────┼─────────────┼───────┼──────┼──────────────────┼──────────────┤
│ github     │ demo-config.json │    10 │         507 │   B   │    — │           $1.52 │ 32 ms        │
│ slack      │ demo-config.json │    10 │         507 │   B   │    — │           $1.52 │ 34 ms        │
│ postgres   │ demo-config.json │    10 │         507 │   B   │    — │           $1.52 │ 34 ms        │
│ notion     │ demo-config.json │     - │           - │   -   │    — │                - │ skip (remote)│
│ legacy-bot │ demo-config.json │     - │           - │   -   │    — │                - │ error …      │
└────────────┴──────────────────┴───────┴─────────────┴───────┴──────┴──────────────────┴──────────────┘

Total: 1,521 tokens of tool definitions across 30 tools — 0.8% of a 200k-token
context window, every turn.
```

That's this toy config. Real setups routinely carry 10–40 servers, and popular
servers like the official GitHub MCP expose **dozens of tools each** — the tax
compounds fast. mcpaxe also flags **duplicate tool names across servers**
(which confuse models) and broken/slow servers.

## Commands

| Command | What it does |
|---|---|
| `mcpaxe` | Audit all discovered configs: per-server and per-tool token cost, grades A–F, latency, duplicate tools, errors. `--verbose` for the per-tool table, `--json` for CI/scripting. |
| `mcpaxe usage` | Parse Claude Code session logs (`~/.claude/projects/**`) and show which MCP servers you *actually* called, and when. |
| `mcpaxe slim` | Combine both: launch-and-measure every server, cross-check usage evidence, and write a `*-slim.json` suggestion dropping servers with **zero calls in the evidence window**. Your original config is never touched. |
| `mcpaxe version` | Version + token-counting mode. |

Useful flags: `--model gpt-5|claude-sonnet-4-5|gemini-2.5-flash|…` (cost column pricing), `--timeout 30`, `--config PATH` (repeatable), `--days 30` (usage window).

### Example: the full workflow

```bash
mcpaxe --usage                        # see cost AND usage side by side
mcpaxe usage --days 14                # focus on the last two weeks
mcpaxe slim --days 14                 # writes claude.json-slim.json next to ~/.claude.json
# review the suggestion, back up the original, swap it in — done.
```

## How measurement works (and its limits)

mcpaxe launches each stdio server **exactly the way your host would** (same
command, args, env), performs the MCP `initialize` → `tools/list` handshake
(including cursor pagination), then counts tokens over each tool's
`name` + `description` + `inputSchema` using OpenAI's `o200k_base` encoding.

Honest caveats, because numbers you can't trust are worse than no numbers:

- Each host serializes tool definitions slightly differently — treat totals as **~±10%**.
- Claude's and Gemini's tokenizers differ from o200k by a similar margin.
- The `$/1k turns` column uses **indicative list prices** (see `src/mcpaxe/tokens.py`) — check your provider's current pricing before making decisions.
- Remote (`http`/`sse`) servers are skipped in v0.1 — they're listed so you know they exist. (Roadmap!)
- Usage evidence comes from Claude Code logs; for other hosts there's no comparable local log — yet.

## How it compares

| | mcpaxe | [context-mode](https://github.com/mksglu/context-mode) | [mcpslim](https://github.com/mcpslim) | [mcp-checkup](https://github.com/yifanyifan897645/mcp-checkup) |
|---|---|---|---|---|
| Layer | audit + prune (config) | runtime sandbox of tool *output* | per-server slim wrappers | meta MCP server |
| Shows per-tool token cost | ✅ | ➖ | ➖ | ✅ |
| Usage evidence from your real logs | ✅ | ➖ | ➖ | ➖ |
| Writes a slimmed config | ✅ (suggestion file) | n/a | ✅ (wrapper setup) | ➖ |
| Duplicate/broken server detection | ✅ | ➖ | ➖ | ✅ / ➖ |
| Works without installing an MCP server | ✅ | ❌ | ❌ | ❌ |

These projects are complementary: prune with mcpaxe, compress runtime output with context-mode.

## Safety & privacy

- **Read-only.** mcpaxe never modifies your configs; `slim` writes a separate suggestion file.
- **Local.** It only launches your servers over stdio, like your host does. No telemetry, no network calls of its own, no data leaves your machine.
- **Boring kills.** Servers that hang are killed after `--timeout` seconds.

## Roadmap

- [ ] Remote server support (`http`/`sse` transports)
- [ ] Usage logs from more hosts (Cursor, VS Code)
- [ ] Per-tool allowlists in generated slim configs (where the server supports tool filtering)
- [ ] PyPI package
- [ ] `mcpaxe watch` — alert when a server update silently balloons its tool descriptions

## Contributing

PRs are welcome — especially price-table updates, new host config support, and
bug reports with your (redacted) config shape. See [CONTRIBUTING.md](CONTRIBUTING.md).
Good first issues are labeled [`good first issue`](https://github.com/20000419/mcpaxe/labels/good%20first%20issue).

## License

[MIT](LICENSE)
