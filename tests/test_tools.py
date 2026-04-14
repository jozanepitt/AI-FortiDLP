"""Unit tests for the tools layer with a mocked FortiDLP backend."""
from __future__ import annotations

import httpx
import pytest
import respx

from app.agent.fortidlp_client import FortiDLPClient
from app.agent.tools import DISPATCH, TOOLS, run_tool

BASE = "https://fortidlp.example.com/api/v1"


def test_tools_schema_well_formed():
    names = {t["name"] for t in TOOLS}
    assert names == set(DISPATCH.keys())
    for t in TOOLS:
        assert "description" in t
        assert t["input_schema"]["type"] == "object"


@pytest.fixture
async def client():
    c = FortiDLPClient(base_url=BASE, token="fake-token")
    try:
        yield c
    finally:
        await c.aclose()


@respx.mock
async def test_get_top_users(client):
    respx.get(f"{BASE}/analytics/top-users").mock(
        return_value=httpx.Response(
            200,
            json=[{"user": "alice@example.com", "events": 42}],
        )
    )
    result = await run_tool("get_top_users", {"period": "today", "limit": 1}, client)
    assert result == [{"user": "alice@example.com", "events": 42}]


@respx.mock
async def test_get_top_policies(client):
    respx.get(f"{BASE}/analytics/top-policies").mock(
        return_value=httpx.Response(
            200,
            json={"items": [{"policy": "PII-Exfiltration", "count": 19}]},
        )
    )
    result = await run_tool("get_top_policies", {"period": "week"}, client)
    assert result == [{"policy": "PII-Exfiltration", "count": 19}]


@respx.mock
async def test_get_os_breakdown_from_list(client):
    respx.get(f"{BASE}/analytics/os-breakdown").mock(
        return_value=httpx.Response(
            200,
            json=[
                {"os": "Windows", "count": 120},
                {"os": "macOS", "count": 35},
            ],
        )
    )
    result = await run_tool("get_os_breakdown", {}, client)
    assert result == {"windows": 120, "macos": 35}


@respx.mock
async def test_get_license_usage(client):
    respx.get(f"{BASE}/licenses").mock(
        return_value=httpx.Response(
            200,
            json={"used": 140, "total": 200, "expires_at": "2027-01-01"},
        )
    )
    result = await run_tool("get_license_usage", {}, client)
    assert result["used"] == 140
    assert result["total"] == 200


@respx.mock
async def test_get_unhealthy_devices(client):
    respx.get(f"{BASE}/devices").mock(
        return_value=httpx.Response(
            200,
            json=[
                {"host": "DESKTOP-A", "reason": "agent offline"},
                {"host": "MBP-B", "reason": "out of date"},
            ],
        )
    )
    result = await run_tool("get_unhealthy_devices", {"limit": 10}, client)
    assert len(result) == 2
    assert result[0]["host"] == "DESKTOP-A"
