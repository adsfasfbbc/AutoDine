from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from autodine_core.modules.device.models import Device, DeviceCommand, DeviceCommandStatus
from autodine_core.modules.event.service import _append_outbox

logger = logging.getLogger("autodine_core.device")

# Device types powered off on a confirmed fire when no override is configured.
DEFAULT_FIRE_SHUTDOWN_DEVICE_TYPES = ("fan", "air_conditioner")


def _device_data(device: Device) -> Dict[str, Any]:
    return {"device_id": device.device_id, "store_id": device.store_id, "device_type": device.device_type}


def register_device(session: Session, *, store_id: str, device_id: str, device_type: str) -> Dict[str, Any]:
    """Idempotent device registration: re-registering returns the existing row."""
    device = session.get(Device, device_id)
    if device is not None:
        return _device_data(device)
    device = Device(store_id=store_id, device_id=device_id, device_type=device_type)
    session.add(device)
    session.commit()
    return _device_data(device)


def create_fire_shutdown_commands(
    session: Session,
    *,
    store_id: str,
    device_types: Optional[Sequence[str]] = None,
    source_event_id: str,
) -> List[Dict[str, Any]]:
    """Power off every registered store device whose type is on the shutdown list.

    A store without matching devices is not an error — it only gets a log line.
    """
    types = tuple(device_types) if device_types is not None else DEFAULT_FIRE_SHUTDOWN_DEVICE_TYPES
    devices = session.scalars(
        select(Device).where(Device.store_id == store_id, Device.device_type.in_(types))
    ).all()
    if not devices:
        logger.info(
            "store %s has no registered devices of types %s; skipping fire shutdown",
            store_id, list(types),
        )
        return []
    commands = []
    for device in devices:
        commands.append(
            create_command(
                session,
                store_id=store_id,
                device_id=device.device_id,
                command_type="power_off",
                parameters={"reason": "fire_alarm", "source_event_id": source_event_id},
            )
        )
    return commands


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
