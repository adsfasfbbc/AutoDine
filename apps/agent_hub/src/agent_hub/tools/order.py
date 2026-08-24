from __future__ import annotations

from uuid import uuid4

from ..config import Settings
from ..core_client import CoreClient
from .base import ToolDefinition


def create_order(
    client: CoreClient,
    settings: Settings,
    *,
    items,
    store_id: str | None = None,
    customer_id: str | None = None,
    idempotency_key: str | None = None,
):
    store_id = store_id or settings.default_store_id
    body = {
        "store_id": store_id,
        "customer_id": customer_id,
        "idempotency_key": idempotency_key or uuid4().hex,
        "items": items,
    }
    return client.request("POST", "/api/v1/orders", json=body)


def get_order(client: CoreClient, settings: Settings, *, order_id: str):
    return client.request("GET", f"/api/v1/orders/{order_id}")


def cancel_order(client: CoreClient, settings: Settings, *, order_id: str):
    return client.request("POST", f"/api/v1/orders/{order_id}/cancel")


CREATE_ORDER = ToolDefinition(
    name="create_order",
    description="创建订单并触发生产任务。items 中每项需给出 product_id 与 quantity。",
    parameters={
        "type": "object",
        "properties": {
            "store_id": {"type": "string", "description": "门店 ID，缺省使用默认门店"},
            "customer_id": {"type": "string", "description": "顾客 ID（可选）"},
            "idempotency_key": {"type": "string", "description": "幂等键（可选，缺省自动生成）"},
            "items": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "properties": {
                        "product_id": {"type": "string"},
                        "quantity": {"type": "integer", "minimum": 1},
                    },
                    "required": ["product_id", "quantity"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["items"],
        "additionalProperties": False,
    },
    handler=create_order,
)

GET_ORDER = ToolDefinition(
    name="get_order",
    description="查询订单详情（状态、金额、商品、以及关联的生产任务与领料清单）。",
    parameters={
        "type": "object",
        "properties": {
            "order_id": {"type": "string", "description": "订单 ID"},
        },
        "required": ["order_id"],
        "additionalProperties": False,
    },
    handler=get_order,
)

CANCEL_ORDER = ToolDefinition(
    name="cancel_order",
    description="取消订单并释放库存预留。",
    parameters={
        "type": "object",
        "properties": {
            "order_id": {"type": "string", "description": "订单 ID"},
        },
        "required": ["order_id"],
        "additionalProperties": False,
    },
    handler=cancel_order,
)
