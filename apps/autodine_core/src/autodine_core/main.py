from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import FastAPI, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from autodine_core.config import Settings, build_settings
from autodine_core.infrastructure.database import Base, build_engine, build_session_factory
from autodine_core.infrastructure.event_bus import InMemoryEventPublisher, WebSocketConnectionManager
from autodine_core.infrastructure.event_bus.routes import router as websocket_router
from autodine_core.modules.alarm.routes import router as alarm_router
from autodine_core.modules.analytics.routes import router as analytics_router
from autodine_core.modules.device.routes import router as device_router
from autodine_core.modules.event.routes import router as event_router
from autodine_core.modules.inventory.routes import router as inventory_router
from autodine_core.modules.menu.routes import router as menu_router
from autodine_core.modules.order.routes import router as order_router
from autodine_core.modules.production.routes import router as production_router
from autodine_core.modules.queue.routes import router as queue_router
from autodine_core.modules import response_envelope


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
    app.state.websocket_manager = WebSocketConnectionManager()
    app.state.event_publisher = InMemoryEventPublisher(app.state.websocket_manager)

    @app.exception_handler(RequestValidationError)
    async def request_validation_handler(request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content=jsonable_encoder(
                response_envelope(
                    {"errors": exc.errors()},
                    code="VALIDATION_ERROR",
                    message="request validation failed",
                )
            ),
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request, exc: HTTPException):
        detail = exc.detail
        if isinstance(detail, dict) and "code" in detail:
            code = detail["code"]
            message = detail.get("message", "request failed")
        else:
            code = "HTTP_" + str(exc.status_code)
            message = str(detail)
        return JSONResponse(
            status_code=exc.status_code,
            content=jsonable_encoder(response_envelope({}, code=code, message=message)),
        )

    @app.get("/health")
    def healthcheck() -> Dict[str, Any]:
        return response_envelope(
            {
                "status": "ok",
                "service": settings.service_name,
                "timestamp": _utc_timestamp(),
            }
        )

    app.include_router(inventory_router)
    app.include_router(menu_router)
    app.include_router(event_router)
    app.include_router(order_router)
    app.include_router(production_router)
    app.include_router(queue_router)
    app.include_router(device_router)
    app.include_router(alarm_router)
    app.include_router(analytics_router)
    app.include_router(websocket_router)

    return app
