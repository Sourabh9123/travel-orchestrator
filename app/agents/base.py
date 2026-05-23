import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from app.core.exceptions import AgentExecutionError, AppError
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
    """Runtime dependencies passed into every agent execution."""

    workflow_id: str
    user_id: str | None
    memory: SharedMemory
    tools: ToolRegistry


class BaseAgent(ABC):
    """Base interface for single-responsibility travel agents."""

    name: str
    description: str
    system_prompt: str

    async def run(self, state: dict[str, Any], context: AgentContext) -> AgentOutput:
        """Execute an agent with latency logging and named error handling."""

        start = time.perf_counter()
        try:
            output = await self._run(state, context)
            latency_ms = int((time.perf_counter() - start) * 1000)
            logger.info("agent.executed", agent=self.name, latency_ms=latency_ms)
            return output
        except AppError:
            raise
        except Exception as exc:
            raise AgentExecutionError(
                f"Agent {self.name} failed",
                details={"agent": self.name, "error": str(exc)},
            ) from exc

    @abstractmethod
    async def _run(self, state: dict[str, Any], context: AgentContext) -> AgentOutput:
        """Implement agent-specific behavior in subclasses."""

        raise NotImplementedError

    def metadata(self) -> dict[str, str]:
        """Return operator-facing metadata for planning, audits, and prompt inspection."""

        return {
            "name": self.name,
            "description": self.description,
            "system_prompt": self.system_prompt,
        }
