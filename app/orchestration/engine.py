import asyncio
from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID

from app.agents.base import AgentContext, BaseAgent
from app.core.exceptions import WorkflowExecutionError
from app.core.logging import get_logger
from app.memory.shared_memory import SharedMemory
from app.orchestration.events import WorkflowEvent, WorkflowEventType
from app.orchestration.graph import WorkflowGraph, WorkflowNode
from app.tools.registry import ToolRegistry

logger = get_logger(__name__)
EventHook = Callable[[WorkflowEvent], Awaitable[None]]


class WorkflowEngine:
    """Dependency-aware async DAG executor for agent workflows."""

    def __init__(
        self,
        agents: dict[str, BaseAgent],
        memory: SharedMemory,
        tools: ToolRegistry,
        event_hooks: list[EventHook] | None = None,
        default_timeout_seconds: int = 60,
    ) -> None:
        """Create a workflow engine with injected agents, memory, tools, and hooks."""

        self.agents = agents
        self.memory = memory
        self.tools = tools
        self.event_hooks = event_hooks or []
        self.default_timeout_seconds = default_timeout_seconds

    async def execute(
        self,
        workflow_id: UUID,
        graph: WorkflowGraph,
        initial_state: dict[str, Any],
        user_id: str | None = None,
    ) -> dict[str, Any]:
        """Execute a graph to completion and return the final shared state."""

        await self.memory.initialize(
            workflow_id,
            {
                **initial_state,
                "workflow": {"status": "running", "completed_nodes": [], "failed_nodes": []},
            },
        )
        await self._emit(
            workflow_id, WorkflowEventType.WORKFLOW_STARTED, payload={"graph": graph.to_dict()}
        )

        completed: set[str] = set()
        failed: set[str] = set()
        running: set[str] = set()
        while len(completed) + len(failed) < len(graph.nodes):
            ready = graph.ready_nodes(completed, running, failed)
            if not ready:
                if running:
                    await asyncio.sleep(0.05)
                    continue
                raise WorkflowExecutionError(
                    "Workflow graph cannot make progress",
                    code="workflow_deadlock",
                    details={"completed": sorted(completed), "failed": sorted(failed)},
                )
            running.update(node.name for node in ready)
            results = await asyncio.gather(
                *(self._run_node(workflow_id, node, user_id) for node in ready),
                return_exceptions=True,
            )
            for node, result in zip(ready, results, strict=True):
                running.remove(node.name)
                if isinstance(result, Exception):
                    failed.add(node.name)
                    await self._emit(
                        workflow_id,
                        WorkflowEventType.NODE_FAILED,
                        node.name,
                        {"error": str(result)},
                    )
                    raise WorkflowExecutionError(
                        f"Workflow node {node.name} failed",
                        code="node_failed",
                        details={"node": node.name},
                    ) from result
                completed.add(node.name)

        snapshot = await self.memory.update(
            workflow_id,
            {"workflow": {"status": "completed", "completed_nodes": sorted(completed)}},
        )
        await self._emit(workflow_id, WorkflowEventType.WORKFLOW_COMPLETED)
        return snapshot.state

    async def _run_node(self, workflow_id: UUID, node: WorkflowNode, user_id: str | None) -> None:
        """Run one workflow node with retries and memory updates."""

        agent = self.agents[node.agent_name]
        await self._emit(workflow_id, WorkflowEventType.NODE_STARTED, node.name)
        last_error: Exception | None = None
        for attempt in range(1, node.max_retries + 2):
            try:
                snapshot = await self.memory.get(workflow_id)
                context = AgentContext(
                    workflow_id=str(workflow_id),
                    user_id=user_id,
                    memory=self.memory,
                    tools=self.tools,
                )
                output = await asyncio.wait_for(
                    agent.run(snapshot.state, context),
                    timeout=node.timeout_seconds or self.default_timeout_seconds,
                )
                await self.memory.update(
                    workflow_id,
                    {
                        **output.data,
                        "agent_outputs": {agent.name: output.model_dump(mode="json")},
                        "workflow": {"last_completed_node": node.name},
                    },
                )
                await self._emit(
                    workflow_id,
                    WorkflowEventType.NODE_COMPLETED,
                    node.name,
                    {"agent": agent.name, "attempt": attempt},
                )
                return
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "workflow.node_retry", node=node.name, attempt=attempt, error=str(exc)
                )
        raise last_error or WorkflowExecutionError(f"Workflow node {node.name} failed")

    async def _emit(
        self,
        workflow_id: UUID,
        event_type: WorkflowEventType,
        node_name: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        """Emit workflow events to structured logs and registered hooks."""

        event = WorkflowEvent(
            workflow_id=workflow_id,
            event_type=event_type,
            node_name=node_name,
            payload=payload or {},
        )
        logger.info("workflow.event", **event.model_dump(mode="json"))
        for hook in self.event_hooks:
            await hook(event)
