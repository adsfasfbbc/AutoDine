from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Optional
from uuid import uuid4

from sqlalchemy import DateTime, Enum as SqlEnum, ForeignKey, ForeignKeyConstraint, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from autodine_core.infrastructure.database import Base


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class MovementType(str, Enum):
    RESERVE = "RESERVE"
    RELEASE = "RELEASE"
    CONSUME = "CONSUME"
    ADJUST = "ADJUST"


class ReservationStatus(str, Enum):
    ACTIVE = "ACTIVE"
    RELEASED = "RELEASED"
    CONSUMED = "CONSUMED"


class InventoryReservation(Base):
    __tablename__ = "inventory_reservations"
    __table_args__ = (
        ForeignKeyConstraint(
            ["store_id", "ingredient_id", "location_id"],
            ["inventories.store_id", "inventories.ingredient_id", "inventories.location_id"],
            name="fk_reservations_inventory_bucket",
        ),
    )

    reservation_id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: uuid4().hex)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.order_id"), nullable=False, index=True)
    store_id: Mapped[str] = mapped_column(String(64), nullable=False)
    ingredient_id: Mapped[str] = mapped_column(ForeignKey("ingredients.ingredient_id"), nullable=False)
    location_id: Mapped[str] = mapped_column(String(64), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False)
    status: Mapped[ReservationStatus] = mapped_column(
        SqlEnum(ReservationStatus, native_enum=False, validate_strings=True),
        nullable=False,
        default=ReservationStatus.ACTIVE,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now)


class InventoryMovement(Base):
    __tablename__ = "inventory_movements"
    __table_args__ = (
        ForeignKeyConstraint(
            ["store_id", "ingredient_id", "location_id"],
            ["inventories.store_id", "inventories.ingredient_id", "inventories.location_id"],
            name="fk_movements_inventory_bucket",
        ),
    )

    movement_id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: uuid4().hex)
    order_id: Mapped[Optional[str]] = mapped_column(ForeignKey("orders.order_id"), nullable=True, index=True)
    reservation_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("inventory_reservations.reservation_id"), nullable=True
    )
    store_id: Mapped[str] = mapped_column(String(64), nullable=False)
    ingredient_id: Mapped[str] = mapped_column(ForeignKey("ingredients.ingredient_id"), nullable=False)
    location_id: Mapped[str] = mapped_column(String(64), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False)
    movement_type: Mapped[MovementType] = mapped_column(
        SqlEnum(MovementType, native_enum=False, validate_strings=True),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now)


__all__ = ["InventoryMovement", "InventoryReservation", "MovementType", "ReservationStatus"]
