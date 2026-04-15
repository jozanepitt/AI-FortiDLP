"""Canned query registry — dropdown entries backed by the same tool DISPATCH."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.agent.tools import DISPATCH, run_tool


@dataclass(frozen=True)
class CannedQuery:
    id: str
    label: str
    tool: str
    args: dict = field(default_factory=dict)


CANNED: list[CannedQuery] = [
    CannedQuery(
        id="top_user_today",
        label="Highest-activity user today",
        tool="get_top_users",
        args={"period": "today", "limit": 1},
    ),
    CannedQuery(
        id="top_policy_week",
        label="Most-triggered policy this week",
        tool="get_top_policies",
        args={"period": "week", "limit": 1},
    ),
    CannedQuery(
        id="detection_breakdown",
        label="Detection type breakdown (past week)",
        tool="get_detection_breakdown",
        args={},
    ),
    CannedQuery(
        id="risky_users",
        label="Highest risk score users (past week)",
        tool="get_top_risky_users",
        args={"period": "week", "limit": 5},
    ),
    CannedQuery(
        id="top_devices",
        label="Devices with most detections (past week)",
        tool="get_top_devices",
        args={"period": "week", "limit": 5},
    ),
]


def list_canned() -> list[dict]:
    return [{"id": q.id, "label": q.label} for q in CANNED]


def get_canned(id_: str) -> CannedQuery | None:
    return next((q for q in CANNED if q.id == id_), None)


async def run_canned(id_: str, client: Any) -> Any:
    q = get_canned(id_)
    if q is None:
        raise KeyError(f"No canned query with id={id_!r}")
    return await run_tool(q.tool, q.args, client)
