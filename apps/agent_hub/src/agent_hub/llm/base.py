from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Protocol

from ..tools.base import ToolDefinition


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict


@dataclass
class ChatMessage:
    role: str  # "system" | "user" | "assistant" | "tool"
    content: str | None = None
    tool_calls: List[ToolCall] = field(default_factory=list)
    tool_call_id: str | None = None


@dataclass
class LLMResponse:
    text: str | None = None
    tool_calls: List[ToolCall] = field(default_factory=list)

    @property
    def wants_tool_use(self) -> bool:
        return bool(self.tool_calls)


class LLMAdapter(Protocol):
    def generate(
        self,
        messages: List[ChatMessage],
        tools: List[ToolDefinition],
    ) -> LLMResponse: ...
