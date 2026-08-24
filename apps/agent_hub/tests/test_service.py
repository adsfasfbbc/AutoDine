from __future__ import annotations

from fastapi.testclient import TestClient

from agent_hub.config import Settings
from agent_hub.hub import AgentHub
from agent_hub.service import create_app

from .helpers import FakeCore


def _make_app():
    fake = FakeCore()
    settings = Settings(
        core_base_url="http://core",
        default_store_id="store-main",
        default_location_id="bar",
        llm_driver="scripted",
    )
    hub = AgentHub(settings, client=fake.client())
    return create_app(hub), fake


def test_health():
    app, _ = _make_app()
    with TestClient(app) as client:
        assert client.get("/health").json()["status"] == "ok"


def test_list_agents():
    app, _ = _make_app()
    with TestClient(app) as client:
        data = client.get("/api/v1/agents").json()
        assert {a["name"] for a in data} == {"consumer", "kitchen", "manager"}


def test_chat_unknown_agent_404():
    app, _ = _make_app()
    with TestClient(app) as client:
        resp = client.post("/api/v1/agents/nope/chat", json={"message": "hi"})
        assert resp.status_code == 404


def test_chat_returns_reply():
    app, fake = _make_app()
    with TestClient(app) as client:
        resp = client.post("/api/v1/agents/manager/chat", json={"message": "库存怎么样"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["agent"] == "manager"
        assert "milk" in body["reply"]
        assert any(r.url.path == "/api/v1/inventory" for r in fake.requests)


def test_web_index_and_pages():
    app, _ = _make_app()
    with TestClient(app) as client:
        assert client.get("/").status_code == 200
        assert client.get("/consumer").status_code == 200
        assert client.get("/kitchen").status_code == 200
        assert client.get("/manager").status_code == 200
        assert client.get("/static/app.js").status_code == 200
        assert client.get("/static/style.css").status_code == 200
        # Each agent page points its chat UI at the right agent.
        assert b'data-agent="consumer"' in client.get("/consumer").content
        assert b'data-agent="kitchen"' in client.get("/kitchen").content
        assert b'data-agent="manager"' in client.get("/manager").content
