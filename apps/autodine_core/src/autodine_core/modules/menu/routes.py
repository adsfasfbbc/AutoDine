from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from autodine_core.dependencies import get_db_session
from autodine_core.modules import response_envelope
from autodine_core.modules.menu.models import Product
from autodine_core.modules.menu.schemas import ProductSchema
from autodine_core.modules.menu.service import get_store_product_projection
from autodine_core.modules.recipe.models import Recipe


router = APIRouter(prefix="/api/v1/menu", tags=["menu"])


def _products_with_recipe():
    return select(Product).options(selectinload(Product.recipe).selectinload(Recipe.items))


@router.get("")
def list_menu(store_id: str, session: Session = Depends(get_db_session)) -> Dict[str, Any]:
    products = session.scalars(_products_with_recipe().order_by(Product.product_id)).all()
    data = [
        ProductSchema.model_validate(get_store_product_projection(session, product, store_id)).model_dump(mode="json")
        for product in products
        if product.recipe is not None
    ]
    return response_envelope(data)


@router.get("/{product_id}")
def get_menu_item(product_id: str, store_id: str, session: Session = Depends(get_db_session)) -> Dict[str, Any]:
    product = session.scalar(_products_with_recipe().where(Product.product_id == product_id))
    if product is None or product.recipe is None:
        raise HTTPException(status_code=404, detail=f"product '{product_id}' does not exist")

    data = ProductSchema.model_validate(get_store_product_projection(session, product, store_id)).model_dump(mode="json")
    return response_envelope(data)
