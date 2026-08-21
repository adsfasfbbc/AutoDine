from __future__ import annotations

from decimal import Decimal
from typing import List

from sqlalchemy import ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from autodine_core.infrastructure.database import Base


STANDARD_UNITS = {"pcs", "g", "ml"}


class Recipe(Base):
    __tablename__ = "recipes"

    recipe_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.product_id"), nullable=False, unique=True)

    product: Mapped["Product"] = relationship("Product", back_populates="recipe")
    items: Mapped[List["RecipeItem"]] = relationship(
        back_populates="recipe",
        cascade="all, delete-orphan",
    )


class RecipeItem(Base):
    __tablename__ = "recipe_items"

    recipe_id: Mapped[str] = mapped_column(ForeignKey("recipes.recipe_id"), primary_key=True)
    ingredient_id: Mapped[str] = mapped_column(ForeignKey("ingredients.ingredient_id"), primary_key=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False)
    unit: Mapped[str] = mapped_column(String(16), nullable=False)

    recipe: Mapped[Recipe] = relationship(back_populates="items")

    @validates("quantity")
    def _validate_quantity(self, _: str, value: Decimal) -> Decimal:
        if value < 0:
            raise ValueError("recipe quantity must be non-negative")
        return value

    @validates("unit")
    def _validate_unit(self, _: str, value: str) -> str:
        if value not in STANDARD_UNITS:
            raise ValueError("unsupported recipe unit")
        return value
