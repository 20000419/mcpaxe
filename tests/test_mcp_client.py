from __future__ import annotations

import sys

import pytest

from mcpaxe import mcp_client
from tests.conftest import fake_server_args


def test_list_tools_returns_all_tools_across_pages():
    tools, latency = mcp_client.list_tools(sys.executable, fake_server_args(), {})
    names = [t.name for t in tools]
    assert names == [
        "echo",
        "fetch_page",
        "search_docs",
        "list_files",
        "read_file",
        "run_query",
        "create_issue",
        "get_weather",
        "send_message",
        "describe_things",
    ]
    assert tools[0].description
    assert tools[0].input_schema
    assert latency >= 0


def test_crashing_server_raises_client_error():
    with pytest.raises(mcp_client.McpClientError):
        mcp_client.list_tools(sys.executable, fake_server_args("--crash"), {})


def test_stalled_server_times_out():
    with pytest.raises(mcp_client.McpClientError, match="timed out"):
        mcp_client.list_tools(sys.executable, fake_server_args("--delay", "3"), {}, timeout=0.5)


def test_missing_command_raises_client_error():
    with pytest.raises(mcp_client.McpClientError, match="command not found"):
        mcp_client.list_tools("definitely-not-a-real-command-xyz-123", [], {})
