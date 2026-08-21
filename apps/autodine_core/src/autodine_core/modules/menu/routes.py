from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from autodine_core.dependencies import get_db_session
from autodine_core.modules import response_envelope
from autodine_core.modules.menu.models import Product
from autodine_core.modules.menu.schemas import ProductSchema
from autodine_core.modules.menu.service import recalculate_product_availability


router = APIRouter(prefix="/api/v1/menu", tags=["menu"])


@router.get("")
def list_menu(session: Session = Depends(get_db_session)) -> Dict[str, Any]:
    product_ids = session.scalars(select(Product.product_id).order_by(Product.product_id)).all()
    products = [recalculate_product_availability(session, product_id) for product_id in product_ids]
    data = [ProductSchema.model_validate(product).model_dump(mode="json") for product in products]
    return response_envelope(data)


@router.get("/{product_id}")
def get_menu_item(product_id: str, session: Session = Depends(get_db_session)) -> Dict[str, Any]:
    try:
        product = recalculate_product_availability(session, product_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    data = ProductSchema.model_validate(product).model_dump(mode="json")
    return response_envelope(data)
