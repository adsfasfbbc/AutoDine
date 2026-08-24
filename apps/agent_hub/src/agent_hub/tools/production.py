from __future__ import annotations

from ..config import Settings
from ..core_client import CoreClient
from .base import ToolDefinition


def start_production_task(client: CoreClient, settings: Settings, *, task_id: str):
    return client.request("POST", f"/api/v1/production/tasks/{task_id}/start")


def ready_production_task(client: CoreClient, settings: Settings, *, task_id: str):
    return client.request("POST", f"/api/v1/production/tasks/{task_id}/ready")


def complete_production_task(
    client: CoreClient,
    settings: Settings,
    *,
    task_id: str,
    actual_consumption=None,
):
    body = {"actual_consumption": actual_consumption or []}
    return client.request("POST", f"/api/v1/production/tasks/{task_id}/complete", json=body)


START_PRODUCTION_TASK = ToolDefinition(
    name="start_production_task",
    description="开始生产任务（PENDING → PRODUCING）。",
    parameters={
        "type": "object",
        "properties": {
            "task_id": {"type": "string", "description": "生产任务 ID"},
        },
        "required": ["task_id"],
        "additionalProperties": False,
    },
    handler=start_production_task,
)

READY_PRODUCTION_TASK = ToolDefinition(
    name="ready_production_task",
    description="将生产任务置为出餐就绪（PRODUCING → READY）。",
    parameters={
        "type": "object",
        "properties": {
            "task_id": {"type": "string", "description": "生产任务 ID"},
        },
        "required": ["task_id"],
        "additionalProperties": False,
    },
    handler=ready_production_task,
)

COMPLETE_PRODUCTION_TASK = ToolDefinition(
    name="complete_production_task",
    description=(
        "完成生产任务（READY → COMPLETED）并按实际消耗核销库存预留。"
        "actual_consumption 需覆盖每个被跟踪（TRACKED）原料的预留，"
        "每项含 ingredient_id、location_id、quantity。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "task_id": {"type": "string", "description": "生产任务 ID"},
            "actual_consumption": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "ingredient_id": {"type": "string"},
                        "location_id": {"type": "string"},
                        "quantity": {"type": "string", "description": "消耗量（数值字符串）"},
                    },
                    "required": ["ingredient_id", "location_id", "quantity"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["task_id"],
        "additionalProperties": False,
    },
    handler=complete_production_task,
)
