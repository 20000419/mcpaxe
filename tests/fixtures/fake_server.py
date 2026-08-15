"""A tiny stdio MCP server used by mcpaxe's own tests.

Speaks initialize / notifications/initialized / tools/list with cursor
pagination. Flags: --crash (exit immediately), --delay SECONDS (stall).

Intentionally dependency-free so it runs on every CI OS and Python version.
"""

from __future__ import annotations

import json
import sys
import time

TOOLS = [
    {
        "name": "echo",
        "description": "Echo a message back.",
        "inputSchema": {
            "type": "object",
            "properties": {"message": {"type": "string"}},
            "required": ["message"],
        },
    },
    {
        "name": "fetch_page",
        "description": "Fetch a web page and return its text content after stripping HTML.",
        "inputSchema": {
            "type": "object",
            "properties": {"url": {"type": "string", "format": "uri"}},
            "required": ["url"],
        },
    },
    {
        "name": "search_docs",
        "description": "Full-text search across the indexed documentation set.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer", "default": 10},
            },
        },
    },
    {
        "name": "list_files",
        "description": "List files in a directory with sizes and modification times.",
        "inputSchema": {"type": "object", "properties": {"path": {"type": "string"}}},
    },
    {
        "name": "read_file",
        "description": "Read a UTF-8 text file from disk.",
        "inputSchema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    },
    {
        "name": "run_query",
        "description": "Run a read-only SQL query against the analytics warehouse.",
        "inputSchema": {
            "type": "object",
            "properties": {"sql": {"type": "string"}, "max_rows": {"type": "integer"}},
            "required": ["sql"],
        },
    },
    {
        "name": "create_issue",
        "description": "Create an issue in a repository with title, body, and labels.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "repo": {"type": "string"},
                "title": {"type": "string"},
                "body": {"type": "string"},
                "labels": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["repo", "title"],
        },
    },
    {
        "name": "get_weather",
        "description": "Current weather conditions for a city.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "city": {"type": "string"},
                "units": {"type": "string", "enum": ["c", "f"]},
            },
            "required": ["city"],
        },
    },
    {
        "name": "send_message",
        "description": "Send a message to a channel.",
        "inputSchema": {
            "type": "object",
            "properties": {"channel": {"type": "string"}, "text": {"type": "string"}},
            "required": ["channel", "text"],
        },
    },
    {
        "name": "describe_things",
        "description": (
            "Describe things. This tool exists to exercise the token measurer with a "
            "deliberately long description: hosts inject every tool's name, description, "
            "and schema into the context window on every single turn, so verbose tools "
            "quietly cost money forever. Keep your tool descriptions lean."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "thing": {"type": "string", "description": "The thing to describe."},
                "verbose": {"type": "boolean", "default": False},
            },
        },
    },
]

PAGE_SIZE = 4


def reply(request_id, result):
    sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": request_id, "result": result}) + "\n")
    sys.stdout.flush()


def main():
    argv = sys.argv[1:]
    if "--crash" in argv:
        sys.exit(1)
    if "--delay" in argv:
        time.sleep(float(argv[argv.index("--delay") + 1]))

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            continue
        method = request.get("method")
        request_id = request.get("id")

        if method == "initialize":
            reply(
                request_id,
                {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "fake", "version": "0.0.1"},
                },
            )
        elif method == "notifications/initialized":
            continue
        elif method == "tools/list":
            cursor = (request.get("params") or {}).get("cursor")
            start = int(cursor) if cursor else 0
            result = {"tools": TOOLS[start : start + PAGE_SIZE]}
            nxt = start + PAGE_SIZE
            if nxt < len(TOOLS):
                result["nextCursor"] = str(nxt)
            reply(request_id, result)
        elif method == "ping":
            reply(request_id, {})


if __name__ == "__main__":
    main()
