from __future__ import annotations

import json
from typing import Any, Dict, List

from ..tools.base import ToolDefinition
from .base import ChatMessage, LLMResponse, ToolCall


class OpenAICompatAdapter:
    """Tool-calling adapter for any OpenAI-compatible endpoint.

    Works with Qwen (DashScope), DeepSeek, GLM (Zhipu) and any other provider
    that exposes ``POST /chat/completions`` with the OpenAI function-calling
    schema. Configure via ``base_url`` + ``api_key`` + ``model``.
    """

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        timeout: float = 60.0,
        client=None,
    ) -> None:
        self.model = model
        if client is None:
            # Imported lazily so the scripted (offline) path works even when the
            # optional `openai` package is not installed.
            from openai import OpenAI

            client = OpenAI(base_url=base_url, api_key=api_key, timeout=timeout)
        self._client = client

    def generate(
        self,
        messages: List[ChatMessage],
        tools: List[ToolDefinition],
    ) -> LLMResponse:
        kwargs: Dict[str, Any] = {
            "model": self.model,
            "messages": [self._to_message(m) for m in messages],
        }
        if tools:
            kwargs["tools"] = [self._to_tool(t) for t in tools]
            kwargs["tool_choice"] = "auto"

        response = self._client.chat.completions.create(**kwargs)
        message = response.choices[0].message

        if message.tool_calls:
            calls: List[ToolCall] = []
            for tc in message.tool_calls:
                try:
                    arguments = json.loads(tc.function.arguments or "{}")
                except json.JSONDecodeError:
                    arguments = {}
                calls.append(ToolCall(id=tc.id, name=tc.function.name, arguments=arguments))
            return LLMResponse(text=message.content or "", tool_calls=calls)

        return LLMResponse(text=message.content or "")

    @staticmethod
    def _to_message(m: ChatMessage) -> Dict[str, Any]:
        if m.role == "tool":
            return {"role": "tool", "tool_call_id": m.tool_call_id, "content": m.content or ""}
        if m.role == "assistant" and m.tool_calls:
            return {
                "role": "assistant",
                "content": m.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments, ensure_ascii=False),
                        },
                    }
                    for tc in m.tool_calls
                ],
            }
        return {"role": m.role, "content": m.content}

    @staticmethod
    def _to_tool(t: ToolDefinition) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description,
                "parameters": t.parameters,
            },
        }
