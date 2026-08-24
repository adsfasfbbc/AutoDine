from __future__ import annotations

import json


def _last_paths(fake_core):
    return [r.url.path for r in fake_core.requests]


def test_recommend_menu(hub, fake_core):
    reply = hub.run("consumer", "推荐一杯含奶饮品")
    assert "Latte" in reply
    assert "/api/v1/menu" in _last_paths(fake_core)


def test_order_flow(hub, fake_core):
    reply = hub.run("consumer", "点一杯美式")
    order_req = next(r for r in fake_core.requests if r.method == "POST" and r.url.path == "/api/v1/orders")
    body = json.loads(order_req.content)
    assert body["items"] == [{"product_id": "americano", "quantity": 1}]
    assert "订单" in reply


def test_inventory_query(hub, fake_core):
    reply = hub.run("manager", "库存怎么样")
    assert "/api/v1/inventory" in _last_paths(fake_core)
    assert "milk" in reply


def test_alarm_query(hub, fake_core):
    reply = hub.run("manager", "有哪些质量告警")
    assert "/api/v1/alarms" in _last_paths(fake_core)
    assert "告警" in reply


def test_operations_summary(hub, fake_core):
    reply = hub.run("manager", "今天的运营总结")
    summary_req = next(r for r in fake_core.requests if r.url.path == "/api/v1/analytics/summary")
    assert "start" in summary_req.url.params
    assert "订单数" in reply


def test_production_view_pick_list(hub, fake_core):
    reply = hub.run("kitchen", "查看订单 deadbeef12345678 的领料清单")
    assert any(p == "/api/v1/orders/deadbeef12345678" for p in _last_paths(fake_core))
    assert "milk" in reply


def test_complete_production_flow(hub, fake_core):
    reply = hub.run("kitchen", "完成订单 deadbeef12345678 的生产")
    paths = _last_paths(fake_core)
    assert "/api/v1/orders/deadbeef12345678" in paths
    complete = next(r for r in fake_core.requests if r.method == "POST" and r.url.path.endswith("/complete"))
    body = json.loads(complete.content)
    assert body["actual_consumption"] == [{"ingredient_id": "milk", "location_id": "bar", "quantity": "220"}]
    assert "完成生产" in reply


def test_start_production(hub, fake_core):
    reply = hub.run("kitchen", "开始制作 deadbeef12345678")
    assert any(p.endswith("/start") for p in _last_paths(fake_core))
    assert "开始生产" in reply


def test_unknown_intent(hub):
    reply = hub.run("consumer", "帮我写一首诗")
    assert "抱歉" in reply


def test_core_down_gives_friendly_error(settings):
    import httpx

    from agent_hub.core_client import CoreClient
    from agent_hub.hub import AgentHub

    def handler(req):
        raise httpx.ConnectError("connection refused")

    client = CoreClient("http://core", transport=httpx.MockTransport(handler))
    hub = AgentHub(settings, client=client)
    reply = hub.run("manager", "库存怎么样")
    assert "失败" in reply
    assert "AutoDineCore" in reply
    assert "{'error'" not in reply
