from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, Iterable, Mapping

from sqlalchemy import select
from sqlalchemy.orm import Session

from autodine_core.modules.inventory.models import Inventory
from autodine_core.modules.inventory.reservations import (
    InventoryMovement,
    InventoryReservation,
    MovementType,
    ReservationStatus,
)
from autodine_core.modules.menu.service import recalculate_products_for_ingredients
from autodine_core.modules.order.models import Order, OrderStatus, OrderStatusHistory
from autodine_core.modules.order.service import (
    OrderProcessingError,
    _append_outbox,
    _load_task,
    _order_data,
    _record_status,
)
from autodine_core.modules.production.models import ProductionTask, ProductionTaskStatus


def _task_data(session: Session, task: ProductionTask) -> Dict[str, Any]:
    order = session.get(Order, task.order_id)
    return {
        "task_id": task.task_id,
        "order_id": task.order_id,
        "store_id": task.store_id,
        "status": task.status.value,
        "pick_list": task.pick_list,
        "order_status": order.status.value if order else None,
    }


def _get_task(session: Session, task_id: str) -> ProductionTask:
    task = session.get(ProductionTask, task_id)
    if task is None:
        raise OrderProcessingError(code="TASK_NOT_FOUND", message="production task not found", http_status=404)
    return task


def _get_task_for_update(session: Session, task_id: str) -> ProductionTask:
    task = session.scalar(
        select(ProductionTask).where(ProductionTask.task_id == task_id).with_for_update()
    )
    if task is None:
        raise OrderProcessingError(code="TASK_NOT_FOUND", message="production task not found", http_status=404)
    return task


def start_task(session: Session, task_id: str) -> Dict[str, Any]:
    try:
        task = _get_task_for_update(session, task_id)
        if task.status is ProductionTaskStatus.PRODUCING:
            return _task_data(session, task)
        if task.status is not ProductionTaskStatus.PENDING:
            raise OrderProcessingError(code="INVALID_TASK_TRANSITION", message="task cannot be started")
        order = session.get(Order, task.order_id)
        if order is None or order.status is not OrderStatus.CONFIRMED:
            raise OrderProcessingError(code="INVALID_ORDER_TRANSITION", message="order cannot start production")
        task.status = ProductionTaskStatus.PRODUCING
        _record_status(session, order, OrderStatus.PRODUCING)
        _append_outbox(
            session,
            trace_id=order.order_id,
            store_id=task.store_id,
            event_type="production.task_started",
            payload={"task_id": task.task_id, "order_id": order.order_id, "status": task.status.value},
        )
        session.commit()
        return _task_data(session, task)
    except OrderProcessingError:
        session.rollback()
        raise


def ready_task(session: Session, task_id: str) -> Dict[str, Any]:
    try:
        task = _get_task_for_update(session, task_id)
        if task.status is ProductionTaskStatus.READY:
            return _task_data(session, task)
        if task.status is not ProductionTaskStatus.PRODUCING:
            raise OrderProcessingError(code="INVALID_TASK_TRANSITION", message="task is not producing")
        order = session.get(Order, task.order_id)
        if order is None or order.status is not OrderStatus.PRODUCING:
            raise OrderProcessingError(code="INVALID_ORDER_TRANSITION", message="order is not producing")
        task.status = ProductionTaskStatus.READY
        _record_status(session, order, OrderStatus.READY)
        _append_outbox(
            session,
            trace_id=order.order_id,
            store_id=task.store_id,
            event_type="production.task_ready",
            payload={"task_id": task.task_id, "order_id": order.order_id, "status": task.status.value},
        )
        session.commit()
        return _task_data(session, task)
    except OrderProcessingError:
        session.rollback()
        raise


