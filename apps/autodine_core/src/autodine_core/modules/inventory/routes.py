from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from autodine_core.dependencies import get_db_session
from autodine_core.modules import response_envelope
from autodine_core.modules.inventory.models import Inventory
from autodine_core.modules.inventory.schemas import InventorySchema


router = APIRouter(prefix="/api/v1/inventory", tags=["inventory"])


@router.get("")
def list_inventory(session: Session = Depends(get_db_session)) -> Dict[str, Any]:
    inventories = session.scalars(
        select(Inventory)
        .options(selectinload(Inventory.ingredient))
        .order_by(Inventory.ingredient_id, Inventory.location_id)
    ).all()
    data = [InventorySchema.model_validate(inventory).model_dump(mode="json") for inventory in inventories]
    return response_envelope(data)
