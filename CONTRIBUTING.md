# Contributing to mcpaxe

Thanks for helping chop the context tax! 🪓

## Getting started

```bash
git clone https://github.com/20000419/mcpaxe
cd mcpaxe
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest                # 42 tests, should all pass
```

## Before you open a PR

```bash
ruff check src tests
ruff format src tests
pytest
```

CI runs the same three steps on Ubuntu/Windows/macOS, so if they pass locally
you're almost certainly green.

## What's especially welcome

- **Price table updates** (`src/mcpaxe/tokens.py`) — provider prices change
  often; include the source in your PR description.
- **New host configs** — know where another MCP host stores its servers?
  Add it to `src/mcpaxe/config.py` with a test.
- **Bug reports** — include the *shape* of your config entry (redact secrets
  and paths) plus the error/status mcpaxe reported.
- Issues labeled
  [`good first issue`](https://github.com/20000419/mcpaxe/labels/good%20first%20issue)
  are pre-scoped for newcomers.

## Design constraints to keep in mind

1. **Read-only by default.** We never write to a host config; suggestions go
   to separate files.
2. **Local only.** No telemetry, no network calls except to the servers the
   user already configured.
3. **Honest numbers.** Any measurement claim needs a caveat when it's an
   estimate; the docs say ±10% and mean it.
4. **Dependency-light.** stdlib + rich + tiktoken. New deps need a strong
   justification in the PR.

## Reporting security issues

See [SECURITY.md](SECURITY.md).
