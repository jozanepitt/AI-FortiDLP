"""Gemini-backed agent loop with FortiDLP tool-use.

Uses the new `google-genai` SDK (v1+) with a manual agentic loop so each
tool call is dispatched through the async FortiDLPClient instance owned
by the FastAPI request context.

ClaudeAgent is kept as an alias of GeminiAgent so existing imports work.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from google import genai
from google.genai import types

from .tools import TOOLS, run_tool

log = logging.getLogger(__name__)

MAX_ITERATIONS = 5

SYSTEM_PROMPT = (
    "You are a read-only FortiDLP security analyst assistant for Capitec Bank. "
    "Answer questions about DLP events, user activity, policy violations, and "
    "endpoint detections by calling the available tools.\n"
    "Guidelines:\n"
    "- Only use the provided tools. Never fabricate data.\n"
    "- All tools are strictly read-only.\n"
    "- Be terse — use bullet lists, not prose.\n"
    "- If a tool returns empty results, say so plainly.\n"
    "- If the event cache has no data yet, explain that the stream needs time "
    "to accumulate events."
)


def _build_tools() -> list[types.Tool]:
    """Convert our JSON-Schema TOOLS list to Gemini FunctionDeclaration objects."""
    _type_map = {
        "string": types.Type.STRING,
        "integer": types.Type.INTEGER,
        "number": types.Type.NUMBER,
        "boolean": types.Type.BOOLEAN,
        "array": types.Type.ARRAY,
        "object": types.Type.OBJECT,
    }

    def _to_schema(spec: dict) -> types.Schema:
        kwargs: dict[str, Any] = {
            "type": _type_map.get(spec.get("type", "string"), types.Type.STRING),
        }
        if "description" in spec:
            kwargs["description"] = spec["description"]
        if "enum" in spec:
            kwargs["enum"] = spec["enum"]
        return types.Schema(**kwargs)

    declarations = []
    for t in TOOLS:
        props = {
            name: _to_schema(spec)
            for name, spec in t["input_schema"].get("properties", {}).items()
        }
        declarations.append(
            types.FunctionDeclaration(
                name=t["name"],
                description=t["description"],
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties=props,
                ),
            )
        )
    return [types.Tool(function_declarations=declarations)]


class GeminiAgent:
    """Agentic loop backed by Google Gemini 2.0 Flash with FortiDLP tool-use."""

    def __init__(self, api_key: str, model: str = "gemini-2.0-flash") -> None:
        self._client = genai.Client(api_key=api_key)
        self._model = model
        self._tools = _build_tools()

    async def ask(self, user_message: str, fortidlp: Any) -> dict[str, Any]:
        """Run the agentic loop for one user question.

        Returns dict with `answer` (final text) and `trace` (tool call log).
        """
        contents: list[types.Content] = [
            types.Content(role="user", parts=[types.Part(text=user_message)])
        ]
        trace: list[dict] = []

        for iteration in range(MAX_ITERATIONS):
            response = await self._client.aio.models.generate_content(
                model=self._model,
                contents=contents,
                config=types.GenerateContentConfig(
                    tools=self._tools,
                    system_instruction=SYSTEM_PROMPT,
                ),
            )

            # Extract text and function calls from response parts
            text_parts: list[str] = []
            function_calls: list[types.FunctionCall] = []

            try:
                parts = response.candidates[0].content.parts
            except (IndexError, AttributeError):
                break

            for part in parts:
                if part.function_call and part.function_call.name:
                    function_calls.append(part.function_call)
                elif part.text:
                    text_parts.append(part.text)

            # No function calls → final answer
            if not function_calls:
                return {"answer": "".join(text_parts).strip() or "(no response)", "trace": trace}

            # Append model turn
            contents.append(types.Content(role="model", parts=parts))

            # Execute each tool and collect function_response parts
            response_parts: list[types.Part] = []
            for fc in function_calls:
                args = dict(fc.args) if fc.args else {}
                try:
                    result = await run_tool(fc.name, args, fortidlp)
                    is_error = False
                except Exception as exc:  # noqa: BLE001
                    log.exception("tool %s failed", fc.name)
                    result = {"error": str(exc)}
                    is_error = True

                trace.append({
                    "step": iteration + 1,
                    "tool": fc.name,
                    "args": args,
                    "is_error": is_error,
                    "result_preview": json.dumps(result, default=str)[:500],
                })

                response_parts.append(
                    types.Part(
                        function_response=types.FunctionResponse(
                            name=fc.name,
                            response={"result": result},
                        )
                    )
                )

            contents.append(types.Content(role="user", parts=response_parts))

        return {
            "answer": f"Agent reached the {MAX_ITERATIONS}-step limit. Try a more specific question.",
            "trace": trace,
        }


# Backward-compatible alias — main.py imports ClaudeAgent
ClaudeAgent = GeminiAgent
