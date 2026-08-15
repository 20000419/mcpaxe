"""Minimal MCP stdio client.

Speaks just enough JSON-RPC 2.0 over stdio to list an MCP server's tools:
initialize → initialized notification → tools/list (with cursor pagination).

This intentionally avoids depending on a full MCP SDK — mcpaxe only ever
launches servers exactly the way your host (Claude Code, Cursor, ...) would,
talks to them locally, and never sends data anywhere else.
"""

from __future__ import annotations

import json
import os
import queue
import subprocess
import threading
import time
from dataclasses import dataclass
from typing import Any

from . import __version__

PROTOCOL_VERSION = "2025-06-18"
CLIENT_INFO = {"name": "mcpaxe", "version": __version__}

_EOF = object()


class McpClientError(RuntimeError):
    """A server could not be launched or did not speak MCP correctly."""


@dataclass
class ToolDef:
    """The parts of a tool definition that hosts inject into the context."""

    name: str
    description: str = ""
    input_schema: dict[str, Any] | None = None


class _StdioRpc:
    """Line-based JSON-RPC reader/writer with a deadline-aware request call."""

    def __init__(self, proc: subprocess.Popen[str]):
        self.proc = proc
        self._next_id = 0
        self._inbox: queue.Queue = queue.Queue()
        self._reader = threading.Thread(target=self._pump, daemon=True)
        self._reader.start()

    def _pump(self) -> None:
        assert self.proc.stdout is not None
        for line in self.proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                self._inbox.put(json.loads(line))
            except json.JSONDecodeError:
                continue
        self._inbox.put(_EOF)

    def request(self, method: str, params: dict[str, Any] | None, timeout: float) -> dict[str, Any]:
        self._next_id += 1
        req_id = self._next_id
        self._send({"jsonrpc": "2.0", "id": req_id, "method": method, "params": params or {}})
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise McpClientError(f"timed out waiting for '{method}' response")
            try:
                msg = self._inbox.get(timeout=remaining)
            except queue.Empty:
                raise McpClientError(f"timed out waiting for '{method}' response") from None
            if msg is _EOF:
                raise McpClientError(f"server exited before responding to '{method}'")
            if not isinstance(msg, dict) or msg.get("id") != req_id:
                continue  # notification, log, or someone else's response
            if "error" in msg and msg["error"] is not None:
                err = msg["error"]
                raise McpClientError(f"{method} failed: {err.get('message', err)}")
            result = msg.get("result")
            return result if isinstance(result, dict) else {}

    def notify(self, method: str) -> None:
        self._send({"jsonrpc": "2.0", "method": method})

    def _send(self, payload: dict[str, Any]) -> None:
        assert self.proc.stdin is not None
        try:
            self.proc.stdin.write(json.dumps(payload) + "\n")
            self.proc.stdin.flush()
        except (BrokenPipeError, OSError, ValueError) as exc:
            raise McpClientError(f"server closed its input ({exc})") from exc

    def close(self) -> None:
        try:
            if self.proc.stdin is not None:
                self.proc.stdin.close()
        except OSError:
            pass
        try:
            self.proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait(timeout=5)


def list_tools(
    command: str, args: list[str], env: dict[str, str], timeout: float = 30.0
) -> tuple[list[ToolDef], float]:
    """Launch a stdio MCP server, list its tools, and return them with latency.

    Raises McpClientError on any launch/protocol/timeout failure.
    """
    full_env = {**os.environ, **env}
    popen_kwargs: dict[str, Any] = {}
    if os.name == "nt":
        popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    try:
        proc = subprocess.Popen(
            [command, *args],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            env=full_env,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            **popen_kwargs,
        )
    except FileNotFoundError:
        raise McpClientError(f"command not found: {command}") from None
    except PermissionError:
        raise McpClientError(f"not executable: {command}") from None
    except OSError as exc:
        raise McpClientError(f"failed to launch: {exc}") from None

    started = time.monotonic()
    rpc = _StdioRpc(proc)
    try:
        rpc.request(
            "initialize",
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": CLIENT_INFO,
            },
            timeout,
        )
        rpc.notify("notifications/initialized")

        tools: list[ToolDef] = []
        cursor: str | None = None
        while True:
            params: dict[str, Any] = {}
            if cursor:
                params["cursor"] = cursor
            result = rpc.request("tools/list", params, timeout)
            for raw in result.get("tools", []) or []:
                if not isinstance(raw, dict) or "name" not in raw:
                    continue
                schema = raw.get("inputSchema")
                tools.append(
                    ToolDef(
                        name=str(raw["name"]),
                        description=str(raw.get("description", "") or ""),
                        input_schema=schema if isinstance(schema, dict) else None,
                    )
                )
            cursor = result.get("nextCursor")
            if not cursor:
                break
        latency_ms = (time.monotonic() - started) * 1000
        return tools, latency_ms
    finally:
        rpc.close()
