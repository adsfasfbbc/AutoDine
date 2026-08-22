from __future__ import annotations

from decimal import Decimal
import json
from pathlib import Path
import sys

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session


ROOT = Path(__file__).resolve().parents[1] / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from autodine_core.main import create_app
from autodine_core.modules.event.models import EventInbox, EventOutbox
from autodine_core.modules.inventory.models import Ingredient, Inventory
from autodine_core.modules.menu.models import Product, ProductStatus
from autodine_core.modules.menu.service import recalculate_product_availability
from autodine_core.modules.recipe.models import Recipe, RecipeItem


def _build_client() -> TestClient:
    app = create_app(database_url="sqlite+pysqlite:///:memory:")
    app.state.metadata.create_all(app.state.engine)
    return TestClient(app)


def _inventory_detected_event(*, event_id: str, ingredient_id: str, physical_quantity: str) -> dict:
    return {
        "protocol": "ADP",
        "version": "1.0",
        "event_id": event_id,
        "trace_id": "trace-" + event_id,
        "event_type": "inventory.detected",
        "severity": "info",
        "timestamp": "2026-08-21T10:30:00Z",
        "store_id": "store-1",
        "source": {
            "module": "vision",
            "device_id": "cam-01",
        },
        "payload": {
            "ingredient_id": ingredient_id,
            "location_id": "bar",
            "physical_quantity": physical_quantity,
            "unit": "g",
            "store_id": "ignored-store",
        },
    }


def _quality_abnormal_event(*, event_id: str, ingredient_id: str, defective_quantity: str) -> dict:
    return {
        "protocol": "ADP",
        "version": "1.0",
        "event_id": event_id,
        "trace_id": "trace-" + event_id,
        "event_type": "quality.abnormal",
        "severity": "info",
        "timestamp": "2026-08-21T11:00:00Z",
        "store_id": "store-1",
        "source": {
            "module": "quality",
        },
        "payload": {
            "ingredient_id": ingredient_id,
            "location_id": "bar",
            "defective_quantity": defective_quantity,
        },
    }


def _count_rows(session: Session, model: object) -> int:
    return session.scalar(select(func.count()).select_from(model))


def _seed_ingredient(
    session: Session,
    *,
    ingredient_id: str,
    name: str,
    unit: str = "g",
) -> None:
    session.add(
        Ingredient(
            ingredient_id=ingredient_id,
            name=name,
            unit=unit,
            inventory_policy="TRACKED",
        )
    )
    session.commit()


def _seed_recipe_product(session: Session) -> None:
    session.add_all(
        [
            Ingredient(
                ingredient_id="bean",
                name="Coffee Bean",
                unit="g",
                inventory_policy="TRACKED",
            ),
            Ingredient(
                ingredient_id="milk",
                name="Milk",
                unit="ml",
                inventory_policy="TRACKED",
            ),
            Product(
                product_id="latte",
                name="Latte",
                price=Decimal("18.50"),
            ),
        ]
    )
    session.flush()

    recipe = Recipe(recipe_id="latte-bom", product_id="latte")
    recipe.items.extend(
        [
            RecipeItem(ingredient_id="bean", quantity=Decimal("120"), unit="g"),
            RecipeItem(ingredient_id="milk", quantity=Decimal("80"), unit="ml"),
        ]
    )
    session.add(recipe)
    session.add(
        Inventory(
            store_id="store-1",
            ingredient_id="milk",
            location_id="bar",
            physical_quantity=Decimal("500"),
            defective_quantity=Decimal("0"),
            reserved_quantity=Decimal("0"),
            reorder_threshold=Decimal("0"),
        )
    )
    session.commit()


