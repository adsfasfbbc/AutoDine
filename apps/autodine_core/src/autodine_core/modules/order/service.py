from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple
from uuid import uuid4

from fastapi.encoders import jsonable_encoder
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from autodine_core.modules.event.models import EventOutbox, PublishStatus
from autodine_core.modules.inventory.models import Ingredient, Inventory, InventoryPolicy
from autodine_core.modules.inventory.reservations import (
    InventoryMovement,
    InventoryReservation,
    MovementType,
    ReservationStatus,
)
from autodine_core.modules.inventory.service import calculate_available_quantity
from autodine_core.modules.menu.models import Product, ProductStatus
from autodine_core.modules.menu.service import recalculate_product_availability
from autodine_core.modules.order.models import Order, OrderItem, OrderStatus, OrderStatusHistory
from autodine_core.modules.order.schemas import OrderCreate
from autodine_core.modules.production.models import ProductionTask, ProductionTaskStatus
from autodine_core.modules.recipe.models import Recipe, RecipeItem


class OrderProcessingError(Exception):
    def __init__(self, *, code: Any, message: str, http_status: int = 409) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status


def _append_outbox(
    session: Session,
    *,
    trace_id: str,
    store_id: str,
    event_type: str,
    payload: Mapping[str, Any],
    severity: str = "info",
) -> None:
    session.add(
        EventOutbox(
            outbox_id=uuid4().hex,
            trace_id=trace_id,
            store_id=store_id,
            event_type=event_type,
            severity=severity,
            payload=jsonable_encoder(dict(payload)),
            publish_status=PublishStatus.PENDING,
        )
    )


