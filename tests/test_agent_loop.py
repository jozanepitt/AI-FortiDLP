"""Tests for the Gemini agent loop with mocked google-genai + FortiDLP."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agent.claude_client import GeminiAgent


def _make_part(text: str | None = None, fc_name: str | None = None, fc_args: dict | None = None):
    fc = SimpleNamespace(name=fc_name, args=fc_args or {}) if fc_name else None
    return SimpleNamespace(text=text, function_call=fc)


def _make_response(*parts):
    content = SimpleNamespace(parts=list(parts))
    candidate = SimpleNamespace(content=content)
    return SimpleNamespace(candidates=[candidate])


@pytest.mark.asyncio
async def test_agent_end_turn_without_tool_call():
    agent = GeminiAgent(api_key="fake", model="gemini-2.0-flash")

    fake_resp = _make_response(_make_part(text="All good."))

    with patch.object(agent._client.aio.models, "generate_content", new=AsyncMock(return_value=fake_resp)):
        result = await agent.ask("hello", fortidlp=MagicMock())

    assert result["answer"] == "All good."
    assert result["trace"] == []


@pytest.mark.asyncio
async def test_agent_executes_tool_then_answers():
    agent = GeminiAgent(api_key="fake", model="gemini-2.0-flash")

    tool_resp = _make_response(
        _make_part(fc_name="get_top_users", fc_args={"period": "today", "limit": 1})
    )
    final_resp = _make_response(_make_part(text="Top user today: alice (42 events)."))

    fortidlp = MagicMock()
    fortidlp.top_users = AsyncMock(return_value=[{"user": "alice@example.com", "events": 42}])

    with patch.object(
        agent._client.aio.models,
        "generate_content",
        new=AsyncMock(side_effect=[tool_resp, final_resp]),
    ):
        result = await agent.ask("who is the top user today?", fortidlp)

    assert "alice" in result["answer"]
    assert len(result["trace"]) == 1
    assert result["trace"][0]["tool"] == "get_top_users"
    assert result["trace"][0]["is_error"] is False
    fortidlp.top_users.assert_awaited_once()
