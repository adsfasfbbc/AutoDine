from __future__ import annotations

from decimal import Decimal
from enum import Enum
from typing import Optional

from sqlalchemy import Enum as SqlEnum
from sqlalchemy import Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from autodine_core.infrastructure.database import Base


class ProductStatus(str, Enum):
    ON_SALE = "ON_SALE"
    SOLD_OUT = "SOLD_OUT"


class Product(Base):
    __tablename__ = "products"

    product_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    status: Mapped[ProductStatus] = mapped_column(
        SqlEnum(ProductStatus, native_enum=False, validate_strings=True),
        nullable=False,
        default=ProductStatus.SOLD_OUT,
    )
    available_product_quantity: Mapped[int] = mapped_column(nullable=False, default=0)

    recipe: Mapped[Optional["Recipe"]] = relationship(
        "Recipe",
        back_populates="product",
        uselist=False,
        cascade="all, delete-orphan",
    )

    @validates("status")
    def _validate_status(self, _: str, value: ProductStatus | str) -> ProductStatus:
        return ProductStatus(value)
