from __future__ import annotations

from ..config import Settings
from ..core_client import CoreClient
from .base import ToolDefinition


def list_menu(client: CoreClient, settings: Settings, *, store_id: str | None = None):
    store_id = store_id or settings.default_store_id
    return client.request("GET", "/api/v1/menu", params={"store_id": store_id})


def get_menu_item(
    client: CoreClient,
    settings: Settings,
    *,
    product_id: str,
    store_id: str | None = None,
):
    store_id = store_id or settings.default_store_id
    return client.request("GET", f"/api/v1/menu/{product_id}", params={"store_id": store_id})


LIST_MENU = ToolDefinition(
    name="list_menu",
    description="列出菜单及每种商品的可售状态、价格与可售数量。用于菜单浏览与推荐。",
    parameters={
        "type": "object",
        "properties": {
            "store_id": {"type": "string", "description": "门店 ID，缺省使用默认门店"},
        },
        "additionalProperties": False,
    },
    handler=list_menu,
)

GET_MENU_ITEM = ToolDefinition(
    name="get_menu_item",
    description="查询单个商品的详情（价格、状态、可售数量）。",
    parameters={
        "type": "object",
        "properties": {
            "product_id": {"type": "string", "description": "商品 ID"},
            "store_id": {"type": "string", "description": "门店 ID，缺省使用默认门店"},
        },
        "required": ["product_id"],
        "additionalProperties": False,
    },
    handler=get_menu_item,
)
