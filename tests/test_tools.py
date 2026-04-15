"""Unit tests for the tools layer with a mocked FortiDLP stream client."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.agent.tools import DISPATCH, TOOLS, run_tool


def test_tools_schema_well_formed():
    names = {t["name"] for t in TOOLS}
    assert names == set(DISPATCH.keys())
    for t in TOOLS:
        assert "description" in t
        assert t["input_schema"]["type"] == "object"


@pytest.fixture
def mock_client():
    c = MagicMock()
    c.top_users = AsyncMock(return_value=[{"user": "alice@example.com", "events": 42}])
    c.top_policies = AsyncMock(return_value=[{"policy": "PII-Exfiltration", "count": 19}])
    c.detection_breakdown = AsyncMock(return_value={"file_upload": 50, "usb": 12})
    c.top_risky_users = AsyncMock(return_value=[{"user": "bob@example.com", "total_score": 850}])
    c.top_devices = AsyncMock(return_value=[{"device": "DESKTOP-ABC", "detections": 15}])
    c.event_summary = AsyncMock(
        return_value={
            "period": "today",
            "total_events": 120,
            "unique_users": 8,
            "unique_devices": 5,
            "unique_policies": 3,
        }
    )
    return c


async def test_get_top_users(mock_client):
    result = await run_tool("get_top_users", {"period": "today", "limit": 1}, mock_client)
    assert result == [{"user": "alice@example.com", "events": 42}]
    mock_client.top_users.assert_awaited_once_with(period="today", limit=1)


async def test_get_top_policies(mock_client):
    result = await run_tool("get_top_policies", {"period": "week"}, mock_client)
    assert result == [{"policy": "PII-Exfiltration", "count": 19}]
    mock_client.top_policies.assert_awaited_once_with(period="week", limit=5)


async def test_get_detection_breakdown(mock_client):
    result = await run_tool("get_detection_breakdown", {}, mock_client)
    assert result == {"file_upload": 50, "usb": 12}
    mock_client.detection_breakdown.assert_awaited_once()


async def test_get_top_risky_users(mock_client):
    result = await run_tool("get_top_risky_users", {"period": "week", "limit": 3}, mock_client)
    assert result[0]["user"] == "bob@example.com"
    mock_client.top_risky_users.assert_awaited_once_with(period="week", limit=3)


async def test_get_top_devices(mock_client):
    result = await run_tool("get_top_devices", {"period": "week"}, mock_client)
    assert result[0]["device"] == "DESKTOP-ABC"
    mock_client.top_devices.assert_awaited_once_with(period="week", limit=10)


async def test_get_event_summary(mock_client):
    result = await run_tool("get_event_summary", {"period": "today"}, mock_client)
    assert result["total_events"] == 120
    assert result["unique_users"] == 8
    mock_client.event_summary.assert_awaited_once_with(period="today")


async def test_unknown_tool_raises(mock_client):
    with pytest.raises(ValueError, match="Unknown tool"):
        await run_tool("nonexistent_tool", {}, mock_client)
