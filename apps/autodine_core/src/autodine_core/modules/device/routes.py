from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from autodine_core.dependencies import get_db_session
from autodine_core.modules import response_envelope
from autodine_core.modules.device.schemas import DeviceCommandCreate
from autodine_core.modules.device.service import create_command, list_commands


router = APIRouter(prefix="/api/v1/devices", tags=["device"])


@router.post("/{device_id}/commands")
def post_command(device_id: str, request: DeviceCommandCreate, session: Session = Depends(get_db_session)) -> Dict[str, Any]:
    return response_envelope(create_command(session, store_id=request.store_id, device_id=device_id, command_type=request.command_type, parameters=request.parameters))


@router.get("/{device_id}/commands")
def get_commands(device_id: str, store_id: str, session: Session = Depends(get_db_session)) -> Dict[str, Any]:
    return response_envelope({"items": list_commands(session, store_id=store_id, device_id=device_id)})
