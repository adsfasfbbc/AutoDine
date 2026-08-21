from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from sqlalchemy import select
from sqlalchemy.orm import Session

from autodine_core.modules.device.models import DeviceCommand, DeviceCommandStatus
from autodine_core.modules.event.service import _append_outbox


def _data(command: DeviceCommand) -> Dict[str, Any]:
    return {"command_id": command.command_id, "store_id": command.store_id, "device_id": command.device_id, "command_type": command.command_type, "parameters": command.parameters, "status": command.status.value, "result": command.result}


def create_command(session: Session, *, store_id: str, device_id: str, command_type: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
    command = DeviceCommand(store_id=store_id, device_id=device_id, command_type=command_type, parameters=parameters)
    session.add(command)
    session.flush()
    _append_outbox(session, trace_id=command.command_id, store_id=store_id, event_type="device.command", severity="info", payload={"command_id": command.command_id, "device_id": device_id, "command_type": command_type, "parameters": parameters, "status": DeviceCommandStatus.PENDING.value})
    session.commit()
    return _data(command)


def list_commands(session: Session, *, store_id: str, device_id: str) -> List[Dict[str, Any]]:
    commands = session.scalars(
        select(DeviceCommand)
        .where(DeviceCommand.store_id == store_id, DeviceCommand.device_id == device_id)
        .order_by(DeviceCommand.created_at.desc())
    ).all()
    return [_data(command) for command in commands]


def apply_command_result(session: Session, *, store_id: str, trace_id: str, payload: Dict[str, Any]) -> None:
    command = session.get(DeviceCommand, payload["command_id"])
    if command is None or command.store_id != store_id:
        return
    status = DeviceCommandStatus(payload["status"])
    command.status = status
    command.result = payload.get("result", {})
    command.completed_at = datetime.now(timezone.utc)
    _append_outbox(session, trace_id=trace_id, store_id=store_id, event_type="device.command_result", severity="info" if status is DeviceCommandStatus.SUCCEEDED else "error", payload={"command_id": command.command_id, "device_id": command.device_id, "status": status.value, "result": command.result})
