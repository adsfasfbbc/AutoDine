from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from autodine_core.dependencies import get_db_session
from autodine_core.infrastructure.event_bus import dispatch_app_outbox
from autodine_core.modules import response_envelope
from autodine_core.modules.order.schemas import CompleteTaskRequest
from autodine_core.modules.order.service import OrderProcessingError
from autodine_core.modules.production.service import complete_task, ready_task, start_task


router = APIRouter(prefix="/api/v1/production/tasks", tags=["production"])


def _error_response(exc: OrderProcessingError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.http_status,
        content=jsonable_encoder(response_envelope({}, code=exc.code, message=exc.message)),
    )


@router.post("/{task_id}/start")
def post_start(task_id: str, app_request: Request, session: Session = Depends(get_db_session)) -> Dict[str, Any]:
    try:
        result = start_task(session, task_id)
        dispatch_app_outbox(session, app_request.app)
        return response_envelope(result)
    except OrderProcessingError as exc:
        session.rollback()
        return _error_response(exc)


@router.post("/{task_id}/ready")
def post_ready(task_id: str, app_request: Request, session: Session = Depends(get_db_session)) -> Dict[str, Any]:
    try:
        result = ready_task(session, task_id)
        dispatch_app_outbox(session, app_request.app)
        return response_envelope(result)
    except OrderProcessingError as exc:
        session.rollback()
        return _error_response(exc)


@router.post("/{task_id}/complete")
def post_complete(
    task_id: str,
    request: CompleteTaskRequest,
    app_request: Request,
    session: Session = Depends(get_db_session),
) -> Dict[str, Any]:
    try:
        result = complete_task(session, task_id, request.actual_consumption)
        dispatch_app_outbox(session, app_request.app)
        return response_envelope(result)
    except OrderProcessingError as exc:
        session.rollback()
        return _error_response(exc)
