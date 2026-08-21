from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from autodine_core.dependencies import get_db_session
from autodine_core.infrastructure.event_bus import dispatch_app_outbox
from autodine_core.modules import response_envelope
from autodine_core.modules.alarm.models import AlarmStatus
from autodine_core.modules.alarm.schemas import AlarmOpenRequest
from autodine_core.modules.alarm.service import AlarmNotFoundError, list_alarms, open_alarm, transition_alarm


router = APIRouter(prefix="/api/v1/alarms", tags=["alarm"])


@router.post("")
def post_alarm(
    request: AlarmOpenRequest,
    app_request: Request,
    session: Session = Depends(get_db_session),
) -> Dict[str, Any]:
    result = open_alarm(
        session,
        store_id=request.store_id,
        source_key=request.source_key,
        severity=request.severity,
        message=request.message,
    )
    dispatch_app_outbox(session, app_request.app)
    return response_envelope(result)


@router.get("")
def get_alarms(store_id: str, session: Session = Depends(get_db_session)) -> Dict[str, Any]:
    return response_envelope({"items": list_alarms(session, store_id)})


def _transition(session: Session, app: Any, alarm_id: str, target: AlarmStatus) -> Dict[str, Any]:
    try:
        result = transition_alarm(session, alarm_id, target)
        dispatch_app_outbox(session, app)
        return response_envelope(result)
    except AlarmNotFoundError as exc:
        raise HTTPException(status_code=404, detail="alarm not found") from exc


@router.post("/{alarm_id}/acknowledge")
def acknowledge_alarm(alarm_id: str, app_request: Request, session: Session = Depends(get_db_session)) -> Dict[str, Any]:
    return _transition(session, app_request.app, alarm_id, AlarmStatus.ACKNOWLEDGED)


@router.post("/{alarm_id}/resolve")
def resolve_alarm(alarm_id: str, app_request: Request, session: Session = Depends(get_db_session)) -> Dict[str, Any]:
    return _transition(session, app_request.app, alarm_id, AlarmStatus.RESOLVED)
