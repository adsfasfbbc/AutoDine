from __future__ import annotations

from ..config import Settings
from ..core_client import CoreClient
from ..llm.base import LLMAdapter
from ..tools import TOOL_REGISTRY
from .base import Agent

CONSUMER_SYSTEM_PROMPT = """你是 AutoDine 无人甜品店的消费者点餐助手。你的职责是帮助顾客浏览菜单、\
根据可售状态推荐饮品/餐品、下单、查询订单进度、以及取消订单。

规则：
- 只能通过提供的工具调用中台接口，严禁猜测或编造数据。
- 下单前先确认商品处于 ON_SALE（在售）状态且数量充足。
- 推荐时优先给出在售且库存充足的商品，并说明价格。
- 用简洁友好的中文回复。"""


def build_consumer_agent(adapter: LLMAdapter, client: CoreClient, settings: Settings) -> Agent:
    tools = [
        TOOL_REGISTRY["list_menu"],
        TOOL_REGISTRY["get_menu_item"],
        TOOL_REGISTRY["create_order"],
        TOOL_REGISTRY["get_order"],
        TOOL_REGISTRY["cancel_order"],
    ]
    return Agent(
        name="consumer",
        system_prompt=CONSUMER_SYSTEM_PROMPT,
        tools=tools,
        adapter=adapter,
        client=client,
        settings=settings,
    )
