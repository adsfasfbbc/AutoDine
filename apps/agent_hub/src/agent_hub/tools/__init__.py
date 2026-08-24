from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from ..config import Settings
from ..core_client import CoreClient
from ..errors import CoreAPIError
from . import alarm, analytics, device, inventory, menu, order, production, queue
from .base import ToolDefinition

ALL_TOOLS: List[ToolDefinition] = [
    menu.LIST_MENU,
    menu.GET_MENU_ITEM,
    order.CREATE_ORDER,
    order.GET_ORDER,
    order.CANCEL_ORDER,
    production.START_PRODUCTION_TASK,
    production.READY_PRODUCTION_TASK,
    production.COMPLETE_PRODUCTION_TASK,
    inventory.LIST_INVENTORY,
    alarm.LIST_ALARMS,
    alarm.ACKNOWLEDGE_ALARM,
    alarm.RESOLVE_ALARM,
    queue.LIST_QUEUE_SNAPSHOTS,
    analytics.GET_ANALYTICS_SUMMARY,
    device.ISSUE_DEVICE_COMMAND,
    device.LIST_DEVICE_COMMANDS,
]

TOOL_REGISTRY: Dict[str, ToolDefinition] = {tool.name: tool for tool in ALL_TOOLS}


def get_tool(name: str) -> Optional[ToolDefinition]:
    return TOOL_REGISTRY.get(name)


def execute_tool(
    name: str,
    client: CoreClient,
    settings: Settings,
    arguments: Dict[str, Any],
) -> str:
    """Execute a tool and serialize its result (or error) as a JSON string.

    The JSON-string form is the common representation consumed both by the
    OpenAI-compatible adapter (as tool-result content) and by the scripted
    fallback adapter (parsed back into a dict).
    """
    tool = TOOL_REGISTRY.get(name)
    if tool is None:
        return json.dumps({"error": f"unknown tool '{name}'"}, ensure_ascii=False)

    try:
        result = tool.handler(client, settings, **arguments)
    except CoreAPIError as exc:
        return json.dumps(
            {"error": exc.message, "code": exc.code, "status_code": exc.status_code},
            ensure_ascii=False,
            default=str,
        )
    except Exception as exc:  # noqa: BLE001 - surface any handler failure to the agent
        return json.dumps(
            {"error": f"{type(exc).__name__}: {exc}"},
            ensure_ascii=False,
            default=str,
        )

    return json.dumps(result, ensure_ascii=False, default=str)
