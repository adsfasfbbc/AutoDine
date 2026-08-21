from __future__ import annotations

from decimal import Decimal
from pathlib import Path
import sys

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session


ROOT = Path(__file__).resolve().parents[1] / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from autodine_core.main import create_app
from autodine_core.modules.event.models import EventOutbox
from autodine_core.modules.inventory.models import Ingredient, Inventory
from autodine_core.modules.inventory.reservations import InventoryMovement, InventoryReservation, MovementType
from autodine_core.modules.menu.models import Product, ProductStatus
from autodine_core.modules.menu.service import recalculate_product_availability
from autodine_core.modules.order.models import Order, OrderStatus
from autodine_core.modules.production.models import ProductionTask, ProductionTaskStatus
from autodine_core.modules.recipe.models import Recipe, RecipeItem


def _build_client() -> TestClient:
    app = create_app(database_url="sqlite+pysqlite:///:memory:")
    app.state.metadata.create_all(app.state.engine)
    return TestClient(app)


def _count_rows(session: Session, model: object) -> int:
    return session.scalar(select(func.count()).select_from(model))


def _seed_menu_catalog(session: Session) -> None:
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
            Ingredient(
                ingredient_id="water",
                name="Water",
                unit="ml",
                inventory_policy="UNLIMITED",
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
            RecipeItem(ingredient_id="water", quantity=Decimal("70"), unit="ml"),
        ]
    )
    session.add(recipe)
    session.add_all(
        [
            Inventory(
                store_id="store-1",
                ingredient_id="bean",
                location_id="bar",
                physical_quantity=Decimal("600"),
                defective_quantity=Decimal("0"),
                reserved_quantity=Decimal("0"),
                reorder_threshold=Decimal("0"),
            ),
            Inventory(
                store_id="store-1",
                ingredient_id="milk",
                location_id="bar",
                physical_quantity=Decimal("500"),
                defective_quantity=Decimal("0"),
                reserved_quantity=Decimal("0"),
                reorder_threshold=Decimal("0"),
            ),
        ]
    )
    session.commit()
    recalculate_product_availability(session, "latte")


