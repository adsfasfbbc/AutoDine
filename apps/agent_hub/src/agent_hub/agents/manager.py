from __future__ import annotations

from ..config import Settings
from ..core_client import CoreClient
from ..llm.base import LLMAdapter
from ..tools import TOOL_REGISTRY
from .base import Agent

MANAGER_SYSTEM_PROMPT = """你是 AutoDine 无人甜品店的店长助手。你负责库存与质量查询、告警处理、\
排队/客流查看，以及运营总结。

规则：
- 只能通过工具调用中台接口，严禁直接访问数据库。
- 运营总结使用 get_analytics_summary，时间窗缺省为最近 24 小时。
- 用简洁的中文回复，突出重点。"""


def build_manager_agent(adapter: LLMAdapter, client: CoreClient, settings: Settings) -> Agent:
    tools = [
        TOOL_REGISTRY["list_inventory"],
        TOOL_REGISTRY["list_alarms"],
        TOOL_REGISTRY["acknowledge_alarm"],
        TOOL_REGISTRY["resolve_alarm"],
        TOOL_REGISTRY["list_queue_snapshots"],
        TOOL_REGISTRY["get_analytics_summary"],
        TOOL_REGISTRY["issue_device_command"],
        TOOL_REGISTRY["list_device_commands"],
    ]
    return Agent(
        name="manager",
        system_prompt=MANAGER_SYSTEM_PROMPT,
        tools=tools,
        adapter=adapter,
        client=client,
        settings=settings,
    )
