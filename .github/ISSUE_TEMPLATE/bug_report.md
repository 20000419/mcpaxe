---
name: Bug report
about: Something measured wrong, crashed, or looked off
labels: bug
---

**What happened?**

A clear description of the problem. If mcpaxe crashed, paste the full traceback.

**What did you run?**

The exact command, e.g. `mcpaxe --config ~/.cursor/mcp.json --verbose`.

**The (redacted) config entry**

```json
{
  "your-server": {
    "command": "npx",
    "args": ["-y", "@example/server"],
    "env": { "API_KEY": "<redacted>" }
  }
}
```

Redact secrets and personal paths, keep the structure.

**Environment**

- OS:
- Python version:
- mcpaxe version (`mcpaxe version`):
- Terminal (if rendering looks broken):

**Output**

```text
<paste --no-color output or --json payload>
```
