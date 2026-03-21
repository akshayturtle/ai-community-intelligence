"""WebSocket route for real-time dashboard updates via Redis pub/sub."""

import asyncio
import json

import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from config.settings import REDIS_URL

router = APIRouter()
logger = structlog.get_logger()

# Connected WebSocket clients
_clients: set[WebSocket] = set()


async def broadcast(message: dict):
    """Broadcast a message to all connected WebSocket clients."""
    if not _clients:
        return
    data = json.dumps(message, default=str)
    disconnected = set()
    for ws in _clients:
        try:
            await ws.send_text(data)
        except Exception:
            disconnected.add(ws)
    _clients -= disconnected


async def _redis_subscriber():
    """Subscribe to Redis pub/sub channel and broadcast to WebSocket clients."""
    try:
        import redis.asyncio as aioredis
        r = aioredis.from_url(REDIS_URL)
        pubsub = r.pubsub()
        await pubsub.subscribe("cmm:events")
        logger.info("redis_pubsub_connected")

        async for message in pubsub.listen():
            if message["type"] == "message":
                try:
                    data = json.loads(message["data"])
                    await broadcast(data)
                except Exception as e:
                    logger.warning("pubsub_broadcast_error", error=str(e))
    except Exception as e:
        logger.warning("redis_pubsub_unavailable", error=str(e))


# Utility: publish an event from anywhere in the app
async def publish_event(event_type: str, payload: dict):
    """Publish an event to Redis pub/sub for WebSocket broadcast."""
    try:
        import redis.asyncio as aioredis
        r = aioredis.from_url(REDIS_URL)
        message = {"type": event_type, "data": payload}
        await r.publish("cmm:events", json.dumps(message, default=str))
        await r.aclose()
    except Exception as e:
        logger.warning("redis_publish_failed", error=str(e))


@router.websocket("/dashboard")
async def websocket_dashboard(ws: WebSocket):
    """WebSocket endpoint for real-time dashboard updates."""
    await ws.accept()
    _clients.add(ws)
    logger.info("ws_client_connected", total=len(_clients))

    try:
        # Send initial connection message
        await ws.send_text(json.dumps({"type": "connected", "data": {"message": "Connected to CMM dashboard"}}))

        # Keep connection alive
        while True:
            try:
                # Wait for client messages (ping/pong or commands)
                data = await asyncio.wait_for(ws.receive_text(), timeout=30)
                if data == "ping":
                    await ws.send_text(json.dumps({"type": "pong"}))
            except asyncio.TimeoutError:
                # Send heartbeat
                await ws.send_text(json.dumps({"type": "heartbeat"}))
    except WebSocketDisconnect:
        pass
    finally:
        _clients.discard(ws)
        logger.info("ws_client_disconnected", total=len(_clients))
