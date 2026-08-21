from __future__ import annotations

from datetime import datetime
from typing import Any, Dict

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from autodine_core.dependencies import get_db_session
from autodine_core.modules import response_envelope
from autodine_core.modules.analytics.service import summary


router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])


@router.get("/summary")
def get_summary(store_id: str, start: datetime = Query(), end: datetime = Query(), session: Session = Depends(get_db_session)) -> Dict[str, Any]:
    return response_envelope(summary(session, store_id=store_id, start=start, end=end))
