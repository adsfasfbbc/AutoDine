from __future__ import annotations

from pathlib import Path
import sys

from fastapi.testclient import TestClient
from sqlalchemy import select


ROOT = Path(__file__).resolve().parents[1] / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from autodine_core.infrastructure.event_bus.dispatcher import dispatch_pending
from autodine_core.infrastructure.event_bus.publisher import EventPublisher
from autodine_core.main import create_app
from autodine_core.modules.event.models import EventOutbox, PublishStatus


def _build_client() -> TestClient:
    app = create_app(database_url="sqlite+pysqlite:///:memory:")
    app.state.metadata.create_all(app.state.engine)
    return TestClient(app)


def _add_outbox_row(session, outbox_id: str, status: PublishStatus = PublishStatus.PENDING) -> None:
    session.add(
        EventOutbox(
            outbox_id=outbox_id,
            trace_id="trace-" + outbox_id,
            store_id="store-1",
            event_type="inventory.changed",
            severity="info",
            payload={"ingredient_id": "bean"},
            publish_status=status,
        )
    )
    session.commit()


class _RecordingPublisher(EventPublisher):
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.published: list[dict] = []

    def publish(self, event: dict) -> None:
        if self.fail:
            raise RuntimeError("broker unavailable")
        self.published.append(event)


def test_failed_rows_are_retried_by_the_next_dispatch_round() -> None:
    client = _build_client()
    session = client.app.state.session_factory()
    _add_outbox_row(session, "outbox-retry")

    failing = _RecordingPublisher(fail=True)
    assert dispatch_pending(session, failing) == 0
    row = session.get(EventOutbox, "outbox-retry")
    assert row.publish_status is PublishStatus.FAILED

    recovered = _RecordingPublisher()
    assert dispatch_pending(session, recovered) == 1
    assert [event["event_id"] for event in recovered.published] == ["outbox-outbox-retry"]
    session.expire_all()
    row = session.get(EventOutbox, "outbox-retry")
    assert row.publish_status is PublishStatus.PUBLISHED
    session.close()


def test_claimed_row_is_not_republished_by_a_competing_dispatcher() -> None:
    client = _build_client()
    session = client.app.state.session_factory()
    # Simulate a competitor that already claimed the row (PENDING -> DISPATCHING).
    _add_outbox_row(session, "outbox-claimed", status=PublishStatus.DISPATCHING)

    publisher = _RecordingPublisher()
    assert dispatch_pending(session, publisher) == 0
    assert publisher.published == []

    session.expire_all()
    row = session.get(EventOutbox, "outbox-claimed")
    assert row.publish_status is PublishStatus.DISPATCHING
    session.close()


def test_pending_rows_are_published_exactly_once_across_rounds() -> None:
    client = _build_client()
    session = client.app.state.session_factory()
    _add_outbox_row(session, "outbox-once-1")
    _add_outbox_row(session, "outbox-once-2")

    publisher = _RecordingPublisher()
    assert dispatch_pending(session, publisher) == 2
    assert dispatch_pending(session, publisher) == 0

    event_ids = [event["event_id"] for event in publisher.published]
    assert event_ids == ["outbox-outbox-once-1", "outbox-outbox-once-2"]
    statuses = session.scalars(select(EventOutbox.publish_status).order_by(EventOutbox.outbox_id)).all()
    assert statuses == [PublishStatus.PUBLISHED, PublishStatus.PUBLISHED]
    session.close()
