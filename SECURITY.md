# Security policy

## Reporting a vulnerability

Email the maintainer via the GitHub account listed in the LICENSE, or open a
private security advisory:
**https://github.com/20000419/mcpaxe/security/advisories/new**

Please don't open public issues for suspected vulnerabilities.

## Scope notes

mcpaxe executes the `command` entries found in your own MCP config files —
the same processes your host (Claude Code, Cursor, ...) would launch. It
talks to them over stdio only and makes no network requests of its own.
Treat config files you feed it like you'd treat running those commands
yourself.
