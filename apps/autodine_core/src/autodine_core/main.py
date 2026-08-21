from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict

from fastapi import FastAPI

from autodine_core.config import Settings, build_settings
from autodine_core.infrastructure.database import Base, build_engine, build_session_factory
from autodine_core.infrastructure.event_bus import NullEventPublisher
from autodine_core.modules.event.routes import router as event_router
from autodine_core.modules.inventory.routes import router as inventory_router
from autodine_core.modules.menu.routes import router as menu_router
from autodine_core.modules.order.routes import router as order_router
from autodine_core.modules.production.routes import router as production_router


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def create_app(database_url: str | None = None) -> FastAPI:
    settings = build_settings(database_url)
    engine = build_engine(settings.database_url)
    session_factory = build_session_factory(engine)

    app = FastAPI(title=settings.service_name)
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = session_factory
    app.state.metadata = Base.metadata
    app.state.event_publisher = NullEventPublisher()

    @app.get("/health")
    def healthcheck() -> Dict[str, str]:
        return {
            "status": "ok",
            "service": settings.service_name,
            "timestamp": _utc_timestamp(),
        }

    app.include_router(inventory_router)
    app.include_router(menu_router)
    app.include_router(event_router)
    app.include_router(order_router)
    app.include_router(production_router)

    return app
