import json
from collections import defaultdict
from uuid import UUID

from fastapi import WebSocket


class WebSocketManager:
    def __init__(self) -> None:
        self._connections: dict[UUID, set[WebSocket]] = defaultdict(set)

    async def connect(self, workflow_id: UUID, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections[workflow_id].add(websocket)

    def disconnect(self, workflow_id: UUID, websocket: WebSocket) -> None:
        self._connections[workflow_id].discard(websocket)
        if not self._connections[workflow_id]:
            self._connections.pop(workflow_id, None)

    async def publish(self, workflow_id: UUID, payload: dict) -> None:
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
