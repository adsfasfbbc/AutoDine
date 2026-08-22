from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from autodine_core.modules.alarm.models import Alarm, AlarmStatus
from autodine_core.modules.event.service import _append_outbox


class AlarmNotFoundError(Exception):
    pass


def _data(alarm: Alarm) -> Dict[str, Any]:
    return {"alarm_id": alarm.alarm_id, "store_id": alarm.store_id, "source_key": alarm.source_key, "severity": alarm.severity, "message": alarm.message, "status": alarm.status.value}


def open_alarm(session: Session, *, store_id: str, source_key: str, severity: str, message: str) -> Dict[str, Any]:
    alarm = session.query(Alarm).filter_by(store_id=store_id, source_key=source_key).one_or_none()
    if alarm is not None:
        return _data(alarm)
    alarm = Alarm(store_id=store_id, source_key=source_key, severity=severity, message=message)
    session.add(alarm)
    try:
        session.flush()
    except IntegrityError:
        # Concurrent openers can both pass the existence check before one wins
        # the uq_alarms_store_source_key insert; the loser returns the winner's
        # alarm instead of leaking a 500.
        session.rollback()
        raced = session.query(Alarm).filter_by(store_id=store_id, source_key=source_key).one_or_none()
        if raced is not None:
            return _data(raced)
        raise
    _append_outbox(session, trace_id=alarm.alarm_id, store_id=store_id, event_type="alarm.opened", severity=severity, payload=_data(alarm))
    session.commit()
    return _data(alarm)


def transition_alarm(session: Session, alarm_id: str, target: AlarmStatus) -> Dict[str, Any]:
    alarm = session.get(Alarm, alarm_id)
    if alarm is None:
        raise AlarmNotFoundError
    if alarm.status is target:
        return _data(alarm)
    if alarm.status is AlarmStatus.RESOLVED:
        return _data(alarm)
    alarm.status = target
    now = datetime.now(timezone.utc)
    event_type = "alarm.acknowledged" if target is AlarmStatus.ACKNOWLEDGED else "alarm.resolved"
    if target is AlarmStatus.ACKNOWLEDGED:
        alarm.acknowledged_at = now
    else:
        alarm.resolved_at = now
    _append_outbox(session, trace_id=alarm.alarm_id, store_id=alarm.store_id, event_type=event_type, severity=alarm.severity, payload=_data(alarm))
    session.commit()
    return _data(alarm)


def list_alarms(session: Session, store_id: str) -> List[Dict[str, Any]]:
    alarms = session.scalars(select(Alarm).where(Alarm.store_id == store_id).order_by(Alarm.opened_at.desc())).all()
    return [_data(alarm) for alarm in alarms]
