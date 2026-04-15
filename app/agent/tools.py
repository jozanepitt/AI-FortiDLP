"""Whitelisted tool schemas and dispatch table for Claude tool-use."""
from __future__ import annotations

import json
import logging
from typing import Any

log = logging.getLogger(__name__)

TOOLS: list[dict] = [
    {
        "name": "get_top_users",
        "description": (
            "Return the most active users ranked by detection/incident count. "
            "period: 'today' (since midnight), 'week' (past 7 days), 'month' (past 30 days)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "period": {
                    "type": "string",
                    "enum": ["today", "week", "month"],
                    "default": "today",
                },
                "limit": {"type": "integer", "default": 5},
            },
        },
    },
    {
        "name": "get_top_policies",
        "description": (
            "Return the most frequently triggered DLP policies for a given period."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "period": {
                    "type": "string",
                    "enum": ["today", "week", "month"],
                    "default": "week",
                },
                "limit": {"type": "integer", "default": 5},
            },
        },
    },
    {
        "name": "get_detection_breakdown",
        "description": (
            "Return a count of detections grouped by sensor/detection type for the past week. "
            "Categories include file_upload, usb, print, browser, email, etc."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_top_risky_users",
        "description": (
            "Return users ranked by cumulative risk score from detections and incidents. "
            "Higher scores indicate more severe or frequent policy violations."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "period": {
                    "type": "string",
                    "enum": ["today", "week", "month"],
                    "default": "week",
                },
                "limit": {"type": "integer", "default": 5},
            },
        },
    },
    {
        "name": "get_top_devices",
        "description": (
            "Return endpoints (by hostname) with the most DLP detections. "
            "Use for questions about device health, unhealthy devices, risky endpoints, "
            "machines generating the most alerts, or endpoint risk overview."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "period": {
                    "type": "string",
                    "enum": ["today", "week", "month"],
                    "default": "week",
                },
                "limit": {"type": "integer", "default": 10},
            },
        },
    },
    {
        "name": "get_event_summary",
        "description": (
            "Return a high-level summary of DLP activity: total events, unique users, "
            "unique devices, and unique policies triggered for a given period."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "period": {
                    "type": "string",
                    "enum": ["today", "week", "month"],
                    "default": "today",
                },
            },
        },
    },
]


async def _tool_get_top_users(args: dict, client: Any) -> Any:
    return await client.top_users(
        period=args.get("period", "today"),
        limit=int(args.get("limit", 5)),
    )


async def _tool_get_top_policies(args: dict, client: Any) -> Any:
    return await client.top_policies(
        period=args.get("period", "week"),
        limit=int(args.get("limit", 5)),
    )


async def _tool_get_detection_breakdown(args: dict, client: Any) -> Any:
    return await client.detection_breakdown()


async def _tool_get_top_risky_users(args: dict, client: Any) -> Any:
    return await client.top_risky_users(
        period=args.get("period", "week"),
        limit=int(args.get("limit", 5)),
    )


async def _tool_get_top_devices(args: dict, client: Any) -> Any:
    return await client.top_devices(
        period=args.get("period", "week"),
        limit=int(args.get("limit", 10)),
    )


async def _tool_get_event_summary(args: dict, client: Any) -> Any:
    return await client.event_summary(period=args.get("period", "today"))


DISPATCH: dict[str, Any] = {
    "get_top_users": _tool_get_top_users,
    "get_top_policies": _tool_get_top_policies,
    "get_detection_breakdown": _tool_get_detection_breakdown,
    "get_top_risky_users": _tool_get_top_risky_users,
    "get_top_devices": _tool_get_top_devices,
    "get_event_summary": _tool_get_event_summary,
}


async def run_tool(name: str, args: dict, client: Any) -> Any:
    fn = DISPATCH.get(name)
    if fn is None:
        raise ValueError(f"Unknown tool: {name!r}")
    log.info("tool_call name=%s args=%s", name, json.dumps(args, default=str))
    return await fn(args, client)
