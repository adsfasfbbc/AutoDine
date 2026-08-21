from __future__ import annotations

from datetime import datetime
from typing import Any, Dict

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from autodine_core.modules.alarm.models import Alarm, AlarmStatus
from autodine_core.modules.inventory.models import Inventory
from autodine_core.modules.order.models import Order
from autodine_core.modules.production.models import ProductionTask


def summary(session: Session, *, store_id: str, start: datetime, end: datetime) -> Dict[str, Any]:
    in_window = lambda column: (column >= start, column <= end)
    metrics = {
        "order_count": session.scalar(select(func.count()).select_from(Order).where(Order.store_id == store_id, *in_window(Order.created_at))) or 0,
        "production_task_count": session.scalar(select(func.count()).select_from(ProductionTask).where(ProductionTask.store_id == store_id, *in_window(ProductionTask.created_at))) or 0,
        "inventory_location_count": session.scalar(select(func.count()).select_from(Inventory).where(Inventory.store_id == store_id)) or 0,
        "open_alarm_count": session.scalar(select(func.count()).select_from(Alarm).where(Alarm.store_id == store_id, Alarm.status.in_([AlarmStatus.OPEN, AlarmStatus.ACKNOWLEDGED]))) or 0,
    }
    return {
        "window": {"start": start.isoformat(), "end": end.isoformat()},
        "metrics": metrics,
        "definitions": {
            "order_count": "Orders created in the requested time window.",
            "production_task_count": "Production tasks created in the requested time window.",
            "inventory_location_count": "Inventory snapshots currently stored for the store.",
            "open_alarm_count": "Alarms still open or acknowledged at query time.",
        },
    }
