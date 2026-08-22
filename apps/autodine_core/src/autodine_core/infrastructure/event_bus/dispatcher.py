from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from autodine_core.infrastructure.event_bus.publisher import EventPublisher
from autodine_core.modules.event.models import EventOutbox, PublishStatus


_CLAIMABLE_STATUSES = (PublishStatus.PENDING, PublishStatus.FAILED)


def dispatch_pending(session: Session, publisher: EventPublisher) -> int:
    """Publish committed outbox rows; failures are recorded after business commit.

    Rows are claimed one at a time via an atomic PENDING/FAILED -> DISPATCHING
    flip, so concurrent dispatchers never publish the same row twice. FAILED
    rows stay claimable and are retried by the next dispatch round.
    """
    candidate_ids = session.scalars(
        select(EventOutbox.outbox_id)
        .where(EventOutbox.publish_status.in_(_CLAIMABLE_STATUSES))
        .order_by(EventOutbox.created_at)
    ).all()
    delivered = 0
    for outbox_id in candidate_ids:
        claimed = session.execute(
            update(EventOutbox)
            .where(
                EventOutbox.outbox_id == outbox_id,
                EventOutbox.publish_status.in_(_CLAIMABLE_STATUSES),
            )
            .values(publish_status=PublishStatus.DISPATCHING)
        ).rowcount
        session.commit()
        if claimed != 1:
            # A concurrent dispatcher claimed this row first.
            continue
        row = session.get(EventOutbox, outbox_id)
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
