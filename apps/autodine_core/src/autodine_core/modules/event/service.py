from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, Iterable, List, Optional
from uuid import uuid4

from fastapi.encoders import jsonable_encoder
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from autodine_core.modules.event.models import EventInbox, EventInboxStatus, EventOutbox, PublishStatus
from autodine_core.modules.event.schemas import AdpEventEnvelopeSchema
from autodine_core.modules.inventory.models import Ingredient, Inventory
from autodine_core.modules.inventory.service import calculate_available_quantity
from autodine_core.modules.menu.service import recalculate_products_for_ingredients
from autodine_core.modules.recipe.models import RecipeItem


class EventProcessingError(Exception):
    def __init__(self, *, code: str, message: str, http_status: int) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status


def _serialize_decimal(value: Decimal) -> str:
    normalized = format(value.normalize(), "f")
    if "." in normalized:
        normalized = normalized.rstrip("0").rstrip(".")
    return normalized or "0"


def _build_inbox_record(envelope: AdpEventEnvelopeSchema, *, status: EventInboxStatus) -> EventInbox:
    return EventInbox(
        event_id=envelope.event_id,
        trace_id=envelope.trace_id or envelope.event_id,
        store_id=envelope.store_id,
        event_type=envelope.event_type,
        source_module=envelope.source.module,
        source_device_id=envelope.source.device_id,
        occurred_at=envelope.timestamp,
        status=status,
        payload=jsonable_encoder(envelope.payload),
    )


def _append_outbox(
    session: Session,
    *,
    trace_id: str,
    store_id: str,
    event_type: str,
    severity: str,
    payload: Dict[str, Any],
) -> None:
    session.add(
        EventOutbox(
            outbox_id=uuid4().hex,
            trace_id=trace_id,
            store_id=store_id,
            event_type=event_type,
            severity=severity,
            payload=payload,
            publish_status=PublishStatus.PENDING,
        )
    )


def _get_ingredient_or_error(session: Session, ingredient_id: str) -> Ingredient:
    ingredient = session.get(Ingredient, ingredient_id)
    if ingredient is None:
        raise EventProcessingError(
            code="UNKNOWN_INGREDIENT",
            message="unknown ingredient",
            http_status=404,
        )
    return ingredient


def _inventory_changed_payload(inventory: Inventory) -> Dict[str, Any]:
    return {
        "ingredient_id": inventory.ingredient_id,
        "location_id": inventory.location_id,
        "physical_quantity": _serialize_decimal(inventory.physical_quantity),
        "defective_quantity": _serialize_decimal(inventory.defective_quantity),
        "reserved_quantity": _serialize_decimal(inventory.reserved_quantity),
        "available_quantity": _serialize_decimal(
            calculate_available_quantity(
                inventory.physical_quantity,
                inventory.defective_quantity,
                inventory.reserved_quantity,
            )
        ),
    }


def _upsert_inventory_snapshot(
    session: Session,
    *,
    store_id: str,
    ingredient_id: str,
    location_id: str,
    unit: str,
    physical_quantity: Any,
    defective_quantity: Any = None,
) -> Inventory:
    ingredient = _get_ingredient_or_error(session, ingredient_id)

    if ingredient.unit != unit:
        raise EventProcessingError(
            code="INVALID_EVENT_PAYLOAD",
            message="ingredient unit mismatch",
            http_status=422,
        )

    inventory = session.get(Inventory, (store_id, ingredient.ingredient_id, location_id))
    if inventory is None:
        inventory = Inventory(
            store_id=store_id,
            ingredient_id=ingredient.ingredient_id,
            location_id=location_id,
            physical_quantity=Decimal("0"),
            defective_quantity=Decimal("0"),
            reserved_quantity=Decimal("0"),
            reorder_threshold=Decimal("0"),
        )
        session.add(inventory)

    inventory.physical_quantity = Decimal(physical_quantity)
    if defective_quantity is not None:
        inventory.defective_quantity = Decimal(defective_quantity)
    # Reservations are Core-owned state. A vision snapshot may report a
    # reserved field for diagnostics, but it must never overwrite an order's
    # reservation while applying an edge observation.
    return inventory


def _emit_menu_availability_changes(
    session: Session,
    *,
    trace_id: str,
    store_id: str,
    ingredient_ids: Iterable[str],
) -> None:
    for change in recalculate_products_for_ingredients(session, ingredient_ids, store_id=store_id):
        if change["changed"]:
            _append_outbox(
                session,
                trace_id=trace_id,
                store_id=store_id,
                event_type="menu.availability_changed",
                severity="info",
                payload={
                    "product_id": change["product_id"],
                    "store_id": change["store_id"],
                    "previous_status": change["previous_status"],
                    "current_status": change["current_status"],
                    "previous_available_product_quantity": change["previous_available_product_quantity"],
                    "current_available_product_quantity": change["current_available_product_quantity"],
                },
            )


# Detections below this confidence are treated as noise and never touch inventory.
MIN_VISION_DETECTION_CONFIDENCE = 0.5


def _handle_inventory_detected(
    session: Session,
    envelope: AdpEventEnvelopeSchema,
) -> None:
    payload = envelope.payload
    inventory = _upsert_inventory_snapshot(
        session,
        store_id=envelope.store_id,
        ingredient_id=payload["ingredient_id"],
        location_id=payload["location_id"],
        unit=payload["unit"],
        physical_quantity=payload["physical_quantity"],
        defective_quantity=payload.get("defective_quantity"),
    )

    trace_id = envelope.trace_id or envelope.event_id
    _append_outbox(
        session,
        trace_id=trace_id,
        store_id=envelope.store_id,
        event_type="inventory.changed",
        severity="info",
        payload=_inventory_changed_payload(inventory),
    )
    _emit_menu_availability_changes(
        session,
        trace_id=trace_id,
        store_id=envelope.store_id,
        ingredient_ids=[inventory.ingredient_id],
    )