def complete_task(
    session: Session,
    task_id: str,
    actual_consumption: Iterable[Mapping[str, Any]],
) -> Dict[str, Any]:
    try:
        # Lock the task, order, and active reservations before reading state so
        # two completion calls cannot both consume the same reservation set.
        task = _get_task_for_update(session, task_id)
        if task.status is ProductionTaskStatus.COMPLETED:
            return _task_data(session, task)
        if task.status is not ProductionTaskStatus.READY:
            raise OrderProcessingError(code="INVALID_TASK_TRANSITION", message="task is not ready")
        order = session.scalar(select(Order).where(Order.order_id == task.order_id).with_for_update())
        if order is None or order.status is not OrderStatus.READY:
            raise OrderProcessingError(code="INVALID_ORDER_TRANSITION", message="order is not ready")

        consumption: Dict[tuple[str, str], Decimal] = {}
        for entry in actual_consumption:
            if isinstance(entry, Mapping):
                ingredient_id = entry["ingredient_id"]
                location_id = entry["location_id"]
                quantity = entry["quantity"]
            else:
                ingredient_id = entry.ingredient_id
                location_id = entry.location_id
                quantity = entry.quantity
            key = (str(ingredient_id), str(location_id))
            consumption[key] = consumption.get(key, Decimal("0")) + Decimal(quantity)

        reservations = session.scalars(
            select(InventoryReservation).where(
                InventoryReservation.order_id == order.order_id,
                InventoryReservation.status == ReservationStatus.ACTIVE,
            )
            .with_for_update()
        ).all()
        reservation_keys = {(reservation.ingredient_id, reservation.location_id) for reservation in reservations}
        if set(consumption) != reservation_keys:
            raise OrderProcessingError(
                code="INVALID_CONSUMPTION",
                message="actual consumption must cover every tracked reservation exactly once",
            )
        affected_ingredients = set()
        release_records = []
        movement_base = datetime.now(timezone.utc)
        consume_index = 0
        for reservation in reservations:
            key = (reservation.ingredient_id, reservation.location_id)
            actual = consumption.pop(key, Decimal("0"))
            if actual > reservation.quantity:
                raise OrderProcessingError(code="INVALID_CONSUMPTION", message="actual consumption exceeds reservation")
            inventory = session.scalar(
                select(Inventory)
                .where(
                    Inventory.store_id == reservation.store_id,
                    Inventory.ingredient_id == reservation.ingredient_id,
                    Inventory.location_id == reservation.location_id,
                )
                .with_for_update()
            )
            if inventory is None:
                raise OrderProcessingError(code="INVENTORY_NOT_FOUND", message="reserved inventory not found", http_status=409)
            if actual:
                if inventory.physical_quantity < actual:
                    raise OrderProcessingError(code=4091, message="insufficient inventory")
                inventory.physical_quantity -= actual
                session.add(
                    InventoryMovement(
                        order_id=order.order_id,
                        reservation_id=reservation.reservation_id,
                        store_id=reservation.store_id,
                        ingredient_id=reservation.ingredient_id,
                        location_id=reservation.location_id,
                        quantity=actual,
                        movement_type=MovementType.CONSUME,
                        created_at=movement_base + timedelta(microseconds=consume_index),
                    )
                )
                consume_index += 1
            inventory.reserved_quantity = max(
                Decimal("0"), inventory.reserved_quantity - reservation.quantity
            )
            reservation.status = ReservationStatus.RELEASED
            release_records.append(reservation)
            affected_ingredients.add(reservation.ingredient_id)

        if consumption:
            raise OrderProcessingError(code="INVALID_CONSUMPTION", message="consumption has no reservation")

        for release_index, reservation in enumerate(release_records):
            session.add(
                InventoryMovement(
                    order_id=order.order_id,
                    reservation_id=reservation.reservation_id,
                    store_id=reservation.store_id,
                    ingredient_id=reservation.ingredient_id,
                    location_id=reservation.location_id,
                    quantity=reservation.quantity,
                    movement_type=MovementType.RELEASE,
                    created_at=movement_base + timedelta(microseconds=1000 + release_index),
                )
            )

        task.status = ProductionTaskStatus.COMPLETED
        _record_status(session, order, OrderStatus.COMPLETED)
        _append_outbox(
            session,
            trace_id=order.order_id,
            store_id=task.store_id,
            event_type="inventory.released",
            payload={"order_id": order.order_id, "reason": "production_completed"},
        )
        _append_outbox(
            session,
            trace_id=order.order_id,
            store_id=task.store_id,
            event_type="production.task_completed",
            payload={"task_id": task.task_id, "order_id": order.order_id, "status": task.status.value},
        )
        changes = recalculate_products_for_ingredients(session, affected_ingredients, store_id=task.store_id)
        for change in changes:
            if change["changed"]:
                _append_outbox(
                    session,
                    trace_id=order.order_id,
                    store_id=task.store_id,
                    event_type="menu.availability_changed",
                    payload=change,
                )
        session.commit()
        return _task_data(session, task)
    except OrderProcessingError:
        session.rollback()
        raise


__all__ = ["complete_task", "ready_task", "start_task"]
