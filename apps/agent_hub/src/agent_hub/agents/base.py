from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..config import Settings
from ..core_client import CoreClient
from ..llm.base import ChatMessage, LLMAdapter, ToolCall
from ..tools import execute_tool
from ..tools.base import ToolDefinition


class Agent:
    """A tool-calling agent: system prompt + tool set + the execution loop."""

    def __init__(
        self,
        *,
        name: str,
        system_prompt: str,
        tools: List[ToolDefinition],
        adapter: LLMAdapter,
        client: CoreClient,
        settings: Settings,
    ) -> None:
        self.name = name
        self.system_prompt = system_prompt
        self.tools = tools
        self.adapter = adapter
        self.client = client
        self.settings = settings

    def run(self, message: str, history: Optional[List[Dict[str, str]]] = None) -> str:
        messages: List[ChatMessage] = [ChatMessage(role="system", content=self.system_prompt)]
        for turn in history or []:
            role = turn.get("role")
            if role in ("user", "assistant"):
                messages.append(ChatMessage(role=role, content=turn.get("content", "")))
        messages.append(ChatMessage(role="user", content=message))

        for _ in range(self.settings.max_tool_iterations):
            response = self.adapter.generate(messages, self.tools)
            if not response.wants_tool_use:
                return response.text or ""

            messages.append(
                ChatMessage(role="assistant", content=response.text, tool_calls=response.tool_calls)
            )
            for call in response.tool_calls:
                result = execute_tool(call.name, self.client, self.settings, call.arguments)
                messages.append(ChatMessage(role="tool", content=result, tool_call_id=call.id))

        return "处理步骤过多，已中止。请简化你的请求。"
