from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from autodine_core.dependencies import get_db_session
from autodine_core.infrastructure.event_bus import dispatch_app_outbox
from autodine_core.modules import response_envelope
from autodine_core.modules.order.schemas import OrderCreate
from autodine_core.modules.order.service import OrderProcessingError, cancel_order, create_order, _order_data


router = APIRouter(prefix="/api/v1/orders", tags=["orders"])


def _error_response(exc: OrderProcessingError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.http_status,
        content=jsonable_encoder(response_envelope({}, code=exc.code, message=exc.message)),
    )


@router.post("")
def post_order(
    request: OrderCreate,
    app_request: Request,
    session: Session = Depends(get_db_session),
) -> Dict[str, Any]:
    try:
        result = create_order(session, request)
        dispatch_app_outbox(session, app_request.app)
        return response_envelope(result)
    except OrderProcessingError as exc:
        session.rollback()
        return _error_response(exc)


@router.get("/{order_id}")
def get_order(order_id: str, session: Session = Depends(get_db_session)) -> Dict[str, Any]:
    try:
        return response_envelope(_order_data(session, order_id))
    except OrderProcessingError as exc:
        return _error_response(exc)


@router.post("/{order_id}/cancel")
def post_cancel_order(
    order_id: str,
    app_request: Request,
    session: Session = Depends(get_db_session),
) -> Dict[str, Any]:
    try:
        result = cancel_order(session, order_id)
        dispatch_app_outbox(session, app_request.app)
        return response_envelope(result)
    except OrderProcessingError as exc:
        session.rollback()
        return _error_response(exc)
