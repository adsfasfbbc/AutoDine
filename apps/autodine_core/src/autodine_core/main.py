from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict

from fastapi import FastAPI

from autodine_core.config import Settings, build_settings
from autodine_core.infrastructure.database import Base, build_engine, build_session_factory


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

    @app.get("/health")
    def healthcheck() -> Dict[str, str]:
        return {
            "status": "ok",
            "service": settings.service_name,
            "timestamp": _utc_timestamp(),
        }

    return app
