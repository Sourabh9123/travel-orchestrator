from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class WorkflowNode:
    """Single executable node in a workflow DAG."""

    name: str
    agent_name: str
    depends_on: set[str] = field(default_factory=set)
    timeout_seconds: int | None = None
    max_retries: int = 1


@dataclass(frozen=True, slots=True)
class WorkflowGraph:
    """Dependency graph used by the workflow engine."""

    nodes: dict[str, WorkflowNode]

    def ready_nodes(self, completed: set[str], running: set[str], failed: set[str]) -> list[WorkflowNode]:
        """Return nodes whose dependencies are complete and are not active."""

        return [
            node
            for node in self.nodes.values()
            if node.name not in completed
            and node.name not in running
            and node.name not in failed
            and node.depends_on.issubset(completed)
        ]

    def to_dict(self) -> dict[str, dict]:
        """Serialize the graph for logging and persistence."""

        return {
            name: {
                "agent_name": node.agent_name,
                "depends_on": sorted(node.depends_on),
                "timeout_seconds": node.timeout_seconds,
                "max_retries": node.max_retries,
            }
            for name, node in self.nodes.items()
        }
