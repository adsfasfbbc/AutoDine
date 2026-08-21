from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, List, Dict
from uuid import uuid4

from sqlalchemy import JSON, DateTime, Enum as SqlEnum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from autodine_core.infrastructure.database import Base


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ProductionTaskStatus(str, Enum):
    PENDING = "PENDING"
    PRODUCING = "PRODUCING"
    READY = "READY"
    COMPLETED = "COMPLETED"
    CANCELED = "CANCELED"


class ProductionTask(Base):
    __tablename__ = "production_tasks"

    task_id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: uuid4().hex)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.order_id"), nullable=False, unique=True, index=True)
    store_id: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[ProductionTaskStatus] = mapped_column(
        SqlEnum(ProductionTaskStatus, native_enum=False, validate_strings=True),
        nullable=False,
        default=ProductionTaskStatus.PENDING,
    )
    pick_list: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, onupdate=_utc_now)


__all__ = ["ProductionTask", "ProductionTaskStatus"]
