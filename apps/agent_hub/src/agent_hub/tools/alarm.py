from __future__ import annotations

from ..config import Settings
from ..core_client import CoreClient
from .base import ToolDefinition


def list_alarms(client: CoreClient, settings: Settings, *, store_id: str | None = None):
    store_id = store_id or settings.default_store_id
    return client.request("GET", "/api/v1/alarms", params={"store_id": store_id})


def acknowledge_alarm(client: CoreClient, settings: Settings, *, alarm_id: str):
    return client.request("POST", f"/api/v1/alarms/{alarm_id}/acknowledge")


def resolve_alarm(client: CoreClient, settings: Settings, *, alarm_id: str):
    return client.request("POST", f"/api/v1/alarms/{alarm_id}/resolve")


LIST_ALARMS = ToolDefinition(
    name="list_alarms",
    description="列出当前门店的告警（质量异常、安全事件等）。",
    parameters={
        "type": "object",
        "properties": {
            "store_id": {"type": "string", "description": "门店 ID，缺省使用默认门店"},
        },
        "additionalProperties": False,
    },
    handler=list_alarms,
)

ACKNOWLEDGE_ALARM = ToolDefinition(
    name="acknowledge_alarm",
    description="确认（ACKNOWLEDGED）一条告警。",
    parameters={
        "type": "object",
        "properties": {
            "alarm_id": {"type": "string", "description": "告警 ID"},
        },
        "required": ["alarm_id"],
        "additionalProperties": False,
    },
    handler=acknowledge_alarm,
)

RESOLVE_ALARM = ToolDefinition(
    name="resolve_alarm",
    description="解决（RESOLVED）一条告警。",
    parameters={
        "type": "object",
        "properties": {
            "alarm_id": {"type": "string", "description": "告警 ID"},
        },
        "required": ["alarm_id"],
        "additionalProperties": False,
    },
    handler=resolve_alarm,
)
