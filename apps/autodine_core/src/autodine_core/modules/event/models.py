from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict

from sqlalchemy import JSON, DateTime, Enum as SqlEnum, String
from sqlalchemy.orm import Mapped, mapped_column

from autodine_core.infrastructure.database import Base


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class EventInboxStatus(str, Enum):
    PROCESSED = "PROCESSED"
    IGNORED = "IGNORED"


class PublishStatus(str, Enum):
    PENDING = "PENDING"
    PUBLISHED = "PUBLISHED"
    FAILED = "FAILED"


class EventInbox(Base):
    __tablename__ = "event_inbox"

    event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    trace_id: Mapped[str] = mapped_column(String(64), nullable=False)
    store_id: Mapped[str] = mapped_column(String(64), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_module: Mapped[str] = mapped_column(String(64), nullable=False)
    source_device_id: Mapped[str] = mapped_column(String(64), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[EventInboxStatus] = mapped_column(
        SqlEnum(EventInboxStatus, native_enum=False, validate_strings=True),
        nullable=False,
    )
    payload: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now)


class EventOutbox(Base):
    __tablename__ = "event_outbox"

    outbox_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    trace_id: Mapped[str] = mapped_column(String(64), nullable=False)
    store_id: Mapped[str] = mapped_column(String(64), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    payload: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    publish_status: Mapped[PublishStatus] = mapped_column(
        SqlEnum(PublishStatus, native_enum=False, validate_strings=True),
        nullable=False,
        default=PublishStatus.PENDING,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now)
