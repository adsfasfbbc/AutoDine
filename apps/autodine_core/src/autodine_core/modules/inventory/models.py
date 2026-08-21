from __future__ import annotations

from decimal import Decimal
from enum import Enum
from typing import List

from sqlalchemy import Enum as SqlEnum
from sqlalchemy import ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from autodine_core.infrastructure.database import Base


class InventoryPolicy(str, Enum):
    TRACKED = "TRACKED"
    UNLIMITED = "UNLIMITED"


class Ingredient(Base):
    __tablename__ = "ingredients"

    ingredient_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    unit: Mapped[str] = mapped_column(String(16), nullable=False)
    inventory_policy: Mapped[InventoryPolicy] = mapped_column(
        SqlEnum(InventoryPolicy, native_enum=False, validate_strings=True),
        nullable=False,
    )

    inventory_records: Mapped[List["Inventory"]] = relationship(back_populates="ingredient")

    @validates("inventory_policy")
    def _validate_inventory_policy(self, _: str, value: InventoryPolicy | str) -> InventoryPolicy:
        return InventoryPolicy(value)


class Inventory(Base):
    __tablename__ = "inventories"

    store_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    ingredient_id: Mapped[str] = mapped_column(ForeignKey("ingredients.ingredient_id"), primary_key=True)
    location_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    physical_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False)
    defective_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False, default=Decimal("0"))
    reserved_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False, default=Decimal("0"))
    reorder_threshold: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False, default=Decimal("0"))

    ingredient: Mapped[Ingredient] = relationship(back_populates="inventory_records")

    @property
    def available_quantity(self) -> Decimal:
        from autodine_core.modules.inventory.service import calculate_available_quantity

        if self.ingredient.inventory_policy is InventoryPolicy.UNLIMITED:
            return Decimal("0")

        return calculate_available_quantity(
            self.physical_quantity,
            self.defective_quantity,
            self.reserved_quantity,
        )
