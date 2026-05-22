import json
from collections import defaultdict
from uuid import UUID

from fastapi import WebSocket


class WebSocketManager:
    """Tracks active WebSocket clients by workflow id."""

    def __init__(self) -> None:
        """Create an empty connection registry."""

        self._connections: dict[UUID, set[WebSocket]] = defaultdict(set)

    async def connect(self, workflow_id: UUID, websocket: WebSocket) -> None:
        """Accept and register a WebSocket for a workflow."""

        await websocket.accept()
        self._connections[workflow_id].add(websocket)

    def disconnect(self, workflow_id: UUID, websocket: WebSocket) -> None:
        """Remove a WebSocket from a workflow subscription."""

        self._connections[workflow_id].discard(websocket)
        if not self._connections[workflow_id]:
            self._connections.pop(workflow_id, None)

    async def publish(self, workflow_id: UUID, payload: dict) -> None:
        """Broadcast a JSON-serializable event payload to workflow subscribers."""

        message = json.dumps(payload, default=str)
        stale: list[WebSocket] = []
        for websocket in self._connections.get(workflow_id, set()):
            try:
                await websocket.send_text(message)
            except RuntimeError:
                stale.append(websocket)
        for websocket in stale:
            self.disconnect(workflow_id, websocket)


websocket_manager = WebSocketManager()
