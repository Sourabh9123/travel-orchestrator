from prometheus_client import Counter, Histogram

WORKFLOW_COUNTER = Counter(
    "travel_workflows_total",
    "Total number of travel workflows",
    ["status"],
)
AGENT_LATENCY = Histogram(
    "travel_agent_latency_seconds",
    "Agent execution latency",
    ["agent"],
)
API_LATENCY = Histogram(
    "travel_api_latency_seconds",
    "API request latency",
    ["method", "path", "status"],
)
