from __future__ import annotations

import httpx
import pytest

from agent_hub.core_client import CoreClient
from agent_hub.errors import CoreAPIError


def _envelope(data):
    return {"code": 0, "message": "success", "request_id": "r", "timestamp": "t", "data": data}


def test_request_returns_data_field():
    transport = httpx.MockTransport(lambda req: httpx.Response(200, json=_envelope({"ok": True})))
    client = CoreClient("http://core", transport=transport)
    assert client.request("GET", "/api/v1/inventory") == {"ok": True}


def test_request_raises_core_api_error_on_non_2xx():
    transport = httpx.MockTransport(
        lambda req: httpx.Response(
            409,
            json={"code": 4091, "message": "insufficient inventory", "request_id": "r", "timestamp": "t", "data": {}},
        )
    )
    client = CoreClient("http://core", transport=transport)
    with pytest.raises(CoreAPIError) as exc:
        client.request("POST", "/api/v1/orders", json={})
    assert exc.value.status_code == 409
    assert exc.value.code == 4091
    assert "insufficient" in exc.value.message


def test_request_passes_query_and_json():
    seen = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["params"] = req.url.params
        seen["body"] = req.content
        return httpx.Response(200, json=_envelope({}))

    client = CoreClient("http://core", transport=httpx.MockTransport(handler))
    client.request("POST", "/api/v1/orders", params={"store_id": "store-main"}, json={"x": 1})
    assert seen["params"]["store_id"] == "store-main"
    assert b'"x"' in seen["body"]
