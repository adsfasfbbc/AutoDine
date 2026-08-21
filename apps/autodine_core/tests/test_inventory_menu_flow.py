from __future__ import annotations

from decimal import Decimal
from pathlib import Path
import sys

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session


ROOT = Path(__file__).resolve().parents[1] / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from autodine_core.main import create_app
from autodine_core.modules.inventory.models import Ingredient, Inventory
from autodine_core.modules.inventory.service import calculate_available_quantity
from autodine_core.modules.menu.models import Product, ProductStatus
from autodine_core.modules.menu.service import (
    calculate_product_quantity,
    recalculate_product_availability,
)
from autodine_core.modules.recipe.models import Recipe, RecipeItem


def _build_client() -> TestClient:
    app = create_app(database_url="sqlite+pysqlite:///:memory:")
    app.state.metadata.create_all(app.state.engine)
    return TestClient(app)


def _seed_product_with_recipe(
    session: Session,
    *,
    physical_coffee: Decimal,
    physical_milk: Decimal,
    water_policy: str = "UNLIMITED",
) -> Product:
    coffee = Ingredient(
        ingredient_id="bean",
        name="Coffee Bean",
        unit="g",
        inventory_policy="TRACKED",
    )
    milk = Ingredient(
        ingredient_id="milk",
        name="Milk",
        unit="ml",
        inventory_policy="TRACKED",
    )
    water = Ingredient(
        ingredient_id="water",
        name="Water",
        unit="ml",
        inventory_policy=water_policy,
    )

    product = Product(
        product_id="latte",
        name="Latte",
        price=Decimal("18.50"),
    )
    recipe = Recipe(recipe_id="latte-bom", product_id=product.product_id)
    recipe.items.extend(
        [
            RecipeItem(ingredient_id="bean", quantity=Decimal("120"), unit="g"),
            RecipeItem(ingredient_id="milk", quantity=Decimal("80"), unit="ml"),
            RecipeItem(ingredient_id="water", quantity=Decimal("70"), unit="ml"),
        ]
    )
    product.recipe = recipe

    session.add_all(
        [
            coffee,
            milk,
            water,
            product,
            Inventory(
                store_id="store-1",
                ingredient_id="bean",
                location_id="bar",
                physical_quantity=physical_coffee,
                defective_quantity=Decimal("0"),
                reserved_quantity=Decimal("0"),
                reorder_threshold=Decimal("0"),
            ),
            Inventory(
                store_id="store-1",
                ingredient_id="milk",
                location_id="bar",
                physical_quantity=physical_milk,
                defective_quantity=Decimal("0"),
                reserved_quantity=Decimal("0"),
                reorder_threshold=Decimal("0"),
            ),
        ]
    )
    session.commit()
    return product


def test_calculate_available_quantity_caps_at_zero() -> None:
    result = calculate_available_quantity(
        Decimal("10"),
        Decimal("4"),
        Decimal("8"),
    )

    assert result == Decimal("0")


def test_calculate_product_quantity_uses_bom_minimum_and_ignores_unlimited_ingredients() -> None:
    quantity = calculate_product_quantity(
        recipe_items=[
            {"ingredient_id": "bean", "quantity": Decimal("120")},
            {"ingredient_id": "milk", "quantity": Decimal("80")},
            {"ingredient_id": "water", "quantity": Decimal("70")},
        ],
        inventory_by_ingredient={
            "bean": Decimal("600"),
            "milk": Decimal("500"),
        },
        ingredient_policies={
            "bean": "TRACKED",
            "milk": "TRACKED",
            "water": "UNLIMITED",
        },
    )

    assert quantity == 5


def test_recalculate_product_availability_marks_sold_out_at_zero_and_reactivates_when_stock_returns() -> None:
    client = _build_client()
    session = client.app.state.session_factory()
    _seed_product_with_recipe(
        session,
        physical_coffee=Decimal("0"),
        physical_milk=Decimal("500"),
    )

    product = recalculate_product_availability(session, "latte")
    assert product.available_product_quantity == 0
    assert product.status is ProductStatus.SOLD_OUT

    inventory = session.get(Inventory, ("store-1", "bean", "bar"))
    inventory.physical_quantity = Decimal("600")
    session.commit()

    product = recalculate_product_availability(session, "latte")
    assert product.available_product_quantity == 5
    assert product.status is ProductStatus.ON_SALE

    session.close()


def test_inventory_and_menu_routes_return_standard_envelope_with_current_availability() -> None:
    client = _build_client()
    session = client.app.state.session_factory()
    _seed_product_with_recipe(
        session,
        physical_coffee=Decimal("600"),
        physical_milk=Decimal("500"),
        water_policy="UNLIMITED",
    )
    recalculate_product_availability(session, "latte")
    session.close()

    inventory_response = client.get("/api/v1/inventory")
    assert inventory_response.status_code == 200
    inventory_payload = inventory_response.json()
    assert inventory_payload["code"] == 0
    assert inventory_payload["message"] == "success"
    assert inventory_payload["request_id"]
    assert inventory_payload["timestamp"]
    assert len(inventory_payload["data"]) == 2
    assert inventory_payload["data"][0]["available_quantity"] in {"600", "500"}

    menu_response = client.get("/api/v1/menu")
    assert menu_response.status_code == 200
    menu_payload = menu_response.json()
    assert menu_payload["code"] == 0
    assert menu_payload["data"][0]["product_id"] == "latte"
    assert menu_payload["data"][0]["available_product_quantity"] == 5
    assert menu_payload["data"][0]["status"] == "ON_SALE"

    detail_response = client.get("/api/v1/menu/latte")
    assert detail_response.status_code == 200
    detail_payload = detail_response.json()
    assert detail_payload["code"] == 0
    assert detail_payload["data"]["product_id"] == "latte"
    assert detail_payload["data"]["available_product_quantity"] == 5
