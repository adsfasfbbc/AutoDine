from __future__ import annotations

from typing import Any, Dict

from fastapi.encoders import jsonable_encoder
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session

from autodine_core.dependencies import get_db_session
from autodine_core.infrastructure.event_bus import dispatch_app_outbox
from autodine_core.modules import response_envelope
from autodine_core.modules.event.schemas import AdpEventEnvelopeSchema
from autodine_core.modules.event.service import EventProcessingError, process_event


router = APIRouter(prefix="/api/v1/events", tags=["events"])


@router.post("")
def ingest_event(
    request: Request,
    payload: Dict[str, Any],
    session: Session = Depends(get_db_session),
) -> Dict[str, Any]:
    try:
        envelope = AdpEventEnvelopeSchema.model_validate(payload)
    except ValidationError as exc:
        return JSONResponse(
            status_code=422,
            content=jsonable_encoder(
                response_envelope(
                    {
                        "errors": exc.errors(),
                    },
                    code="INVALID_EVENT_ENVELOPE",
                    message="invalid event envelope",
                )
            ),
        )

    try:
        result = process_event(session, envelope)
    except EventProcessingError as exc:
        session.rollback()
        return JSONResponse(
            status_code=exc.http_status,
            content=jsonable_encoder(
                response_envelope(
                    {
                        "event_id": envelope.event_id,
                    },
                    code=exc.code,
                    message=exc.message,
                )
            ),
        )

    dispatch_app_outbox(session, request.app)
    return response_envelope(result)
