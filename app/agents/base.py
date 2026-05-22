import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from app.core.logging import get_logger
from app.schemas.travel import AgentOutput

if TYPE_CHECKING:
    from app.memory.shared_memory import SharedMemory
    from app.tools.registry import ToolRegistry
else:
    SharedMemory = Any
    ToolRegistry = Any

logger = get_logger(__name__)


@dataclass(slots=True)
class AgentContext:
    workflow_id: str
    user_id: str | None
    memory: SharedMemory
    tools: ToolRegistry


class BaseAgent(ABC):
    name: str
    description: str

    async def run(self, state: dict[str, Any], context: AgentContext) -> AgentOutput:
        start = time.perf_counter()
        output = await self._run(state, context)
        latency_ms = int((time.perf_counter() - start) * 1000)
        logger.info("agent.executed", agent=self.name, latency_ms=latency_ms)
        return output

    @abstractmethod
    async def _run(self, state: dict[str, Any], context: AgentContext) -> AgentOutput:
        raise NotImplementedError
