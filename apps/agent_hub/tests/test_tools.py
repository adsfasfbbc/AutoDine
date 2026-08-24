from __future__ import annotations

import json

import httpx

from agent_hub.core_client import CoreClient
from agent_hub.errors import CoreAPIError
from agent_hub.tools import alarm, analytics, device, inventory, menu, order, production, queue
from agent_hub.tools import execute_tool

from .helpers import make_client


def test_list_menu_hits_endpoint(settings):
    requests = []
    client, _ = make_client({("GET", "/api/v1/menu"): [{"name": "Latte"}]}, requests)
    assert menu.list_menu(client, settings) == [{"name": "Latte"}]
    assert requests[0].url.path == "/api/v1/menu"
    assert requests[0].url.params["store_id"] == "store-main"


def test_get_menu_item(settings):
    requests = []
    client, _ = make_client({("GET", "/api/v1/menu/latte"): {"name": "Latte"}}, requests)
    assert menu.get_menu_item(client, settings, product_id="latte") == {"name": "Latte"}
    assert requests[0].url.path == "/api/v1/menu/latte"


def test_create_order_generates_idempotency_key(settings):
    requests = []
    client, _ = make_client({("POST", "/api/v1/orders"): {"order_id": "abc"}}, requests)
    data = order.create_order(client, settings, items=[{"product_id": "latte", "quantity": 1}])
    assert data == {"order_id": "abc"}
    body = json.loads(requests[0].content)
    assert body["store_id"] == "store-main"
    assert body["idempotency_key"]
    assert body["items"] == [{"product_id": "latte", "quantity": 1}]


def test_create_order_respects_explicit_key(settings):
    requests = []
    client, _ = make_client({("POST", "/api/v1/orders"): {}}, requests)
    order.create_order(client, settings, items=[{"product_id": "latte", "quantity": 2}], idempotency_key="k1")
    assert json.loads(requests[0].content)["idempotency_key"] == "k1"


def test_get_and_cancel_order(settings):
    requests = []
    client, _ = make_client(
        {
            ("GET", "/api/v1/orders/o1"): {"order_id": "o1"},
            ("POST", "/api/v1/orders/o1/cancel"): {"order_id": "o1", "status": "CANCELED"},
        },
        requests,
    )
    assert order.get_order(client, settings, order_id="o1") == {"order_id": "o1"}
    assert order.cancel_order(client, settings, order_id="o1")["status"] == "CANCELED"
    assert [r.url.path for r in requests] == ["/api/v1/orders/o1", "/api/v1/orders/o1/cancel"]


def test_production_transitions(settings):
    requests = []
    client, _ = make_client(
        {
            ("POST", "/api/v1/production/tasks/t1/start"): {"status": "PRODUCING"},
            ("POST", "/api/v1/production/tasks/t1/ready"): {"status": "READY"},
            ("POST", "/api/v1/production/tasks/t1/complete"): {"status": "COMPLETED"},
        },
        requests,
    )
    assert production.start_production_task(client, settings, task_id="t1")["status"] == "PRODUCING"
    assert production.ready_production_task(client, settings, task_id="t1")["status"] == "READY"
    result = production.complete_production_task(
        client, settings, task_id="t1",
        actual_consumption=[{"ingredient_id": "milk", "location_id": "bar", "quantity": "220"}],
    )
    assert result["status"] == "COMPLETED"
    body = json.loads(requests[2].content)
    assert body["actual_consumption"] == [{"ingredient_id": "milk", "location_id": "bar", "quantity": "220"}]


def test_inventory_alarm_queue(settings):
    requests = []
    client, _ = make_client(
        {
            ("GET", "/api/v1/inventory"): [{"ingredient_id": "milk"}],
            ("GET", "/api/v1/alarms"): {"items": []},
            ("GET", "/api/v1/queues/store-main"): {"items": []},
        },
        requests,
    )
    assert inventory.list_inventory(client, settings) == [{"ingredient_id": "milk"}]
    assert alarm.list_alarms(client, settings) == {"items": []}
    assert requests[1].url.params["store_id"] == "store-main"
    assert queue.list_queue_snapshots(client, settings) == {"items": []}


def test_analytics_defaults_window(settings):
    requests = []
    client, _ = make_client({("GET", "/api/v1/analytics/summary"): {"metrics": {}}}, requests)
    analytics.get_analytics_summary(client, settings)
    params = requests[0].url.params
    assert params["store_id"] == "store-main"
    assert "start" in params and "end" in params


def test_device_commands(settings):
    requests = []
    client, _ = make_client(
        {
            ("POST", "/api/v1/devices/fridge-1/commands"): {"status": "PENDING"},
            ("GET", "/api/v1/devices/fridge-1/commands"): {"items": []},
        },
        requests,
    )
    device.issue_device_command(client, settings, device_id="fridge-1", command_type="set_temp", parameters={"celsius": 4})
    body = json.loads(requests[0].content)
    assert body["store_id"] == "store-main"
    assert body["command_type"] == "set_temp"
    assert device.list_device_commands(client, settings, device_id="fridge-1") == {"items": []}


def test_execute_tool_serializes_json(settings):
    client, _ = make_client({("GET", "/api/v1/inventory"): [{"ingredient_id": "milk"}]})
    result = execute_tool("list_inventory", client, settings, {})
    assert json.loads(result) == [{"ingredient_id": "milk"}]


def test_execute_tool_unknown_tool(settings):
    client, _ = make_client({})
    result = execute_tool("nope", client, settings, {})
    assert "error" in json.loads(result)


def test_execute_tool_surfaces_core_error(settings):
    def handler(req):
        return httpx.Response(409, json={"code": 4092, "message": "product unavailable", "data": {}})

    client = CoreClient("http://core", transport=httpx.MockTransport(handler))
    result = execute_tool("create_order", client, settings, {"items": [{"product_id": "x", "quantity": 1}]})
    parsed = json.loads(result)
    assert parsed["code"] == 4092
