"""Token measurement, grading, and indicative pricing.

Methodology
-----------
Every MCP host injects each tool's name, description, and input schema into
the request payload before the model sees it. mcpaxe serializes exactly those
three fields to compact JSON and counts tokens over the result with OpenAI's
``o200k_base`` encoding. Real per-host serialization differs slightly, so
treat numbers as within ~±10% of what your host actually sends. Claude and
Gemini tokenizations differ from o200k by a similar margin.

If tiktoken cannot load an encoding (e.g. offline with no cache), mcpaxe
falls back to a calibrated character-based estimate and clearly marks the
report as approximate.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from .mcp_client import ToolDef

try:
    import tiktoken

    _tiktoken_ok = True
except ImportError:  # pragma: no cover - depends on install flavor
    tiktoken = None  # type: ignore[assignment]
    _tiktoken_ok = False

# Calibrated for compact JSON of name+description+schema (mostly ASCII keys,
# short strings). Good to within ~15% of o200k_base on typical toolsets.
FALLBACK_CHARS_PER_TOKEN = 3.6

_encoding = None

# Indicative list prices, USD per 1M tokens (input, output), snapshot
# 2026-08. Prices change often — PRs updating this table are welcome.
PRICES: dict[str, tuple[float, float]] = {
    "gpt-5": (1.25, 10.00),
    "gpt-5-mini": (0.25, 2.00),
    "claude-opus-4-5": (5.00, 25.00),
    "claude-sonnet-4-5": (3.00, 15.00),
    "claude-haiku-4-5": (1.00, 5.00),
    "gemini-2.5-pro": (1.25, 10.00),
    "gemini-2.5-flash": (0.30, 2.50),
}
DEFAULT_MODEL = "claude-sonnet-4-5"
DEFAULT_CONTEXT_WINDOW = 200_000


def using_exact() -> bool:
    """True when tiktoken is importable (exact OpenAI-encoding counts)."""
    return _tiktoken_ok


def _get_encoding():
    global _encoding
    if _encoding is None:
        _encoding = tiktoken.get_encoding("o200k_base")
    return _encoding


def count_tokens(text: str) -> int:
    """Count tokens with o200k_base, or estimate from character count."""
    if not text:
        return 0
    if _tiktoken_ok:
        try:
            return len(_get_encoding().encode(text))
        except Exception:
            # e.g. no cached encoding file and offline
            pass
    return max(1, round(len(text) / FALLBACK_CHARS_PER_TOKEN))


def tool_payload(tool: ToolDef) -> str:
    """Serialize the fields a host injects per tool into one measurable blob."""
    return json.dumps(
        {
            "name": tool.name,
            "description": tool.description,
            "inputSchema": tool.input_schema or {},
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )


def measure_tool(tool: ToolDef) -> int:
    return count_tokens(tool_payload(tool))


_THRESHOLDS = {
    "tool": [("A", 100), ("B", 250), ("C", 500), ("D", 1000), ("E", 2000)],
    "server": [("A", 500), ("B", 1500), ("C", 3000), ("D", 6000), ("E", 12000)],
}


def grade(tokens: int, kind: str = "tool") -> str:
    """A (lean) .. F (obese) grade for a tool- or server-level token cost."""
    for letter, ceiling in _THRESHOLDS[kind]:
        if tokens <= ceiling:
            return letter
    return "F"


def cost_per_1k_turns(tokens: int, model: str = DEFAULT_MODEL) -> float:
    """USD a server's tool definitions add to every 1,000 requests (input)."""
    price = PRICES.get(model, PRICES[DEFAULT_MODEL])[0]
    return tokens / 1_000_000 * price * 1_000


def context_percent(tokens: int, window: int = DEFAULT_CONTEXT_WINDOW) -> float:
    return tokens / window * 100
