"""Registry of canned dropdown queries.

Each canned query is (id, label, tool_name, kwargs). The id is exposed to
the frontend, the label is what the user sees in the dropdown, and
tool_name/kwargs are resolved through tools.DISPATCH - the exact same
path Claude uses.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .fortidlp_client import FortiDLPClient
from .tools import run_tool


@dataclass(frozen=True)
class CannedQuery:
    id: str
    label: str
    tool: str
    args: dict


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
        id="os_breakdown",
        label="macOS vs Windows device counts",
        tool="get_os_breakdown",
        args={},
    ),
    CannedQuery(
        id="license_count",
        label="Current license usage",
        tool="get_license_usage",
        args={},
    ),
    CannedQuery(
        id="unhealthy_devices",
        label="Devices in unhealthy state",
        tool="get_unhealthy_devices",
        args={"limit": 50},
    ),
]


def list_canned() -> list[dict]:
    """Return canned queries as dicts for the frontend dropdown."""
    return [{"id": q.id, "label": q.label} for q in CANNED]


def get_canned(id_: str) -> CannedQuery | None:
    for q in CANNED:
        if q.id == id_:
            return q
    return None


async def run_canned(id_: str, client: FortiDLPClient) -> Any:
    q = get_canned(id_)
    if q is None:
        raise KeyError(f"unknown canned query id: {id_}")
    return await run_tool(q.tool, dict(q.args), client)
