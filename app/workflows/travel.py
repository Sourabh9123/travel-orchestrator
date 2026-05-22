from app.orchestration.graph import WorkflowGraph, WorkflowNode


def build_travel_planning_graph(timeout_seconds: int) -> WorkflowGraph:
    nodes = [
        WorkflowNode("supervise", "supervisor", timeout_seconds=timeout_seconds),
        WorkflowNode(
            "requirements",
            "requirement_analysis",
            depends_on={"supervise"},
            timeout_seconds=timeout_seconds,
        ),
        WorkflowNode(
            "destination",
            "destination_research",
            depends_on={"requirements"},
            timeout_seconds=timeout_seconds,
        ),
        WorkflowNode(
            "flights",
            "flight_transportation",
            depends_on={"requirements"},
            timeout_seconds=timeout_seconds,
        ),
        WorkflowNode(
            "hotels",
            "hotel_stay",
            depends_on={"requirements"},
            timeout_seconds=timeout_seconds,
        ),
        WorkflowNode(
            "food",
            "food_restaurant",
            depends_on={"requirements"},
            timeout_seconds=timeout_seconds,
        ),
        WorkflowNode(
            "weather",
            "weather_season",
            depends_on={"requirements"},
            timeout_seconds=timeout_seconds,
        ),
        WorkflowNode(
            "budget",
            "budget_estimation",
            depends_on={"requirements", "flights", "hotels"},
            timeout_seconds=timeout_seconds,
        ),
        WorkflowNode(
            "activities",
            "activity_attraction",
            depends_on={"destination"},
            timeout_seconds=timeout_seconds,
        ),
        WorkflowNode(
            "itinerary",
            "itinerary_planning",
            depends_on={"activities", "weather", "hotels"},
            timeout_seconds=timeout_seconds,
        ),
        WorkflowNode(
            "validation",
            "validation",
            depends_on={"itinerary", "budget", "flights"},
            timeout_seconds=timeout_seconds,
        ),
        WorkflowNode(
            "final_plan",
            "final_plan_generator",
            depends_on={"validation"},
            timeout_seconds=timeout_seconds,
        ),
    ]
    return WorkflowGraph(nodes={node.name: node for node in nodes})
