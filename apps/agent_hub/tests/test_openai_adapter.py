from __future__ import annotations

from types import SimpleNamespace

from agent_hub.llm.base import ChatMessage, ToolCall
from agent_hub.llm.openai_adapter import OpenAICompatAdapter
from agent_hub.tools.base import ToolDefinition


def _adapter_with_fake_client(response):
    fake = SimpleNamespace()
    fake.chat = SimpleNamespace()
    fake.chat.completions = SimpleNamespace()
    fake.chat.completions.create = lambda **kwargs: response
    return OpenAICompatAdapter(base_url="x", api_key="x", model="test-model", client=fake)


def _tool():
    return ToolDefinition(
        name="list_menu",
        description="list menu",
        parameters={"type": "object", "properties": {}},
        handler=lambda *a, **k: None,
    )


def test_to_tool_format():
    fmt = OpenAICompatAdapter._to_tool(_tool())
    assert fmt["type"] == "function"
    assert fmt["function"]["name"] == "list_menu"
    assert fmt["function"]["parameters"]["type"] == "object"


def test_to_message_formats_assistant_tool_calls():
    m = ChatMessage(role="assistant", content=None, tool_calls=[ToolCall(id="c1", name="list_menu", arguments={"store_id": "s"})])
    fmt = OpenAICompatAdapter._to_message(m)
    assert fmt["role"] == "assistant"
    assert fmt["tool_calls"][0]["id"] == "c1"
    assert fmt["tool_calls"][0]["function"]["name"] == "list_menu"
    assert '"store_id"' in fmt["tool_calls"][0]["function"]["arguments"]


def test_generate_parses_tool_calls():
    tc = SimpleNamespace(id="call_1", function=SimpleNamespace(name="list_menu", arguments='{"store_id": "store-main"}'))
    msg = SimpleNamespace(content=None, tool_calls=[tc])
    response = SimpleNamespace(choices=[SimpleNamespace(message=msg)])
    adapter = _adapter_with_fake_client(response)

    result = adapter.generate([ChatMessage(role="user", content="hi")], [_tool()])
    assert result.wants_tool_use
    assert result.tool_calls[0].name == "list_menu"
    assert result.tool_calls[0].arguments == {"store_id": "store-main"}


def test_generate_returns_text_when_no_tool_calls():
    msg = SimpleNamespace(content="推荐拿铁", tool_calls=None)
    response = SimpleNamespace(choices=[SimpleNamespace(message=msg)])
    adapter = _adapter_with_fake_client(response)

    result = adapter.generate([ChatMessage(role="user", content="hi")], [_tool()])
    assert not result.wants_tool_use
    assert result.text == "推荐拿铁"