def _handle_vision_storage_detected(
    session: Session,
    envelope: AdpEventEnvelopeSchema,
) -> None:
    """Translate a raw smart-storage vision frame into inventory snapshots."""
    payload = envelope.payload
    trace_id = envelope.trace_id or envelope.event_id
    changed_ingredient_ids: List[str] = []

    for detection in payload["detections"]:
        if float(detection.get("confidence", 1.0)) < MIN_VISION_DETECTION_CONFIDENCE:
            continue
        inventory = _upsert_inventory_snapshot(
            session,
            store_id=envelope.store_id,
            ingredient_id=detection["ingredient_id"],
            location_id=payload["location_id"],
            unit=detection["unit"],
            physical_quantity=detection["quantity"],
        )
        changed_ingredient_ids.append(inventory.ingredient_id)
        _append_outbox(
            session,
            trace_id=trace_id,
            store_id=envelope.store_id,
            event_type="inventory.changed",
            severity="info",
            payload=_inventory_changed_payload(inventory),
        )

    if changed_ingredient_ids:
        _emit_menu_availability_changes(
            session,
            trace_id=trace_id,
            store_id=envelope.store_id,
            ingredient_ids=changed_ingredient_ids,
        )


def _handle_quality_abnormal(
    session: Session,
    envelope: AdpEventEnvelopeSchema,
) -> None:
    payload = envelope.payload
    ingredient = _get_ingredient_or_error(session, payload["ingredient_id"])
    defective_quantity = payload.get("defective_quantity", payload.get("quantity"))

    inventory = session.get(Inventory, (envelope.store_id, ingredient.ingredient_id, payload["location_id"]))
    if inventory is None:
        inventory = Inventory(
            store_id=envelope.store_id,
            ingredient_id=ingredient.ingredient_id,
            location_id=payload["location_id"],
            physical_quantity=Decimal("0"),
            defective_quantity=Decimal("0"),
            reserved_quantity=Decimal("0"),
            reorder_threshold=Decimal("0"),
        )
        session.add(inventory)

    inventory.defective_quantity = Decimal(defective_quantity)

    trace_id = envelope.trace_id or envelope.event_id
    _append_outbox(
        session,
        trace_id=trace_id,
        store_id=envelope.store_id,
        event_type="inventory.changed",
        severity="info",
        payload=_inventory_changed_payload(inventory),
    )
    _emit_menu_availability_changes(
        session,
        trace_id=trace_id,
        store_id=envelope.store_id,
        ingredient_ids=[ingredient.ingredient_id],
    )


def process_event(session: Session, envelope: AdpEventEnvelopeSchema) -> Dict[str, Any]:
    try:
        if session.get(EventInbox, envelope.event_id) is not None:
            session.rollback()
            return {
                "status": "duplicate",
                "event_id": envelope.event_id,
            }

        if envelope.event_type == "inventory.detected":
            session.add(_build_inbox_record(envelope, status=EventInboxStatus.PROCESSED))
            _handle_inventory_detected(session, envelope)
            session.commit()
            return {
                "status": "processed",
                "event_id": envelope.event_id,
            }

        if envelope.event_type == "quality.abnormal":
            session.add(_build_inbox_record(envelope, status=EventInboxStatus.PROCESSED))
            _handle_quality_abnormal(session, envelope)
            session.commit()
            return {
                "status": "processed",
                "event_id": envelope.event_id,
            }

        if envelope.event_type == "vision.storage.detected":
            session.add(_build_inbox_record(envelope, status=EventInboxStatus.PROCESSED))
            _handle_vision_storage_detected(session, envelope)
            session.commit()
            return {
                "status": "processed",
                "event_id": envelope.event_id,
            }

        if envelope.event_type == "queue.updated":
            from autodine_core.modules.queue.service import apply_queue_update

            session.add(_build_inbox_record(envelope, status=EventInboxStatus.PROCESSED))
            apply_queue_update(
                session,
                store_id=envelope.store_id,
                trace_id=envelope.trace_id or envelope.event_id,
                payload=envelope.payload,
            )
            session.commit()
            return {"status": "processed", "event_id": envelope.event_id}

        if envelope.event_type == "device.command_result":
            from autodine_core.modules.device.service import apply_command_result

            session.add(_build_inbox_record(envelope, status=EventInboxStatus.PROCESSED))
            apply_command_result(
                session,
                store_id=envelope.store_id,
                trace_id=envelope.trace_id or envelope.event_id,
                payload=envelope.payload,
            )
            session.commit()
            return {"status": "processed", "event_id": envelope.event_id}

        session.add(_build_inbox_record(envelope, status=EventInboxStatus.IGNORED))
        session.commit()
        return {
            "status": "ignored",
            "event_id": envelope.event_id,
        }
    except IntegrityError:
        # Concurrent deliveries can both pass the initial read before one
        # wins the EventInbox primary-key insert. Treat the losing transaction
        # as the same idempotent duplicate rather than leaking a 500.
        session.rollback()
        if session.get(EventInbox, envelope.event_id) is not None:
            return {"status": "duplicate", "event_id": envelope.event_id}
        raise
    except Exception:
        session.rollback()
        raise
