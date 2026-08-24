from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from ..config import Settings
from ..core_client import CoreClient
from .base import ToolDefinition


def _parse_time(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc)
    text = str(value)
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def get_analytics_summary(
    client: CoreClient,
    settings: Settings,
    *,
    store_id: str | None = None,
    start=None,
    end=None,
):
    store_id = store_id or settings.default_store_id
    end_dt = _parse_time(end) or datetime.now(timezone.utc)
    start_dt = _parse_time(start) or (end_dt - timedelta(hours=24))
    params = {
        "store_id": store_id,
        "start": start_dt.isoformat(),
        "end": end_dt.isoformat(),
    }
    return client.request("GET", "/api/v1/analytics/summary", params=params)


GET_ANALYTICS_SUMMARY = ToolDefinition(
    name="get_analytics_summary",
    description=(
        "获取门店在给定时间窗内的运营汇总指标（订单数、生产任务数、库存位置数、未关闭告警数）。"
        "start/end 为 ISO 8601 时间；缺省为最近 24 小时。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "store_id": {"type": "string", "description": "门店 ID，缺省使用默认门店"},
            "start": {"type": "string", "description": "起始时间（ISO 8601）"},
            "end": {"type": "string", "description": "结束时间（ISO 8601）"},
        },
        "additionalProperties": False,
    },
    handler=get_analytics_summary,
)