def _canonical_request(request: OrderCreate) -> str:
    return json.dumps(
        {
            "customer_id": request.customer_id,
            "items": [
                {"product_id": item.product_id, "quantity": item.quantity}
                for item in sorted(request.items, key=lambda entry: entry.product_id)
            ],
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def _canonical_order(order: Order) -> str:
    return json.dumps(
        {
            "customer_id": order.customer_id,
            "items": [
                {"product_id": item.product_id, "quantity": item.quantity}
                for item in sorted(order.items, key=lambda entry: entry.product_id)
            ],
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def _load_order(session: Session, order_id: str) -> Order:
    order = session.scalar(
        select(Order)
        .where(Order.order_id == order_id)
        .options(selectinload(Order.items), selectinload(Order.status_history))
    )
    if order is None:
        raise OrderProcessingError(code="ORDER_NOT_FOUND", message="order not found", http_status=404)
    return order


def _load_task(session: Session, order_id: str) -> ProductionTask | None:
    return session.scalar(select(ProductionTask).where(ProductionTask.order_id == order_id))


def _record_status(session: Session, order: Order, status: OrderStatus) -> None:
    if order.status is status:
        return
    order.status = status
    order.status_history.append(OrderStatusHistory(status=status))


def _product_with_recipe(session: Session, product_id: str) -> Product | None:
    return session.scalar(
        select(Product)
        .where(Product.product_id == product_id)
        .options(selectinload(Product.recipe).selectinload(Recipe.items))
    )


def _allocation_plan(
    session: Session,
    *,
    store_id: str,
    ingredient_id: str,
    required: Decimal,
) -> List[Tuple[Inventory, Decimal]]:
    if required <= 0:
        return []
    rows = session.scalars(
        select(Inventory)
        .where(Inventory.store_id == store_id, Inventory.ingredient_id == ingredient_id)
        .order_by(Inventory.location_id)
        .with_for_update()
    ).all()
    remaining = required
    allocations: List[Tuple[Inventory, Decimal]] = []
    for inventory in rows:
        available = calculate_available_quantity(
            inventory.physical_quantity,
            inventory.defective_quantity,
            inventory.reserved_quantity,
        )
        if available <= 0:
            continue
        quantity = min(available, remaining)
        allocations.append((inventory, quantity))
        remaining -= quantity
        if remaining <= 0:
            break
    if remaining > 0:
        raise OrderProcessingError(code=4091, message="insufficient inventory")
    return allocations


def _order_data(session: Session, order_id: str, *, idempotency_status: str | None = None) -> Dict[str, Any]:
    order = _load_order(session, order_id)
    task = _load_task(session, order_id)
    data: Dict[str, Any] = {
        "order_id": order.order_id,
        "store_id": order.store_id,
        "customer_id": order.customer_id,
        "status": order.status.value,
        "total_amount": str(order.total_amount),
        "idempotency_key": order.idempotency_key,
        "items": [
            {
                "product_id": item.product_id,
                "quantity": item.quantity,
                "unit_price": str(item.unit_price),
            }
            for item in order.items
        ],
        "status_history": [
            {"status": history.status.value, "timestamp": history.created_at.isoformat()}
            for history in order.status_history
        ],
    }
    if idempotency_status:
        data["idempotency_status"] = idempotency_status
    if task is not None:
        data["task"] = {
            "task_id": task.task_id,
            "order_id": task.order_id,
            "status": task.status.value,
            "pick_list": task.pick_list,
        }
    return data


def create_order(session: Session, request: OrderCreate) -> Dict[str, Any]:
    existing = session.scalar(
        select(Order)
        .where(Order.store_id == request.store_id, Order.idempotency_key == request.idempotency_key)
        .options(selectinload(Order.items))
    )
    if existing is not None:
        if _canonical_order(existing) != _canonical_request(request):
            raise OrderProcessingError(code="IDEMPOTENCY_CONFLICT", message="idempotency key payload conflict")
        return _order_data(session, existing.order_id, idempotency_status="replayed")

    try:
        product_rows: List[Tuple[Any, Product, int]] = []
        required_by_ingredient: Dict[str, Decimal] = {}
        ingredient_policies: Dict[str, InventoryPolicy] = {}
        pick_list: Dict[Tuple[str, str], Dict[str, Any]] = {}
        total_amount = Decimal("0")

        for item in request.items:
            product = _product_with_recipe(session, item.product_id)
            if product is None or product.recipe is None:
                raise OrderProcessingError(code=4092, message="product unavailable")
            # Re-read current stock before reserving. This intentionally avoids relying on a stale menu projection.
            recalculate_product_availability(session, product.product_id, request.store_id, commit=False)
            if product.status is ProductStatus.SOLD_OUT:
                raise OrderProcessingError(code=4092, message="product unavailable")
            if product.available_product_quantity < item.quantity:
                raise OrderProcessingError(code=4091, message="insufficient inventory")

            product_rows.append((item, product, item.quantity))
            total_amount += product.price * item.quantity
            for recipe_item in product.recipe.items:
                ingredient = session.get(Ingredient, recipe_item.ingredient_id)
                if ingredient is None:
                    raise OrderProcessingError(code=4092, message="product unavailable")
                ingredient_policies[ingredient.ingredient_id] = InventoryPolicy(ingredient.inventory_policy)
                if ingredient.inventory_policy is InventoryPolicy.UNLIMITED:
                    continue
                required = Decimal(recipe_item.quantity) * item.quantity
                required_by_ingredient[ingredient.ingredient_id] = (
                    required_by_ingredient.get(ingredient.ingredient_id, Decimal("0")) + required
                )
                # The pick list is filled after allocation so it records concrete locations.
                pick_list.setdefault(
                    (ingredient.ingredient_id, recipe_item.unit),
                    {"ingredient_id": ingredient.ingredient_id, "quantity": Decimal("0"), "unit": recipe_item.unit},
                )["quantity"] += required

        allocations: List[Tuple[Inventory, Decimal]] = []
        for ingredient_id, required in required_by_ingredient.items():
            allocations.extend(
                (inventory, quantity)
                for inventory, quantity in _allocation_plan(
                    session,
                    store_id=request.store_id,
                    ingredient_id=ingredient_id,
                    required=required,
                )
            )

        order = Order(
            order_id=uuid4().hex,
            store_id=request.store_id,
            customer_id=request.customer_id,
            idempotency_key=request.idempotency_key,
            status=OrderStatus.PENDING,
            total_amount=total_amount,
        )
        order.status_history.append(OrderStatusHistory(status=OrderStatus.PENDING))
        for line_no, (item, product, _) in enumerate(product_rows, start=1):
            order.items.append(
                OrderItem(
                    line_no=line_no,
                    product_id=product.product_id,
                    quantity=item.quantity,
                    unit_price=product.price,
                )
            )
        session.add(order)
        session.flush()

        movement_base = datetime.now(timezone.utc)
        for allocation_index, (inventory, quantity) in enumerate(allocations):
            inventory.reserved_quantity += quantity
            reservation = InventoryReservation(
                order_id=order.order_id,
                store_id=request.store_id,
                ingredient_id=inventory.ingredient_id,
                location_id=inventory.location_id,
                quantity=quantity,
                status=ReservationStatus.ACTIVE,
            )
            session.add(reservation)
            session.flush()
            session.add(
                InventoryMovement(
                    order_id=order.order_id,
                    reservation_id=reservation.reservation_id,
                    store_id=request.store_id,
                    ingredient_id=inventory.ingredient_id,
                    location_id=inventory.location_id,
                    quantity=quantity,
                    movement_type=MovementType.RESERVE,
                    created_at=movement_base + timedelta(microseconds=allocation_index),
                )
            )

        order.status = OrderStatus.CONFIRMED
        order.status_history.append(OrderStatusHistory(status=OrderStatus.CONFIRMED))
        task = ProductionTask(
            task_id=uuid4().hex,
            order_id=order.order_id,
            store_id=request.store_id,
            status=ProductionTaskStatus.PENDING,
            pick_list=[
                {
                    "ingredient_id": key[0],
                    "quantity": format(value["quantity"].normalize(), "f").rstrip("0").rstrip(".")
                    if "." in format(value["quantity"].normalize(), "f")
                    else format(value["quantity"].normalize(), "f"),
                    "unit": value["unit"],
                }
                for key, value in sorted(pick_list.items())
            ],
        )
        session.add(task)
        trace_id = order.order_id
        _append_outbox(
            session,
            trace_id=trace_id,
            store_id=request.store_id,
            event_type="order.created",
            payload={"order_id": order.order_id, "status": order.status.value},
        )
        _append_outbox(
            session,
            trace_id=trace_id,
            store_id=request.store_id,
            event_type="inventory.reserved",
            payload={
                "order_id": order.order_id,
                "reservations": [
                    {
                        "ingredient_id": inventory.ingredient_id,
                        "location_id": inventory.location_id,
                        "quantity": str(quantity),
                    }
                    for inventory, quantity in allocations
                ],
            },
        )
        _append_outbox(
            session,
            trace_id=trace_id,
            store_id=request.store_id,
            event_type="production.task_created",
            payload={"task_id": task.task_id, "order_id": order.order_id, "status": task.status.value},
        )
        session.commit()
        return _order_data(session, order.order_id)
    except OrderProcessingError:
        session.rollback()
        raise
    except IntegrityError:
        # The unique (store_id, idempotency_key) constraint is the final arbiter
        # when two requests race before either can see the other's order.
        session.rollback()
        raced = session.scalar(
            select(Order)
            .where(Order.store_id == request.store_id, Order.idempotency_key == request.idempotency_key)
            .options(selectinload(Order.items))
        )
        if raced is not None:
            if _canonical_order(raced) != _canonical_request(request):
                raise OrderProcessingError(code="IDEMPOTENCY_CONFLICT", message="idempotency key payload conflict")
            return _order_data(session, raced.order_id, idempotency_status="replayed")
        raise
    except Exception:
        session.rollback()
        raise


def cancel_order(session: Session, order_id: str) -> Dict[str, Any]:
    try:
        order = _load_order(session, order_id)
        if order.status is OrderStatus.CANCELED:
            return _order_data(session, order.order_id)
        if order.status in {OrderStatus.COMPLETED, OrderStatus.READY}:
            raise OrderProcessingError(code="INVALID_ORDER_TRANSITION", message="order cannot be canceled")
        reservations = session.scalars(
            select(InventoryReservation).where(
                InventoryReservation.order_id == order.order_id,
                InventoryReservation.status == ReservationStatus.ACTIVE,
            )
        ).all()
        for reservation in reservations:
            inventory = session.scalar(
                select(Inventory)
                .where(
                    Inventory.store_id == reservation.store_id,
                    Inventory.ingredient_id == reservation.ingredient_id,
                    Inventory.location_id == reservation.location_id,
                )
                .with_for_update()
            )
            if inventory is not None:
                inventory.reserved_quantity = max(
                    Decimal("0"), inventory.reserved_quantity - reservation.quantity
                )
            else:
                raise OrderProcessingError(code="INVENTORY_NOT_FOUND", message="reserved inventory not found")
            reservation.status = ReservationStatus.RELEASED
            session.add(
                InventoryMovement(
                    order_id=order.order_id,
                    reservation_id=reservation.reservation_id,
                    store_id=reservation.store_id,
                    ingredient_id=reservation.ingredient_id,
                    location_id=reservation.location_id,
                    quantity=reservation.quantity,
                    movement_type=MovementType.RELEASE,
                )
            )
        _record_status(session, order, OrderStatus.CANCELED)
        task = _load_task(session, order.order_id)
        if task is not None:
            task.status = ProductionTaskStatus.CANCELED
        if reservations:
            _append_outbox(
                session,
                trace_id=order.order_id,
                store_id=order.store_id,
                event_type="inventory.released",
                payload={"order_id": order.order_id},
            )
        session.commit()
        return _order_data(session, order.order_id)
    except OrderProcessingError:
        session.rollback()
        raise
    except Exception:
        session.rollback()
        raise


__all__ = [
    "OrderProcessingError",
    "cancel_order",
    "create_order",
    "_append_outbox",
    "_load_order",
    "_load_task",
    "_order_data",
    "_record_status",
]
