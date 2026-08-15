<div align="center">

<img src="assets/mcpaxe-logo.svg" width="150" alt="mcpaxe logo" />

# 🪓 mcpaxe

**称一称你的 MCP 配置，砍掉上下文税。**

审计每个 MCP 服务器和工具的 token 开销 · 找出你从没用过的 · 生成瘦身版配置

[![CI](https://github.com/20000419/mcpaxe/actions/workflows/ci.yml/badge.svg)](https://github.com/20000419/mcpaxe/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

[English](README.md) | 简体中文

</div>

---

## 什么是"上下文税"

你安装的每一个 MCP 服务器都会把它的**工具定义**（名称、描述、JSON Schema）注入到**每一轮对话**的上下文里——不管你用不用这些工具。

"先装上试试"装了一打服务器之后，你可能每轮请求都在为模型根本不会调用的工具**白付几千 token**：响应变慢、有效上下文变小、API 账单实实在在变贵。GitHub 自己的 agent 团队报告过：仅靠裁剪未使用的 MCP 工具，就把 agent token 成本砍掉了最多 **62%**（[InfoQ，2026 年 5 月](https://www.infoq.com/news/2026/05/github-agentic-token-savings/)）。

**mcpaxe 就是你的 MCP 配置的 `du`** —— 一个本地、只读的命令行工具：告诉你每个服务器真实开销多少、用日志证明哪些你从来没用过、并生成一份可以直接审查采用的瘦身配置。

## 快速开始

```bash
pipx install git+https://github.com/20000419/mcpaxe
# 或零安装试用：
uvx --from git+https://github.com/20000419/mcpaxe mcpaxe
```

```bash
mcpaxe        # 自动发现并审计 MCP 配置（Claude Code、Claude Desktop、
              # Cursor、Windsurf、当前目录 .mcp.json）
```

| 宿主 | 位置 |
|---|---|
| Claude Code | `~/.claude.json`（全局 + 各项目） |
| Claude Desktop | 各系统应用数据目录下的 `claude_desktop_config.json` |
| Cursor | `~/.cursor/mcp.json` |
| Windsurf | `~/.codeium/windsurf/mcp_config.json` |
| 任意项目 | `./.mcp.json` |

配置在别处？`mcpaxe --config 路径/文件.json`。

## 演示

```text
$ mcpaxe --config demo-config.json

                            MCP 上下文税报告
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

这只是一个演示配置。真实环境里装 10–40 个服务器很常见，官方 GitHub MCP 这类热门服务器单个就暴露**几十个工具**——税越滚越快。mcpaxe 还会标记**跨服务器的重名工具**（会让模型困惑）以及坏掉/超时的服务器。

## 命令

| 命令 | 作用 |
|---|---|
| `mcpaxe` | 审计所有发现的配置：每个服务器/工具的 token 开销、A–F 评级、延迟、重名工具、错误。`--verbose` 看每个工具，`--json` 用于脚本/CI。 |
| `mcpaxe usage` | 解析 Claude Code 会话日志（`~/.claude/projects/**`），显示你**实际**调用过哪些 MCP 服务器。 |
| `mcpaxe slim` | 两者结合：实测每个服务器 + 交叉比对使用证据，生成去掉「证据窗口内零调用」服务器的 `*-slim.json` 建议文件。**绝不改动你的原配置。** |
| `mcpaxe version` | 版本与 token 计量模式。 |

常用参数：`--model gpt-5|claude-sonnet-4-5|gemini-2.5-flash|…`（成本列计价）、`--timeout 30`、`--config 路径`（可多次）、`--days 30`（使用证据窗口）。

```bash
mcpaxe --usage              # 开销与使用情况并排看
mcpaxe usage --days 14      # 只看最近两周
mcpaxe slim --days 14       # 在 ~/.claude.json 旁边生成 claude.json-slim.json
# 审查建议文件 → 备份原配置 → 替换，完成。
```

## 计量方法（以及局限）

mcpaxe 以**和宿主完全相同的方式**（相同的 command、args、env）启动每个 stdio 服务器，执行 MCP `initialize` → `tools/list` 握手（含分页），然后用 OpenAI 的 `o200k_base` 编码对每个工具的 `name` + `description` + `inputSchema` 计 token。

诚实的免责声明（不可信的数字比没有数字更糟）：

- 各宿主序列化工具定义的格式略有差异——总量请按 **±10%** 理解；
- Claude / Gemini 的分词器与 o200k 有相近幅度的差异；
- `$/1k turns` 列用的是**指导价**（见 `src/mcpaxe/tokens.py`）——决策前请核对服务商当前价格；
- v0.1 暂不测量远程（`http`/`sse`）服务器，但会列出提醒你它们存在（已在路线图上）；
- 使用证据来自 Claude Code 日志；其他宿主暂无可比的本地日志。

## 安全与隐私

- **只读**：mcpaxe 绝不修改你的配置；`slim` 只生成单独的建议文件。
- **本地**：只通过 stdio 启动你自己的服务器（和宿主行为一致）。无遥测、自身不发起网络请求、数据不出你的机器。
- **卡死即杀**：超过 `--timeout` 秒的进程直接终止。

## 路线图

- [ ] 支持远程服务器（`http`/`sse`）
- [ ] 更多宿主的使用日志（Cursor、VS Code）
- [ ] 瘦身配置中生成按工具的白名单（对支持工具过滤的服务器）
- [ ] 发布到 PyPI
- [ ] `mcpaxe watch`——服务器更新后工具描述悄悄膨胀时报警

## 参与贡献

欢迎 PR——特别是价格表更新、新宿主配置支持，以及附上（脱敏后）配置结构的 bug 报告。见 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 许可证

[MIT](LICENSE)
