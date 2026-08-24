from __future__ import annotations

from ..config import Settings
from ..core_client import CoreClient
from .base import ToolDefinition


def issue_device_command(
    client: CoreClient,
    settings: Settings,
    *,
    device_id: str,
    command_type: str,
    store_id: str | None = None,
    parameters=None,
):
    store_id = store_id or settings.default_store_id
    body = {"store_id": store_id, "command_type": command_type, "parameters": parameters or {}}
    return client.request("POST", f"/api/v1/devices/{device_id}/commands", json=body)


def list_device_commands(
    client: CoreClient,
    settings: Settings,
    *,
    device_id: str,
    store_id: str | None = None,
):
    store_id = store_id or settings.default_store_id
    return client.request(
        "GET", f"/api/v1/devices/{device_id}/commands", params={"store_id": store_id}
    )


ISSUE_DEVICE_COMMAND = ToolDefinition(
    name="issue_device_command",
    description="向设备下发命令（如温控、灯光等）。",
    parameters={
        "type": "object",
        "properties": {
            "device_id": {"type": "string", "description": "设备 ID"},
            "command_type": {"type": "string", "description": "命令类型"},
            "store_id": {"type": "string", "description": "门店 ID，缺省使用默认门店"},
            "parameters": {"type": "object", "description": "命令参数"},
        },
        "required": ["device_id", "command_type"],
        "additionalProperties": False,
    },
    handler=issue_device_command,
)

LIST_DEVICE_COMMANDS = ToolDefinition(
    name="list_device_commands",
    description="查询设备的命令历史。",
    parameters={
        "type": "object",
        "properties": {
            "device_id": {"type": "string", "description": "设备 ID"},
            "store_id": {"type": "string", "description": "门店 ID，缺省使用默认门店"},
        },
        "required": ["device_id"],
        "additionalProperties": False,
    },
    handler=list_device_commands,
)
