"""Whitelisted query functions exposed to Claude as tools.

Each entry in `TOOLS` is a tool definition matching Anthropic's tool-use
schema. `DISPATCH` maps the tool name to an async Python function that
takes the validated input dict and a `FortiDLPClient`, and returns a
JSON-serializable result.

Every function here is strictly read-only and wraps a single FortiDLP
endpoint. Adding a new tool means adding BOTH a schema entry and a
dispatch function - no freeform API access.
"""
from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable

from .fortidlp_client import FortiDLPClient

logger = logging.getLogger(__name__)

ToolFn = Callable[[dict, FortiDLPClient], Awaitable[Any]]


TOOLS: list[dict] = [
    {
        "name": "get_top_users",
        "description": (
            "Return the users with the most DLP policy triggers in a given "
            "period. Use this to answer questions like 'who has the highest "
            "activity today' or 'top offenders this week'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "period": {
                    "type": "string",
                    "enum": ["today", "week", "month"],
                    "description": "Time window to aggregate over.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max number of users to return (default 10).",
                    "minimum": 1,
                    "maximum": 100,
                },
            },
            "required": ["period"],
        },
    },
    {
        "name": "get_top_policies",
        "description": (
            "Return the most-triggered DLP policies in a given period. Use "
            "this for 'most triggered policy today/this week' questions."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "period": {
                    "type": "string",
                    "enum": ["today", "week", "month"],
                },
                "limit": {"type": "integer", "minimum": 1, "maximum": 100},
            },
            "required": ["period"],
        },
    },
    {
        "name": "get_os_breakdown",
        "description": (
            "Return the count of managed devices broken down by operating "
            "system (macOS, Windows, Linux, ...). Use for 'MAC vs PC user "
            "counts' or OS fleet composition questions."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_license_usage",
        "description": (
            "Return current FortiDLP license usage: seats used, total "
            "purchased, and expiration if available."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_unhealthy_devices",
        "description": (
            "Return devices reported by FortiDLP as unhealthy, with the "
            "reason and (where available) recommended remediation steps. "
            "Use for 'which devices need attention' questions."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Max devices to return (default 50).",
                    "minimum": 1,
                    "maximum": 500,
                },
            },
        },
    },
]


# --- dispatch functions ---


async def _tool_get_top_users(args: dict, client: FortiDLPClient) -> Any:
    return await client.top_users(
        period=args.get("period", "today"),
        limit=args.get("limit", 10),
    )


async def _tool_get_top_policies(args: dict, client: FortiDLPClient) -> Any:
    return await client.top_policies(
        period=args.get("period", "today"),
        limit=args.get("limit", 10),
    )


async def _tool_get_os_breakdown(args: dict, client: FortiDLPClient) -> Any:
    return await client.os_breakdown()


async def _tool_get_license_usage(args: dict, client: FortiDLPClient) -> Any:
    return await client.license_usage()


async def _tool_get_unhealthy_devices(args: dict, client: FortiDLPClient) -> Any:
    return await client.unhealthy_devices(limit=args.get("limit", 50))


DISPATCH: dict[str, ToolFn] = {
    "get_top_users": _tool_get_top_users,
    "get_top_policies": _tool_get_top_policies,
    "get_os_breakdown": _tool_get_os_breakdown,
    "get_license_usage": _tool_get_license_usage,
    "get_unhealthy_devices": _tool_get_unhealthy_devices,
}


async def run_tool(name: str, args: dict, client: FortiDLPClient) -> Any:
    """Execute a whitelisted tool. Raises KeyError for unknown tools."""
    fn = DISPATCH[name]
    logger.info("tool_call name=%s args=%s", name, args)
    return await fn(args, client)
