from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from autodine_core.dependencies import get_db_session
from autodine_core.modules import response_envelope
from autodine_core.modules.queue.service import list_queue_snapshots


router = APIRouter(prefix="/api/v1/queues", tags=["queue"])


@router.get("/{store_id}")
def get_queue(store_id: str, session: Session = Depends(get_db_session)) -> Dict[str, Any]:
    return response_envelope({"items": list_queue_snapshots(session, store_id)})
