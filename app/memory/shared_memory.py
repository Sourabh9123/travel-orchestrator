import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from uuid import UUID

from app.core.exceptions import ValidationFailure

if TYPE_CHECKING:
    from redis.asyncio import Redis
else:
    Redis = Any


@dataclass(frozen=True, slots=True)
class MemorySnapshot:
    workflow_id: UUID
    version: int
    state: dict[str, Any]


class SharedMemory:
    def __init__(self, redis: Redis, ttl_seconds: int) -> None:
        self.redis = redis
        self.ttl_seconds = ttl_seconds

    def _state_key(self, workflow_id: UUID) -> str:
        return f"travel:workflow:{workflow_id}:state"

    def _version_key(self, workflow_id: UUID) -> str:
        return f"travel:workflow:{workflow_id}:version"

    async def initialize(self, workflow_id: UUID, state: dict[str, Any]) -> MemorySnapshot:
        key = self._state_key(workflow_id)
        version_key = self._version_key(workflow_id)
        payload = json.dumps(state, default=str)
        async with self.redis.pipeline(transaction=True) as pipe:
            pipe.set(key, payload, ex=self.ttl_seconds)
            pipe.set(version_key, 1, ex=self.ttl_seconds)
            await pipe.execute()
        return MemorySnapshot(workflow_id=workflow_id, version=1, state=state)

    async def get(self, workflow_id: UUID) -> MemorySnapshot:
        raw, version = await self.redis.mget(self._state_key(workflow_id), self._version_key(workflow_id))
        if raw is None:
            raise ValidationFailure("Workflow state was not found", code="memory_not_found")
        return MemorySnapshot(
            workflow_id=workflow_id,
            version=int(version or 1),
            state=json.loads(raw),
        )

    async def update(
        self,
        workflow_id: UUID,
        patch: dict[str, Any],
        expected_version: int | None = None,
    ) -> MemorySnapshot:
        key = self._state_key(workflow_id)
        version_key = self._version_key(workflow_id)
        async with self.redis.lock(f"{key}:lock", timeout=10):
            snapshot = await self.get(workflow_id)
            if expected_version is not None and snapshot.version != expected_version:
                raise ValidationFailure("Memory version conflict", code="memory_version_conflict")
            state = _deep_merge(snapshot.state, patch)
            version = snapshot.version + 1
            async with self.redis.pipeline(transaction=True) as pipe:
                pipe.set(key, json.dumps(state, default=str), ex=self.ttl_seconds)
                pipe.set(version_key, version, ex=self.ttl_seconds)
                await pipe.execute()
            return MemorySnapshot(workflow_id=workflow_id, version=version, state=state)


def _deep_merge(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    merged = dict(left)
    for key, value in right.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged
