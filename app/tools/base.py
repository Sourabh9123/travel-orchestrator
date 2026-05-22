import asyncio
import hashlib
import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

try:
    from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential
except ImportError:  # pragma: no cover - fallback for dependency-light test environments
    AsyncRetrying = None  # type: ignore[assignment]
    retry_if_exception_type = None  # type: ignore[assignment]
    stop_after_attempt = None  # type: ignore[assignment]
    wait_exponential = None  # type: ignore[assignment]

from app.core.exceptions import ToolExecutionError
from app.core.logging import get_logger

if TYPE_CHECKING:
    from redis.asyncio import Redis
else:
    Redis = Any

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class ToolContext:
    workflow_id: str
    user_id: str | None = None
    correlation_id: str | None = None


class BaseTool(ABC):
    name: str
    description: str

    def __init__(
        self,
        redis: Redis | None = None,
        timeout_seconds: int = 20,
        cache_ttl_seconds: int = 900,
        max_retries: int = 2,
        max_calls_per_minute: int = 120,
    ) -> None:
        self.redis = redis
        self.timeout_seconds = timeout_seconds
        self.cache_ttl_seconds = cache_ttl_seconds
        self.max_retries = max_retries
        self.max_calls_per_minute = max_calls_per_minute

    async def execute(self, payload: dict[str, Any], context: ToolContext) -> dict[str, Any]:
        await self._enforce_rate_limit(context)
        cache_key = self._cache_key(payload)
        if self.redis is not None:
            cached = await self.redis.get(cache_key)
            if cached:
                return json.loads(cached)

        start = time.perf_counter()
        try:
            if AsyncRetrying is None:
                result = await self._execute_with_simple_retries(payload, context)
            else:
                async for attempt in AsyncRetrying(
                    stop=stop_after_attempt(self.max_retries + 1),
                    wait=wait_exponential(multiplier=0.2, min=0.2, max=2),
                    retry=retry_if_exception_type((TimeoutError, ToolExecutionError)),
                    reraise=True,
                ):
                    with attempt:
                        result = await asyncio.wait_for(
                            self._execute(payload, context), timeout=self.timeout_seconds
                        )
        except Exception as exc:
            raise ToolExecutionError(
                f"Tool {self.name} failed", code="tool_failed", details={"tool": self.name}
            ) from exc

        latency_ms = int((time.perf_counter() - start) * 1000)
        logger.info("tool.executed", tool=self.name, latency_ms=latency_ms)
        if self.redis is not None:
            await self.redis.set(cache_key, json.dumps(result, default=str), ex=self.cache_ttl_seconds)
        return result

    @abstractmethod
    async def _execute(self, payload: dict[str, Any], context: ToolContext) -> dict[str, Any]:
        raise NotImplementedError

    async def _execute_with_simple_retries(
        self, payload: dict[str, Any], context: ToolContext
    ) -> dict[str, Any]:
        last_error: Exception | None = None
        for _ in range(self.max_retries + 1):
            try:
                return await asyncio.wait_for(self._execute(payload, context), timeout=self.timeout_seconds)
            except (TimeoutError, ToolExecutionError) as exc:
                last_error = exc
                await asyncio.sleep(0.2)
        raise last_error or ToolExecutionError(f"Tool {self.name} failed")

    def _cache_key(self, payload: dict[str, Any]) -> str:
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()
        return f"travel:tool:{self.name}:{digest}"

    async def _enforce_rate_limit(self, context: ToolContext) -> None:
        if self.redis is None:
            return
        identity = context.user_id or "anonymous"
        key = f"travel:rate:{self.name}:{identity}"
        count = await self.redis.incr(key)
        if count == 1:
            await self.redis.expire(key, 60)
        if count > self.max_calls_per_minute:
            raise ToolExecutionError(
                f"Tool {self.name} rate limit exceeded",
                code="tool_rate_limited",
                details={"tool": self.name, "limit": self.max_calls_per_minute},
            )