def test_create_order_reserves_inventory_creates_task_and_outbox_events() -> None:
    client = _build_client()
    session = client.app.state.session_factory()
    _seed_menu_catalog(session)
    session.close()

    response = client.post(
        "/api/v1/orders",
        json={
            "store_id": "store-1",
            "customer_id": "cust-1",
            "idempotency_key": "idem-order-1",
            "items": [
                {
                    "product_id": "latte",
                    "quantity": 2,
                }
            ],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 0
    order_id = payload["data"]["order_id"]
    task_id = payload["data"]["task"]["task_id"]
    assert payload["data"]["status"] == "CONFIRMED"
    assert payload["data"]["task"]["status"] == "PENDING"

    detail = client.get("/api/v1/orders/" + order_id)
    assert detail.status_code == 200
    detail_payload = detail.json()["data"]
    assert detail_payload["status"] == "CONFIRMED"
    assert [entry["status"] for entry in detail_payload["status_history"]] == ["PENDING", "CONFIRMED"]
    assert detail_payload["task"]["task_id"] == task_id
    assert detail_payload["task"]["status"] == "PENDING"
    assert detail_payload["task"]["pick_list"] == [
        {"ingredient_id": "bean", "quantity": "240", "unit": "g"},
        {"ingredient_id": "milk", "quantity": "160", "unit": "ml"},
    ]

    session = client.app.state.session_factory()
    bean_inventory = session.get(Inventory, ("store-1", "bean", "bar"))
    milk_inventory = session.get(Inventory, ("store-1", "milk", "bar"))
    assert bean_inventory.reserved_quantity == Decimal("240")
    assert milk_inventory.reserved_quantity == Decimal("160")
    assert _count_rows(session, InventoryReservation) == 2
    assert _count_rows(session, Order) == 1
    assert _count_rows(session, ProductionTask) == 1
    outbox_types = [row.event_type for row in session.scalars(select(EventOutbox).order_by(EventOutbox.created_at)).all()]
    assert outbox_types[-3:] == ["order.created", "inventory.reserved", "production.task_created"]
    session.close()


def test_create_order_returns_4091_when_locked_inventory_is_insufficient() -> None:
    client = _build_client()
    session = client.app.state.session_factory()
    _seed_menu_catalog(session)
    bean_inventory = session.get(Inventory, ("store-1", "bean", "bar"))
    bean_inventory.physical_quantity = Decimal("120")
    product = session.get(Product, "latte")
    product.status = ProductStatus.ON_SALE
    product.available_product_quantity = 99
    session.commit()
    session.close()

    response = client.post(
        "/api/v1/orders",
        json={
            "store_id": "store-1",
            "customer_id": "cust-2",
            "idempotency_key": "idem-order-4091",
            "items": [{"product_id": "latte", "quantity": 2}],
        },
    )

    assert response.status_code == 409
    payload = response.json()
    assert payload["code"] == 4091
    assert payload["message"] == "insufficient inventory"

    session = client.app.state.session_factory()
    assert _count_rows(session, Order) == 0
    assert _count_rows(session, ProductionTask) == 0
    assert _count_rows(session, InventoryReservation) == 0
    session.close()


def test_create_order_returns_4092_when_product_is_sold_out_or_unavailable() -> None:
    client = _build_client()
    session = client.app.state.session_factory()
    _seed_menu_catalog(session)
    bean_inventory = session.get(Inventory, ("store-1", "bean", "bar"))
    bean_inventory.physical_quantity = Decimal("0")
    session.commit()
    recalculate_product_availability(session, "latte")
    session.close()

    response = client.post(
        "/api/v1/orders",
        json={
            "store_id": "store-1",
            "customer_id": "cust-3",
            "idempotency_key": "idem-order-4092",
            "items": [{"product_id": "latte", "quantity": 1}],
        },
    )

    assert response.status_code == 409
    payload = response.json()
    assert payload["code"] == 4092
    assert payload["message"] == "product unavailable"


def test_repeat_idempotency_key_returns_existing_order_and_conflicting_payload_returns_409() -> None:
    client = _build_client()
    session = client.app.state.session_factory()
    _seed_menu_catalog(session)
    session.close()

    first = client.post(
        "/api/v1/orders",
        json={
            "store_id": "store-1",
            "customer_id": "cust-4",
            "idempotency_key": "idem-repeat",
            "items": [{"product_id": "latte", "quantity": 1}],
        },
    )
    second = client.post(
        "/api/v1/orders",
        json={
            "store_id": "store-1",
            "customer_id": "cust-4",
            "idempotency_key": "idem-repeat",
            "items": [{"product_id": "latte", "quantity": 1}],
        },
    )
    conflict = client.post(
        "/api/v1/orders",
        json={
            "store_id": "store-1",
            "customer_id": "cust-4",
            "idempotency_key": "idem-repeat",
            "items": [{"product_id": "latte", "quantity": 2}],
        },
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["data"]["order_id"] == second.json()["data"]["order_id"]
    assert second.json()["data"]["idempotency_status"] == "replayed"
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "IDEMPOTENCY_CONFLICT"

    session = client.app.state.session_factory()
    assert _count_rows(session, Order) == 1
    assert _count_rows(session, InventoryReservation) == 2
    bean_inventory = session.get(Inventory, ("store-1", "bean", "bar"))
    assert bean_inventory.reserved_quantity == Decimal("120")
    session.close()


def test_cancel_order_releases_reservations_and_is_idempotent() -> None:
    client = _build_client()
    session = client.app.state.session_factory()
    _seed_menu_catalog(session)
    session.close()

    create = client.post(
        "/api/v1/orders",
        json={
            "store_id": "store-1",
            "customer_id": "cust-5",
            "idempotency_key": "idem-cancel",
            "items": [{"product_id": "latte", "quantity": 1}],
        },
    )
    order_id = create.json()["data"]["order_id"]

    first_cancel = client.post("/api/v1/orders/" + order_id + "/cancel")
    second_cancel = client.post("/api/v1/orders/" + order_id + "/cancel")

    assert first_cancel.status_code == 200
    assert first_cancel.json()["data"]["status"] == "CANCELED"
    assert second_cancel.status_code == 200
    assert second_cancel.json()["data"]["status"] == "CANCELED"

    session = client.app.state.session_factory()
    bean_inventory = session.get(Inventory, ("store-1", "bean", "bar"))
    milk_inventory = session.get(Inventory, ("store-1", "milk", "bar"))
    order = session.get(Order, order_id)
    task = session.scalar(select(ProductionTask).where(ProductionTask.order_id == order_id))
    assert bean_inventory.reserved_quantity == Decimal("0")
    assert milk_inventory.reserved_quantity == Decimal("0")
    assert order.status is OrderStatus.CANCELED
    assert task.status is ProductionTaskStatus.CANCELED
    released = session.scalars(select(EventOutbox).where(EventOutbox.event_type == "inventory.released")).all()
    assert len(released) == 1
    session.close()


def test_production_task_transitions_complete_order_and_record_actual_consumption_movements() -> None:
    client = _build_client()
    session = client.app.state.session_factory()
    _seed_menu_catalog(session)
    session.close()

    create = client.post(
        "/api/v1/orders",
        json={
            "store_id": "store-1",
            "customer_id": "cust-6",
            "idempotency_key": "idem-complete",
            "items": [{"product_id": "latte", "quantity": 1}],
        },
    )
    order_id = create.json()["data"]["order_id"]
    task_id = create.json()["data"]["task"]["task_id"]

    start = client.post("/api/v1/production/tasks/" + task_id + "/start")
    ready = client.post("/api/v1/production/tasks/" + task_id + "/ready")
    complete = client.post(
        "/api/v1/production/tasks/" + task_id + "/complete",
        json={
            "actual_consumption": [
                {"ingredient_id": "bean", "location_id": "bar", "quantity": "110"},
                {"ingredient_id": "milk", "location_id": "bar", "quantity": "75"},
            ]
        },
    )

    assert start.status_code == 200
    assert start.json()["data"]["status"] == "PRODUCING"
    assert ready.status_code == 200
    assert ready.json()["data"]["status"] == "READY"
    assert complete.status_code == 200
    assert complete.json()["data"]["status"] == "COMPLETED"

    detail = client.get("/api/v1/orders/" + order_id)
    assert detail.status_code == 200
    order_payload = detail.json()["data"]
    assert order_payload["status"] == "COMPLETED"
    assert [entry["status"] for entry in order_payload["status_history"]] == [
        "PENDING",
        "CONFIRMED",
        "PRODUCING",
        "READY",
        "COMPLETED",
    ]
    assert order_payload["task"]["status"] == "COMPLETED"

    session = client.app.state.session_factory()
    bean_inventory = session.get(Inventory, ("store-1", "bean", "bar"))
    milk_inventory = session.get(Inventory, ("store-1", "milk", "bar"))
    assert bean_inventory.physical_quantity == Decimal("490")
    assert milk_inventory.physical_quantity == Decimal("425")
    assert bean_inventory.reserved_quantity == Decimal("0")
    assert milk_inventory.reserved_quantity == Decimal("0")

    movements = session.scalars(
        select(InventoryMovement)
        .where(InventoryMovement.order_id == order_id)
        .order_by(InventoryMovement.created_at, InventoryMovement.ingredient_id)
    ).all()
    assert [(movement.ingredient_id, movement.movement_type, str(movement.quantity)) for movement in movements] == [
        ("bean", MovementType.RESERVE, "120.000"),
        ("milk", MovementType.RESERVE, "80.000"),
        ("bean", MovementType.CONSUME, "110.000"),
        ("milk", MovementType.CONSUME, "75.000"),
        ("bean", MovementType.RELEASE, "120.000"),
        ("milk", MovementType.RELEASE, "80.000"),
    ]

    outbox_types = [row.event_type for row in session.scalars(select(EventOutbox).order_by(EventOutbox.created_at)).all()]
    assert outbox_types[-7:] == [
        "inventory.reserved",
        "production.task_created",
        "production.task_started",
        "production.task_ready",
        "inventory.released",
        "production.task_completed",
        "menu.availability_changed",
    ]
    session.close()
