from __future__ import annotations

from ..config import Settings
from ..core_client import CoreClient
from ..llm.base import LLMAdapter
from ..tools import TOOL_REGISTRY
from .base import Agent

KITCHEN_SYSTEM_PROMPT = """你是 AutoDine 无人甜品店的后厨助手。你负责解答生产相关问题：\
查看订单的生产任务与领料清单（pick_list），并推进生产状态 PENDING → PRODUCING → READY → COMPLETED。

规则：
- 只能通过工具调用中台接口，严禁直接访问数据库。
- 生产任务与领料清单通过订单（order_id）获取（get_order 返回其中的 task），再按任务 ID 推进。
- 完成生产（complete）时需给出 actual_consumption（实际消耗，含 ingredient_id / location_id / quantity），\
通常与领料清单一致。
- 用简洁的中文回复。"""


def build_kitchen_agent(adapter: LLMAdapter, client: CoreClient, settings: Settings) -> Agent:
    tools = [
        TOOL_REGISTRY["get_order"],
        TOOL_REGISTRY["start_production_task"],
        TOOL_REGISTRY["ready_production_task"],
        TOOL_REGISTRY["complete_production_task"],
    ]
    return Agent(
        name="kitchen",
        system_prompt=KITCHEN_SYSTEM_PROMPT,
        tools=tools,
        adapter=adapter,
        client=client,
        settings=settings,
    )
