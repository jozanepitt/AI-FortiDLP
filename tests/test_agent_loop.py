"""Tests for the Claude agent loop with mocked Anthropic + FortiDLP."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.agent.claude_client import ClaudeAgent


class _Block(SimpleNamespace):
    pass


def _text_block(text: str) -> _Block:
    return _Block(type="text", text=text)


def _tool_use_block(id_: str, name: str, input_: dict) -> _Block:
    return _Block(type="tool_use", id=id_, name=name, input=input_)


@pytest.mark.asyncio
async def test_agent_end_turn_without_tool_call():
    agent = ClaudeAgent(api_key="x", model="claude-sonnet-4-5")
    agent._client = MagicMock()
    agent._client.messages = MagicMock()
    agent._client.messages.create = AsyncMock(
        return_value=SimpleNamespace(
            stop_reason="end_turn",
            content=[_text_block("All good.")],
        )
    )

    result = await agent.ask("hello", fortidlp=MagicMock())
    assert result["answer"] == "All good."
    assert result["trace"] == []


@pytest.mark.asyncio
async def test_agent_executes_tool_then_answers():
    agent = ClaudeAgent(api_key="x", model="claude-sonnet-4-5")
    agent._client = MagicMock()
    agent._client.messages = MagicMock()

    # First response: tool call. Second response: final text.
    agent._client.messages.create = AsyncMock(
        side_effect=[
            SimpleNamespace(
                stop_reason="tool_use",
                content=[
                    _tool_use_block(
                        "tool_1",
                        "get_top_users",
                        {"period": "today", "limit": 1},
                    )
                ],
            ),
            SimpleNamespace(
                stop_reason="end_turn",
                content=[_text_block("Top user today: alice (42 events).")],
            ),
        ]
    )

    fortidlp = MagicMock()
    fortidlp.top_users = AsyncMock(
        return_value=[{"user": "alice@example.com", "events": 42}]
    )

    result = await agent.ask("who is the top user today?", fortidlp)
    assert "alice" in result["answer"]
    assert len(result["trace"]) == 1
    assert result["trace"][0]["tool"] == "get_top_users"
    assert result["trace"][0]["is_error"] is False
    fortidlp.top_users.assert_awaited_once()
