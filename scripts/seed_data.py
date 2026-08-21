"""Idempotently load the deterministic demo catalog into an AutoDine database."""
from __future__ import print_function

import argparse
from decimal import Decimal
import json
from pathlib import Path
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
CORE_SOURCE = REPOSITORY_ROOT / "apps" / "autodine_core" / "src"
if str(CORE_SOURCE) not in sys.path:
    sys.path.insert(0, str(CORE_SOURCE))

from autodine_core.infrastructure.database import Base, build_engine, build_session_factory
from autodine_core.modules.inventory.models import Ingredient, Inventory, InventoryPolicy
from autodine_core.modules.menu.models import Product, ProductStatus
from autodine_core.modules.menu.service import recalculate_product_availability
from autodine_core.modules.recipe.models import Recipe, RecipeItem
from autodine_core.modules.inventory import reservations as _reservations  # noqa: F401
from autodine_core.modules.event import models as _event_models  # noqa: F401
from autodine_core.modules.order import models as _order_models  # noqa: F401
from autodine_core.modules.production import models as _production_models  # noqa: F401
from autodine_core.modules.queue import models as _queue_models  # noqa: F401
from autodine_core.modules.device import models as _device_models  # noqa: F401
from autodine_core.modules.alarm import models as _alarm_models  # noqa: F401


DEFAULT_CATALOG = REPOSITORY_ROOT / "data" / "seed" / "catalog.json"


def load_catalog(path):
    with Path(path).open(encoding="utf-8") as handle:
        return json.load(handle)


def seed_database(database_url, catalog_path=DEFAULT_CATALOG):
    """Upsert the static catalog; tracked stock is reset to its documented snapshot."""
    catalog = load_catalog(catalog_path)
    engine = build_engine(database_url)
    if database_url.startswith("sqlite"):
        Base.metadata.create_all(engine)
    session = build_session_factory(engine)()
    try:
        for data in catalog["ingredients"]:
            ingredient = session.get(Ingredient, data["ingredient_id"])
            if ingredient is None:
                ingredient = Ingredient(
                    ingredient_id=data["ingredient_id"],
                    name=data["name"],
                    unit=data["unit"],
                    inventory_policy=InventoryPolicy(data["inventory_policy"]),
                )
                session.add(ingredient)
            else:
                ingredient.name = data["name"]
                ingredient.unit = data["unit"]
                ingredient.inventory_policy = InventoryPolicy(data["inventory_policy"])
            if ingredient.inventory_policy is InventoryPolicy.TRACKED:
                key = (catalog["store_id"], ingredient.ingredient_id, catalog["location_id"])
                inventory = session.get(Inventory, key)
                if inventory is None:
                    inventory = Inventory(
                        store_id=key[0], ingredient_id=key[1], location_id=key[2],
                        physical_quantity=Decimal("0"), defective_quantity=Decimal("0"),
                        reserved_quantity=Decimal("0"), reorder_threshold=Decimal("0"),
                    )
                    session.add(inventory)
                inventory.physical_quantity = Decimal(data["physical_quantity"])
                inventory.defective_quantity = Decimal("0")
                inventory.reserved_quantity = Decimal("0")
                inventory.reorder_threshold = Decimal("0")

        session.flush()
        for data in catalog["products"]:
            product = session.get(Product, data["product_id"])
            if product is None:
                product = Product(product_id=data["product_id"], name=data["name"], price=Decimal(data["price"]))
                session.add(product)
            else:
                product.name = data["name"]
                product.price = Decimal(data["price"])
            recipe_id = data["product_id"] + "-bom"
            recipe = session.get(Recipe, recipe_id)
            if recipe is None:
                recipe = Recipe(recipe_id=recipe_id, product_id=product.product_id)
                session.add(recipe)
            else:
                recipe.product_id = product.product_id
                recipe.items.clear()
            for item in data["bom"]:
                recipe.items.append(RecipeItem(
                    ingredient_id=item["ingredient_id"], quantity=Decimal(item["quantity"]), unit=item["unit"],
                ))
        session.flush()
        for product in catalog["products"]:
            recalculate_product_availability(session, product["product_id"], commit=False)
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
        engine.dispose()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", required=True, help="SQLAlchemy URL; migrate PostgreSQL first")
    parser.add_argument("--catalog", default=str(DEFAULT_CATALOG))
    args = parser.parse_args(argv)
    seed_database(args.database_url, args.catalog)
    print("Seeded catalog from {0}".format(args.catalog))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
