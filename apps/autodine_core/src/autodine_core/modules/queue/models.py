from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from autodine_core.infrastructure.database import Base


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class QueueSnapshot(Base):
    __tablename__ = "queue_snapshots"

    store_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    zone_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    waiting_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    estimated_wait_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, onupdate=_utc_now)
