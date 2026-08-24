from __future__ import annotations

from ..config import Settings
from ..core_client import CoreClient
from .base import ToolDefinition


def list_inventory(client: CoreClient, settings: Settings):
    return client.request("GET", "/api/v1/inventory")


LIST_INVENTORY = ToolDefinition(
    name="list_inventory",
    description="列出所有原料的库存快照（实物量、瑕疵量、预留量、可用量）。用于库存与质量查询。",
    parameters={"type": "object", "properties": {}, "additionalProperties": False},
    handler=list_inventory,
)
