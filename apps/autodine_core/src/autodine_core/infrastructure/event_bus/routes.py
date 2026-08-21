from __future__ import annotations

import asyncio
from queue import Empty

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from autodine_core.infrastructure.event_bus.publisher import WebSocketConnectionManager


router = APIRouter()


@router.websocket("/ws/stores/{store_id}")
async def store_events(websocket: WebSocket, store_id: str) -> None:
    manager: WebSocketConnectionManager = websocket.app.state.websocket_manager
    await websocket.accept()
    subscription = manager.subscribe(store_id)
    disconnect_waiter = asyncio.ensure_future(websocket.receive())
    try:
        while True:
            if disconnect_waiter.done():
                break
            try:
                await websocket.send_json(subscription.get_nowait())
            except Empty:
                await asyncio.sleep(0.01)
    except WebSocketDisconnect:
        pass
    finally:
        disconnect_waiter.cancel()
        manager.unsubscribe(store_id, subscription)
