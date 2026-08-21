from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from uuid import uuid4

from sqlalchemy import DateTime, Enum as SqlEnum, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from autodine_core.infrastructure.database import Base


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AlarmStatus(str, Enum):
    OPEN = "OPEN"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"


class Alarm(Base):
    __tablename__ = "alarms"
    __table_args__ = (UniqueConstraint("store_id", "source_key", name="uq_alarms_store_source_key"),)

    alarm_id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: uuid4().hex)
    store_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_key: Mapped[str] = mapped_column(String(128), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    message: Mapped[str] = mapped_column(String(512), nullable=False)
    status: Mapped[AlarmStatus] = mapped_column(SqlEnum(AlarmStatus, native_enum=False, validate_strings=True), nullable=False, default=AlarmStatus.OPEN)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now)
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
