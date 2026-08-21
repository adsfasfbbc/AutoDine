from __future__ import annotations

from typing import Any, Dict, List

from sqlalchemy import select
from sqlalchemy.orm import Session

from autodine_core.modules.event.service import _append_outbox
from autodine_core.modules.queue.models import QueueSnapshot


def apply_queue_update(session: Session, *, store_id: str, trace_id: str, payload: Dict[str, Any]) -> None:
    zone_id = str(payload["zone_id"])
    snapshot = session.get(QueueSnapshot, (store_id, zone_id))
    if snapshot is None:
        snapshot = QueueSnapshot(store_id=store_id, zone_id=zone_id)
        session.add(snapshot)
    snapshot.waiting_count = int(payload["waiting_count"])
    snapshot.estimated_wait_seconds = payload.get("estimated_wait_seconds")
    _append_outbox(
        session,
        trace_id=trace_id,
        store_id=store_id,
        event_type="queue.updated",
        severity="info",
        payload={
            "zone_id": zone_id,
            "waiting_count": snapshot.waiting_count,
            "estimated_wait_seconds": snapshot.estimated_wait_seconds,
        },
    )


def list_queue_snapshots(session: Session, store_id: str) -> List[Dict[str, Any]]:
    snapshots = session.scalars(select(QueueSnapshot).where(QueueSnapshot.store_id == store_id).order_by(QueueSnapshot.zone_id)).all()
    return [
        {
            "zone_id": item.zone_id,
            "waiting_count": item.waiting_count,
            "estimated_wait_seconds": item.estimated_wait_seconds,
        }
        for item in snapshots
    ]