def test_post_events_rejects_invalid_adp_envelope() -> None:
    client = _build_client()

    response = client.post(
        "/api/v1/events",
        json={
            "protocol": "MQTT",
                "version": "2.0",
                "event_id": "evt-invalid",
                "trace_id": "trace-evt-invalid",
                "event_type": "inventory.detected",
                "severity": "info",
                "timestamp": "2026-08-21T10:30:00Z",
            "store_id": "store-1",
            "source": {"module": "vision"},
            "payload": {
                "ingredient_id": "bean",
                "location_id": "bar",
                "physical_quantity": "10",
                "unit": "g",
            },
        },
    )

    assert response.status_code == 422
    payload = response.json()
    assert payload["code"] == "INVALID_EVENT_ENVELOPE"
    assert payload["message"] == "invalid event envelope"
    assert payload["request_id"]
    assert payload["timestamp"]


def test_duplicate_event_id_is_accepted_once_without_second_inventory_mutation_or_outbox() -> None:
    client = _build_client()
    session = client.app.state.session_factory()
    _seed_ingredient(session, ingredient_id="syrup", name="Syrup")
    session.close()

    first_response = client.post(
        "/api/v1/events",
        json=_inventory_detected_event(
            event_id="evt-duplicate",
            ingredient_id="syrup",
            physical_quantity="10",
        ),
    )
    second_response = client.post(
        "/api/v1/events",
        json=_inventory_detected_event(
            event_id="evt-duplicate",
            ingredient_id="syrup",
            physical_quantity="99",
        ),
    )

    assert first_response.status_code == 200
    assert first_response.json()["data"]["status"] == "processed"
    assert second_response.status_code == 200
    assert second_response.json()["data"]["status"] == "duplicate"

    session = client.app.state.session_factory()
    inventory = session.get(Inventory, ("store-1", "syrup", "bar"))
    assert inventory.physical_quantity == Decimal("10")
    assert _count_rows(session, EventInbox) == 1
    assert _count_rows(session, EventOutbox) == 1
    session.close()


def test_inventory_detected_upserts_snapshot_and_recalculates_only_affected_menu_products() -> None:
    client = _build_client()
    session = client.app.state.session_factory()
    _seed_recipe_product(session)
    session.close()

    response = client.post(
        "/api/v1/events",
        json=_inventory_detected_event(
            event_id="evt-detected",
            ingredient_id="bean",
            physical_quantity="600",
        ),
    )

    assert response.status_code == 200
    assert response.json()["data"]["status"] == "processed"

    session = client.app.state.session_factory()
    inventory = session.get(Inventory, ("store-1", "bean", "bar"))
    assert inventory.physical_quantity == Decimal("600")
    assert inventory.defective_quantity == Decimal("0")
    product = session.get(Product, "latte")
    assert product.available_product_quantity == 5
    assert product.status is ProductStatus.ON_SALE
    outbox_types = [row.event_type for row in session.scalars(select(EventOutbox).order_by(EventOutbox.created_at)).all()]
    assert outbox_types == ["inventory.changed", "menu.availability_changed"]
    session.close()


def test_quality_abnormal_updates_defective_quantity_without_double_subtracting_physical() -> None:
    client = _build_client()
    session = client.app.state.session_factory()
    _seed_recipe_product(session)
    session.add(
        Inventory(
            store_id="store-1",
            ingredient_id="bean",
            location_id="bar",
            physical_quantity=Decimal("600"),
            defective_quantity=Decimal("0"),
            reserved_quantity=Decimal("0"),
            reorder_threshold=Decimal("0"),
        )
    )
    session.commit()
    recalculate_product_availability(session, "latte", "store-1")
    session.close()

    response = client.post(
        "/api/v1/events",
        json=_quality_abnormal_event(
            event_id="evt-quality",
            ingredient_id="bean",
            defective_quantity="600",
        ),
    )

    assert response.status_code == 200
    assert response.json()["data"]["status"] == "processed"

    session = client.app.state.session_factory()
    inventory = session.get(Inventory, ("store-1", "bean", "bar"))
    assert inventory.physical_quantity == Decimal("600")
    assert inventory.defective_quantity == Decimal("600")
    product = session.get(Product, "latte")
    assert product.available_product_quantity == 0
    assert product.status is ProductStatus.SOLD_OUT
    session.close()


