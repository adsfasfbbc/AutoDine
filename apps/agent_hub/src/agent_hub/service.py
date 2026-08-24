from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .errors import UnknownAgentError
from .hub import AgentHub

WEB_DIR = Path(__file__).resolve().parent / "web"


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    history: Optional[List[Dict[str, str]]] = None


class ChatResponse(BaseModel):
    agent: str
    reply: str


def create_app(hub: Optional[AgentHub] = None) -> FastAPI:
    hub = hub or AgentHub()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        hub.close()

    app = FastAPI(title="AutoDine Agent Hub", lifespan=lifespan)

    @app.get("/health")
    def health() -> Dict[str, Any]:
        return {"status": "ok", "service": "agent_hub"}

    @app.get("/api/v1/agents")
    def list_agents() -> List[Dict[str, Any]]:
        return hub.describe()

    @app.post("/api/v1/agents/{agent_name}/chat", response_model=ChatResponse)
    def chat(agent_name: str, body: ChatRequest) -> ChatResponse:
        try:
            reply = hub.run(agent_name, body.message, body.history)
        except UnknownAgentError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except Exception as exc:  # noqa: BLE001 - always return a JSON reply, never a bare 500
            reply = f"处理请求时出错：{exc}"
        return ChatResponse(agent=agent_name, reply=reply)

    # --- Web UI -----------------------------------------------------------
    app.mount("/static", StaticFiles(directory=str(WEB_DIR / "static")), name="static")

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(WEB_DIR / "index.html")

    @app.get("/consumer", include_in_schema=False)
    def consumer_page() -> FileResponse:
        return FileResponse(WEB_DIR / "consumer.html")

    @app.get("/kitchen", include_in_schema=False)
    def kitchen_page() -> FileResponse:
        return FileResponse(WEB_DIR / "kitchen.html")

    @app.get("/manager", include_in_schema=False)
    def manager_page() -> FileResponse:
        return FileResponse(WEB_DIR / "manager.html")

    return app
