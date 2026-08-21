from __future__ import annotations

from collections.abc import Iterable, Mapping
from decimal import Decimal
from typing import Any, Dict, Iterable as TypingIterable, List, Union

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from autodine_core.modules.inventory.models import Ingredient, Inventory, InventoryPolicy
from autodine_core.modules.inventory.service import calculate_available_quantity
from autodine_core.modules.menu.models import Product, ProductStatus
from autodine_core.modules.recipe.models import Recipe, RecipeItem


def _item_value(item: object, field_name: str) -> object:
    if isinstance(item, Mapping):
        return item[field_name]
    return getattr(item, field_name)


def calculate_product_quantity(
    recipe_items: Iterable[object],
    inventory_by_ingredient: Mapping[str, Decimal],
    ingredient_policies: Mapping[str, Union[str, InventoryPolicy]],
) -> int:
    candidate_quantities: List[int] = []

    for recipe_item in recipe_items:
        ingredient_id = str(_item_value(recipe_item, "ingredient_id"))
        required_quantity = Decimal(_item_value(recipe_item, "quantity"))
        policy = InventoryPolicy(ingredient_policies[ingredient_id])

        if policy is InventoryPolicy.UNLIMITED:
            continue

        available_quantity = inventory_by_ingredient.get(ingredient_id)
        if available_quantity is None or required_quantity <= 0:
            return 0

        candidate_quantities.append(int(available_quantity // required_quantity))

    if not candidate_quantities:
        return 0

    minimum_quantity = min(candidate_quantities)
    if minimum_quantity < 0:
        return 0
    return minimum_quantity


def recalculate_product_availability(session: Session, product_id: str, commit: bool = True) -> Product:
    product = session.scalar(
        select(Product)
        .where(Product.product_id == product_id)
        .options(selectinload(Product.recipe).selectinload(Recipe.items))
    )
    if product is None or product.recipe is None:
        raise ValueError(f"product '{product_id}' does not exist")

    ingredient_ids = [item.ingredient_id for item in product.recipe.items]
    ingredients = session.scalars(
        select(Ingredient).where(Ingredient.ingredient_id.in_(ingredient_ids))
    ).all()
    inventories = session.scalars(
        select(Inventory)
        .where(Inventory.ingredient_id.in_(ingredient_ids))
        .options(selectinload(Inventory.ingredient))
    ).all()

    ingredient_policies = {ingredient.ingredient_id: ingredient.inventory_policy for ingredient in ingredients}
    inventory_by_ingredient: Dict[str, Decimal] = {}
    for inventory in inventories:
        available_quantity = calculate_available_quantity(
            inventory.physical_quantity,
            inventory.defective_quantity,
            inventory.reserved_quantity,
        )
        inventory_by_ingredient.setdefault(inventory.ingredient_id, Decimal("0"))
        inventory_by_ingredient[inventory.ingredient_id] += available_quantity

    available_product_quantity = calculate_product_quantity(
        recipe_items=product.recipe.items,
        inventory_by_ingredient=inventory_by_ingredient,
        ingredient_policies=ingredient_policies,
    )
    product.available_product_quantity = available_product_quantity
    product.status = ProductStatus.ON_SALE if available_product_quantity > 0 else ProductStatus.SOLD_OUT
    session.add(product)
    if commit:
        session.commit()
        session.refresh(product)
    return product


def recalculate_products_for_ingredients(
    session: Session,
    ingredient_ids: TypingIterable[str],
) -> List[Dict[str, Any]]:
    session.flush()
    product_ids = session.scalars(
        select(Recipe.product_id)
        .join(RecipeItem, RecipeItem.recipe_id == Recipe.recipe_id)
        .where(RecipeItem.ingredient_id.in_(list(ingredient_ids)))
        .distinct()
        .order_by(Recipe.product_id)
    ).all()

    changes: List[Dict[str, Any]] = []
    for product_id in product_ids:
        product = session.get(Product, product_id)
        previous_status = product.status.value
        previous_quantity = product.available_product_quantity
        product = recalculate_product_availability(session, product_id, commit=False)
        changes.append(
            {
                "product_id": product.product_id,
                "previous_status": previous_status,
                "current_status": product.status.value,
                "previous_available_product_quantity": previous_quantity,
                "current_available_product_quantity": product.available_product_quantity,
                "changed": previous_status != product.status.value
                or previous_quantity != product.available_product_quantity,
            }
        )

    return changes
