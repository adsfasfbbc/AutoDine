"""Shared test helpers for the agent hub test suite."""

from __future__ import annotations

import httpx

from agent_hub.core_client import CoreClient


def make_transport(responses, requests=None):
    """Build an ``httpx.MockTransport`` serving canned Core envelopes.

    ``responses`` maps ``(method, path)`` to either a static ``data`` payload or
    a callable ``request -> data``. Every request is appended to ``requests``.
    """
    captured = requests if requests is not None else []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        key = (request.method, request.url.path)
        value = responses.get(key, {})
        data = value(request) if callable(value) else value
        return httpx.Response(
            200,
            json={"code": 0, "message": "success", "request_id": "req", "timestamp": "t", "data": data},
        )

    return httpx.MockTransport(handler), captured


def make_client(responses, requests=None):
    """Build a ``CoreClient`` backed by a canned mock transport."""
    transport, captured = make_transport(responses, requests)
    return CoreClient("http://core", transport=transport), captured


class FakeCore:
    """In-memory fake of the Core REST API for deterministic agent tests."""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self.menu = [
            {"product_id": "latte", "name": "Latte", "price": "18.50", "status": "ON_SALE", "available_product_quantity": 50},
            {"product_id": "americano", "name": "Americano", "price": "12.00", "status": "ON_SALE", "available_product_quantity": 100},
        ]
        self.inventory = [
            {
                "ingredient_id": "milk",
                "location_id": "bar",
                "physical_quantity": "12000",
                "defective_quantity": "0",
                "reserved_quantity": "0",
                "reorder_threshold": "0",
                "available_quantity": "12000",
            }
        ]

    def handle(self, request: httpx.Request):
        self.requests.append(request)
        method = request.method
        path = request.url.path

        if method == "GET" and path == "/api/v1/menu":
            return self.menu
        if method == "GET" and path == "/api/v1/inventory":
            return self.inventory
        if method == "GET" and path == "/api/v1/alarms":
            return {"items": []}
        if method == "GET" and path.endswith("/queues/store-main"):
            return {"items": [{"zone_id": "bar", "waiting_count": 3, "estimated_wait_seconds": 60}]}
        if method == "GET" and path == "/api/v1/analytics/summary":
            return {
                "window": {"start": "s", "end": "e"},
                "metrics": {
                    "order_count": 5,
                    "production_task_count": 4,
                    "inventory_location_count": 25,
                    "open_alarm_count": 1,
                },
                "definitions": {},
            }
        if method == "POST" and path == "/api/v1/orders":
            return self._order("order-1234")
        if method == "GET" and path.startswith("/api/v1/orders/"):
            return self._order(path.rsplit("/", 1)[-1])
        if method == "POST" and path.endswith("/cancel"):
            return self._order(path.split("/")[-2])
        if method == "POST" and "/production/tasks/" in path and path.endswith("/start"):
            return {"task_id": "task-1234", "order_id": "order-1234", "status": "PRODUCING", "order_status": "PRODUCING", "pick_list": []}
        if method == "POST" and "/production/tasks/" in path and path.endswith("/ready"):
            return {"task_id": "task-1234", "order_id": "order-1234", "status": "READY", "order_status": "READY", "pick_list": []}
        if method == "POST" and "/production/tasks/" in path and path.endswith("/complete"):
            return {"task_id": "task-1234", "order_id": "order-1234", "status": "COMPLETED", "order_status": "COMPLETED", "pick_list": []}
        return {}

    @staticmethod
    def _order(order_id: str) -> dict:
        return {
            "order_id": order_id,
            "store_id": "store-main",
            "status": "CONFIRMED",
            "total_amount": "18.50",
            "items": [{"product_id": "latte", "quantity": 1, "unit_price": "18.50"}],
            "task": {
                "task_id": "task-1234",
                "order_id": order_id,
                "status": "PENDING",
                "pick_list": [{"ingredient_id": "milk", "quantity": "220", "unit": "ml"}],
            },
        }

    def transport(self) -> httpx.MockTransport:
        def handler(request: httpx.Request) -> httpx.Response:
            data = self.handle(request)
            return httpx.Response(
                200,
                json={"code": 0, "message": "success", "request_id": "r", "timestamp": "t", "data": data},
            )

        return httpx.MockTransport(handler)

    def client(self) -> CoreClient:
        return CoreClient("http://core", transport=self.transport())
