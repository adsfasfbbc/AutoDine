from __future__ import annotations

from decimal import Decimal
from typing import List

from pydantic import BaseModel, ConfigDict, field_validator

from autodine_core.modules.recipe.models import STANDARD_UNITS


class RecipeItemSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ingredient_id: str
    quantity: Decimal
    unit: str

    @field_validator("quantity")
    @classmethod
    def validate_quantity(cls, value: Decimal) -> Decimal:
        if value < 0:
            raise ValueError("recipe quantity must be non-negative")
        return value

    @field_validator("unit")
    @classmethod
    def validate_unit(cls, value: str) -> str:
        if value not in STANDARD_UNITS:
            raise ValueError("unsupported recipe unit")
        return value


class RecipeSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    recipe_id: str
    product_id: str
    items: List[RecipeItemSchema]
