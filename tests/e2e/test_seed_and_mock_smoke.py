from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

from fastapi.testclient import TestClient
from sqlalchemy import func, select


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
CORE_SOURCE = REPOSITORY_ROOT / "apps" / "autodine_core" / "src"
if str(CORE_SOURCE) not in sys.path:
    sys.path.insert(0, str(CORE_SOURCE))

from autodine_core.main import create_app
from autodine_core.modules.inventory.models import Ingredient
from autodine_core.modules.inventory.reservations import InventoryReservation
from autodine_core.modules.menu.models import Product, ProductStatus
from autodine_core.modules.production.models import ProductionTask
from autodine_core.modules.recipe.models import Recipe


def _run_seed(database_url: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "scripts/seed_data.py", "--database-url", database_url],
        cwd=str(REPOSITORY_ROOT),
        capture_output=True,
        text=True,
    )


def test_alembic_config_resolves_migrations_from_repository_root() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "apps/autodine_core/alembic.ini", "heads"],
        cwd=str(REPOSITORY_ROOT),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "20260821_0001" in result.stdout


def test_alembic_environment_reads_core_database_url() -> None:
    environment_source = (REPOSITORY_ROOT / "apps" / "autodine_core" / "migrations" / "env.py").read_text(
        encoding="utf-8"
    )
    assert "AUTODINE_CORE_DATABASE_URL" in environment_source


def test_seed_is_idempotent_and_mock_inventory_flow_creates_reservation_and_production_task(tmp_path: Path) -> None:
    database_url = "sqlite+pysqlite:///" + str(tmp_path / "autodine-e2e.db")

    first_seed = _run_seed(database_url)
    assert first_seed.returncode == 0, first_seed.stderr
    second_seed = _run_seed(database_url)
    assert second_seed.returncode == 0, second_seed.stderr

    app = create_app(database_url=database_url)
    client = TestClient(app)
    session = app.state.session_factory()
    assert session.scalar(select(func.count()).select_from(Product)) >= 20
    assert session.scalar(select(func.count()).select_from(Ingredient)) >= 25
    assert session.scalar(select(func.count()).select_from(Recipe)) >= 20
    assert session.scalar(select(func.count()).select_from(Product)) == 20
    session.close()

    events = json.loads((REPOSITORY_ROOT / "data" / "mock" / "e2e_inventory_menu_order.json").read_text(encoding="utf-8"))
    assert client.post("/api/v1/events", json=events["sold_out"]).status_code == 200
    assert client.get("/api/v1/menu/latte", params={"store_id": "store-main"}).json()["data"]["status"] == ProductStatus.SOLD_OUT.value
    assert client.post("/api/v1/events", json=events["recovered"]).status_code == 200
    assert client.get("/api/v1/menu/latte", params={"store_id": "store-main"}).json()["data"]["status"] == ProductStatus.ON_SALE.value

    order = client.post(
        "/api/v1/orders",
        json={
            "store_id": "store-main",
            "customer_id": "e2e-customer",
            "idempotency_key": "e2e-latte-order-1",
            "items": [{"product_id": "latte", "quantity": 1}],
        },
    )
    assert order.status_code == 200
    assert order.json()["data"]["status"] == "CONFIRMED"
    assert order.json()["data"]["task"]["status"] == "PENDING"

    session = app.state.session_factory()
    assert session.scalar(select(func.count()).select_from(InventoryReservation)) > 0
    assert session.scalar(select(func.count()).select_from(ProductionTask)) == 1
    session.close()