def test_processed_event_creates_outbox_record_with_trace_store_and_publish_status() -> None:
    client = _build_client()
    session = client.app.state.session_factory()
    _seed_ingredient(session, ingredient_id="cocoa", name="Cocoa")
    session.close()

    response = client.post(
        "/api/v1/events",
        json=_inventory_detected_event(
            event_id="evt-outbox",
            ingredient_id="cocoa",
            physical_quantity="24",
        ),
    )

    assert response.status_code == 200

    session = client.app.state.session_factory()
    outbox = session.scalar(select(EventOutbox).where(EventOutbox.trace_id == "trace-evt-outbox"))
    assert outbox is not None
    assert outbox.outbox_id
    assert outbox.store_id == "store-1"
    assert outbox.event_type == "inventory.changed"
    assert outbox.severity == "info"
    assert outbox.publish_status == "PUBLISHED"
    assert outbox.payload["ingredient_id"] == "cocoa"
    session.close()


MOCK_FIXTURES = Path(__file__).resolve().parents[3] / "data" / "mock"


def _seed_milk_product(session: Session) -> None:
    session.add_all(
        [
            Ingredient(
                ingredient_id="milk",
                name="Milk",
                unit="ml",
                inventory_policy="TRACKED",
            ),
            Product(
                product_id="milk-tea",
                name="Milk Tea",
                price=Decimal("12.00"),
            ),
        ]
    )
    session.flush()
    recipe = Recipe(recipe_id="milk-tea-bom", product_id="milk-tea")
    recipe.items.append(RecipeItem(ingredient_id="milk", quantity=Decimal("80"), unit="ml"))
    session.add(recipe)
    session.commit()


def test_vision_storage_detected_fixture_replay_updates_inventory_and_menu() -> None:
    client = _build_client()
    session = client.app.state.session_factory()
    _seed_milk_product(session)
    session.close()

    fixture = json.loads((MOCK_FIXTURES / "storage_detection.json").read_text(encoding="utf-8"))
    response = client.post("/api/v1/events", json=fixture)

    assert response.status_code == 200
    assert response.json()["data"]["status"] == "processed"

    session = client.app.state.session_factory()
    inventory = session.get(Inventory, ("store-main", "milk", "bar"))
    assert inventory is not None
    assert inventory.physical_quantity == Decimal("12000")
    product = session.get(Product, "milk-tea")
    assert product.status is ProductStatus.ON_SALE
    assert product.available_product_quantity == 150
    outbox_types = [row.event_type for row in session.scalars(select(EventOutbox).order_by(EventOutbox.created_at)).all()]
    assert outbox_types == ["inventory.changed", "menu.availability_changed"]
    session.close()


def test_vision_storage_detected_skips_low_confidence_detections() -> None:
    client = _build_client()
    session = client.app.state.session_factory()
    _seed_milk_product(session)
    session.close()

    response = client.post(
        "/api/v1/events",
        json={
            "protocol": "ADP",
            "version": "1.0",
            "event_id": "evt-vision-low-confidence",
            "trace_id": "trace-evt-vision-low-confidence",
            "event_type": "vision.storage.detected",
            "severity": "info",
            "timestamp": "2026-08-21T10:30:00Z",
            "store_id": "store-1",
            "source": {"module": "smart_storage_vision", "device_id": "cam-01"},
            "payload": {
                "location_id": "bar",
                "detections": [
                    {"ingredient_id": "milk", "quantity": "500", "unit": "ml", "confidence": 0.1},
                ],
            },
        },
    )

    assert response.status_code == 200
    assert response.json()["data"]["status"] == "processed"

    session = client.app.state.session_factory()
    assert session.get(Inventory, ("store-1", "milk", "bar")) is None
    assert _count_rows(session, EventOutbox) == 0
    session.close()
