from __future__ import annotations

import pytest

from mcpaxe import tokens
from mcpaxe.mcp_client import ToolDef


def test_payload_contains_the_three_injected_fields():
    tool = ToolDef(
        name="echo",
        description="Echo a message.",
        input_schema={"type": "object", "properties": {"msg": {"type": "string"}}},
    )
    payload = tokens.tool_payload(tool)
    assert '"name":"echo"' in payload
    assert '"description":"Echo a message."' in payload
    assert '"inputSchema"' in payload


def test_measure_tool_is_positive_and_monotonic_in_description():
    lean = ToolDef(name="a", description="x")
    fat = ToolDef(name="a", description="x" * 400)
    assert tokens.measure_tool(lean) > 0
    assert tokens.measure_tool(fat) > tokens.measure_tool(lean)


def test_empty_text_is_zero():
    assert tokens.count_tokens("") == 0


def test_fallback_estimate_when_no_tiktoken(monkeypatch):
    monkeypatch.setattr(tokens, "_tiktoken_ok", False)
    monkeypatch.setattr(tokens, "_encoding", None)
    estimated = tokens.count_tokens("a" * 360)
    assert estimated == 100  # 360 / 3.6


def test_exact_counts_match_tiktoken():
    pytest.importorskip("tiktoken")
    import tiktoken

    enc = tiktoken.get_encoding("o200k_base")
    text = "def hello():\n    return 'world'\n" * 3
    assert tokens.count_tokens(text) == len(enc.encode(text))


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (0, "A"),
        (100, "A"),
        (101, "B"),
        (250, "B"),
        (251, "C"),
        (1000, "D"),
        (2000, "E"),
        (2001, "F"),
    ],
)
def test_tool_grades(value, expected):
    assert tokens.grade(value, "tool") == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [(0, "A"), (500, "A"), (501, "B"), (3000, "C"), (6000, "D"), (12000, "E"), (12001, "F")],
)
def test_server_grades(value, expected):
    assert tokens.grade(value, "server") == expected


def test_cost_per_1k_turns_math():
    # 1M tokens at $3/M input → $3 per 1k turns
    assert tokens.cost_per_1k_turns(1_000_000, "claude-sonnet-4-5") == pytest.approx(3000.0)
    assert tokens.cost_per_1k_turns(0, "gpt-5") == 0.0


def test_context_percent():
    assert tokens.context_percent(100_000) == pytest.approx(50.0)
