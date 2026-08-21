from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional
from uuid import uuid4

from sqlalchemy import JSON, DateTime, Enum as SqlEnum, String
from sqlalchemy.orm import Mapped, mapped_column

from autodine_core.infrastructure.database import Base


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class DeviceCommandStatus(str, Enum):
    PENDING = "PENDING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    TIMED_OUT = "TIMED_OUT"


class DeviceCommand(Base):
    __tablename__ = "device_commands"

    command_id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: uuid4().hex)
    store_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    device_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    command_type: Mapped[str] = mapped_column(String(64), nullable=False)
    parameters: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[DeviceCommandStatus] = mapped_column(SqlEnum(DeviceCommandStatus, native_enum=False, validate_strings=True), nullable=False, default=DeviceCommandStatus.PENDING)
    result: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
