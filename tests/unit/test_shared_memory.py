import asyncio
from uuid import uuid4

from app.memory.shared_memory import SharedMemory


class FakePipeline:
    def __init__(self, redis):
        self.redis = redis
        self.commands = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    def set(self, key, value, ex=None):
        self.commands.append((key, value))

    async def execute(self):
        for key, value in self.commands:
            self.redis.store[key] = value


class FakeLock:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None


class FakeRedis:
    def __init__(self):
        self.store = {}

    def pipeline(self, transaction=True):
        return FakePipeline(self)

    async def mget(self, *keys):
        return [self.store.get(key) for key in keys]

    def lock(self, name, timeout=10):
        return FakeLock()


def test_shared_memory_versioned_deep_merge() -> None:
    asyncio.run(_run_shared_memory_versioned_deep_merge())


async def _run_shared_memory_versioned_deep_merge() -> None:
    workflow_id = uuid4()
    memory = SharedMemory(FakeRedis(), ttl_seconds=60)

    await memory.initialize(workflow_id, {"a": {"b": 1}})
    snapshot = await memory.update(workflow_id, {"a": {"c": 2}}, expected_version=1)

    assert snapshot.version == 2
    assert snapshot.state == {"a": {"b": 1, "c": 2}}
