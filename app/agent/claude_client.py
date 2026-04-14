"""Anthropic Claude tool-use loop for the FortiDLP agent.

Uses a manual agentic loop (rather than the SDK tool runner) because we
need to dispatch each tool call through an async FortiDLPClient instance
that is owned by the FastAPI request - the tool runner would require
global or closure-captured state that's awkward in a web handler.

Prompt caching: the system prompt + tool list are stable across every
request, so we mark the last system text block with cache_control. After
the first request of a 5-minute window, subsequent requests hit the
cache and pay ~0.1x for the shared prefix.
"""
from __future__ import annotations

import logging
from typing import Any

from anthropic import AsyncAnthropic

from .fortidlp_client import FortiDLPClient
from .tools import DISPATCH, TOOLS, run_tool

logger = logging.getLogger(__name__)

MAX_ITERATIONS = 5

SYSTEM_PROMPT = (
    "You are a read-only assistant for a FortiDLP (Fortinet Data Loss "
    "Prevention) console. A security engineer asks you operational "
    "questions about their tenant; you answer using the provided tools. "
    "\n\nGuidelines:\n"
    "- You may ONLY use the provided tools. Never claim to access the "
    "console any other way.\n"
    "- All tools are strictly read-only. Never imply you can change "
    "policy, quarantine a device, or modify any state.\n"
    "- When the user asks about unhealthy devices, always include both "
    "the reason and a short suggested remediation step per device.\n"
    "- Be terse. Security engineers scan answers fast; use short "
    "paragraphs or bullet lists, not prose.\n"
    "- If a tool returns an empty result, say so plainly. Do not make up "
    "data.\n"
    "- If you are unsure which tool to use, ask the user for "
    "clarification before calling a tool."
)


class ClaudeAgent:
    def __init__(self, api_key: str, model: str) -> None:
        self._client = AsyncAnthropic(api_key=api_key)
        self._model = model

    async def ask(
        self,
        user_message: str,
        fortidlp: FortiDLPClient,
    ) -> dict[str, Any]:
        """Run the agentic loop for a single user question.

        Returns a dict with `answer` (final text) and `trace` (list of
        tool_name/args/result tuples) for display in the UI.
        """
        messages: list[dict] = [{"role": "user", "content": user_message}]
        trace: list[dict] = []

        for step in range(MAX_ITERATIONS):
            response = await self._client.messages.create(
                model=self._model,
                max_tokens=2048,
                system=[
                    {
                        "type": "text",
                        "text": SYSTEM_PROMPT,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                tools=TOOLS,
                messages=messages,
            )

            if response.stop_reason == "end_turn":
                answer = _extract_text(response.content)
                return {"answer": answer, "trace": trace}

            if response.stop_reason != "tool_use":
                # Unexpected stop (max_tokens, refusal, etc.). Return what we have.
                answer = _extract_text(response.content) or (
                    f"Agent stopped unexpectedly: {response.stop_reason}"
                )
                return {"answer": answer, "trace": trace}

            # Append assistant turn (must include the raw content blocks so
            # tool_use IDs line up with tool_results below).
            messages.append({"role": "assistant", "content": response.content})

            tool_results: list[dict] = []
            for block in response.content:
                if getattr(block, "type", None) != "tool_use":
                    continue

                name = block.name
                args = block.input or {}

                if name not in DISPATCH:
                    result_text = f"Error: unknown tool '{name}'"
                    is_error = True
                else:
                    try:
                        result = await run_tool(name, args, fortidlp)
                        result_text = _to_text(result)
                        is_error = False
                    except Exception as exc:  # noqa: BLE001
                        logger.exception("tool %s failed", name)
                        result_text = f"Error executing {name}: {exc}"
                        is_error = True

                trace.append(
                    {
                        "step": step,
                        "tool": name,
                        "args": args,
                        "is_error": is_error,
                        "result_preview": result_text[:500],
                    }
                )

                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result_text,
                        "is_error": is_error,
                    }
                )

            messages.append({"role": "user", "content": tool_results})

        return {
            "answer": (
                f"Agent hit the max-iteration cap ({MAX_ITERATIONS}). "
                "Try asking a more specific question."
            ),
            "trace": trace,
        }


def _extract_text(content: list) -> str:
    parts: list[str] = []
    for block in content:
        if getattr(block, "type", None) == "text":
            parts.append(block.text)
    return "\n".join(parts).strip()


def _to_text(value: Any) -> str:
    import json

    try:
        return json.dumps(value, default=str, ensure_ascii=False)
    except (TypeError, ValueError):
        return str(value)
