from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from autodine_core.infrastructure.event_bus.publisher import EventPublisher
from autodine_core.modules.event.models import EventOutbox, PublishStatus


def dispatch_pending(session: Session, publisher: EventPublisher) -> int:
    """Publish committed outbox rows; failures are recorded after business commit."""
    rows = session.scalars(select(EventOutbox).where(EventOutbox.publish_status == PublishStatus.PENDING).order_by(EventOutbox.created_at)).all()
    delivered = 0
    for row in rows:
        envelope: Dict[str, Any] = {
            "protocol": "ADP",
            "version": "1.0",
            "event_id": "outbox-" + row.outbox_id,
            "trace_id": row.trace_id,
            "event_type": row.event_type,
            "severity": row.severity,
            "timestamp": row.created_at.isoformat() if row.created_at else datetime.now(timezone.utc).isoformat(),
            "store_id": row.store_id,
            "source": {"module": "core"},
            "payload": row.payload,
        }
        try:
            publisher.publish(envelope)
            row.publish_status = PublishStatus.PUBLISHED
            delivered += 1
        except Exception:
            row.publish_status = PublishStatus.FAILED
    session.commit()
    return delivered


def dispatch_app_outbox(session: Session, app: Any) -> int:
    """Publish committed outbox rows through the app's configured publisher."""
    publisher = getattr(getattr(app, "state", None), "event_publisher", None)
    if publisher is None:
        return 0
    return dispatch_pending(session, publisher)
