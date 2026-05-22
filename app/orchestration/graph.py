from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class WorkflowNode:
    name: str
    agent_name: str
    depends_on: set[str] = field(default_factory=set)
    timeout_seconds: int | None = None
    max_retries: int = 1


@dataclass(frozen=True, slots=True)
class WorkflowGraph:
    nodes: dict[str, WorkflowNode]

    def ready_nodes(self, completed: set[str], running: set[str], failed: set[str]) -> list[WorkflowNode]:
        return [
            node
            for node in self.nodes.values()
            if node.name not in completed
            and node.name not in running
            and node.name not in failed
            and node.depends_on.issubset(completed)
        ]

    def to_dict(self) -> dict[str, dict]:
        return {
            name: {
                "agent_name": node.agent_name,
                "depends_on": sorted(node.depends_on),
                "timeout_seconds": node.timeout_seconds,
                "max_retries": node.max_retries,
            }
            for name, node in self.nodes.items()
        }
