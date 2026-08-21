from __future__ import annotations

from abc import ABC, abstractmethod
from queue import Queue
from threading import Lock
from typing import Any, Dict, List


class EventPublisher(ABC):
    @abstractmethod
    def publish(self, event: Dict[str, Any]) -> None:
        raise NotImplementedError


class NullEventPublisher(EventPublisher):
    def publish(self, event: Dict[str, Any]) -> None:
        return None


class WebSocketConnectionManager:
    """Thread-safe store-scoped subscriptions used by the ASGI WebSocket route."""

    def __init__(self) -> None:
        self._connections: Dict[str, List[Queue[Dict[str, Any]]]] = {}
        self._lock = Lock()

    def subscribe(self, store_id: str) -> Queue[Dict[str, Any]]:
        subscription: Queue[Dict[str, Any]] = Queue()
        with self._lock:
            self._connections.setdefault(store_id, []).append(subscription)
        return subscription

    def unsubscribe(self, store_id: str, subscription: Queue[Dict[str, Any]]) -> None:
        with self._lock:
            subscribers = self._connections.get(store_id, [])
            if subscription in subscribers:
                subscribers.remove(subscription)
            if not subscribers:
                self._connections.pop(store_id, None)

    def publish(self, event: Dict[str, Any]) -> None:
        store_id = event.get("store_id")
        if not isinstance(store_id, str):
            return
        with self._lock:
            subscribers = list(self._connections.get(store_id, []))
        for subscription in subscribers:
            subscription.put(event)


class InMemoryEventPublisher(EventPublisher):
    def __init__(self, manager: WebSocketConnectionManager) -> None:
        self._manager = manager

    def publish(self, event: Dict[str, Any]) -> None:
        self._manager.publish(event)
