from app.orchestration.graph import WorkflowGraph, WorkflowNode


def test_ready_nodes_respects_dependencies() -> None:
    graph = WorkflowGraph(
        nodes={
            "a": WorkflowNode("a", "agent_a"),
            "b": WorkflowNode("b", "agent_b", depends_on={"a"}),
        }
    )

    assert [node.name for node in graph.ready_nodes(set(), set(), set())] == ["a"]
    assert [node.name for node in graph.ready_nodes({"a"}, set(), set())] == ["b"]
