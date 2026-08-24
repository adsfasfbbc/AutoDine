from __future__ import annotations

from ..config import Settings
from ..core_client import CoreClient
from .base import ToolDefinition


def list_queue_snapshots(client: CoreClient, settings: Settings, *, store_id: str | None = None):
    store_id = store_id or settings.default_store_id
    return client.request("GET", f"/api/v1/queues/{store_id}")


LIST_QUEUE_SNAPSHOTS = ToolDefinition(
    name="list_queue_snapshots",
    description="列出当前门店各区域（zone）的排队快照：等待人数与预估等待时长。",
    parameters={
        "type": "object",
        "properties": {
            "store_id": {"type": "string", "description": "门店 ID，缺省使用默认门店"},
        },
        "additionalProperties": False,
    },
    handler=list_queue_snapshots,
)
