from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
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


def _resolve_store_id(request: Request, store_id: Optional[str]) -> str:
    # Single-store operation: an omitted store_id falls back to the configured
    # default store; the parameter stays in the contract as the multi-store
    # reservation.
    return store_id or request.app.state.settings.default_store_id


@router.get("")
def list_menu(
    request: Request,
    store_id: Optional[str] = None,
    session: Session = Depends(get_db_session),
) -> Dict[str, Any]:
    resolved_store_id = _resolve_store_id(request, store_id)
    products = session.scalars(_products_with_recipe().order_by(Product.product_id)).all()
    data = [
        ProductSchema.model_validate(get_store_product_projection(session, product, resolved_store_id)).model_dump(mode="json")
        for product in products
        if product.recipe is not None
    ]
    return response_envelope(data)


@router.get("/{product_id}")
def get_menu_item(
    product_id: str,
    request: Request,
    store_id: Optional[str] = None,
    session: Session = Depends(get_db_session),
) -> Dict[str, Any]:
    product = session.scalar(_products_with_recipe().where(Product.product_id == product_id))
    if product is None or product.recipe is None:
        raise HTTPException(status_code=404, detail=f"product '{product_id}' does not exist")

    resolved_store_id = _resolve_store_id(request, store_id)
    data = ProductSchema.model_validate(get_store_product_projection(session, product, resolved_store_id)).model_dump(mode="json")
    return response_envelope(data)
