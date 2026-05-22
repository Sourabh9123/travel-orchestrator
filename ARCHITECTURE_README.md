# travel-orchestrator architecture README

## Purpose

`travel-orchestrator` is an AI-powered, multi-agent travel planning backend. It is designed as a production-ready foundation for trip planning, itinerary optimization, provider search, budget analysis, validation, and future booking/payment orchestration.

The platform uses a supervisor/orchestrator model: the API accepts a travel request, a workflow graph coordinates specialized agents, agents write structured outputs into shared memory, a validation stage checks consistency, and the final plan generator produces an exportable trip plan.

## High-level system

```text
Client
  |
  | REST / WebSocket
  v
FastAPI API
  |
  | service layer
  v
TravelPlanningService
  |
  | builds DAG + runtime context
  v
WorkflowEngine
  |
  | dependency-aware async execution
  v
Specialized Agents
  |
  | tools + shared state
  v
Redis Shared Memory / Provider Tools / PostgreSQL
```

## Runtime flow

1. A client calls `POST /api/v1/travel/plan` with a prompt and optional structured fields.
2. The API validates the request with Pydantic schemas.
3. `TravelPlanningService` creates a `Trip` row in PostgreSQL and a workflow id.
4. The workflow state is initialized in Redis.
5. `WorkflowEngine` executes a DAG:
   - supervisor setup
   - requirement analysis
   - parallel destination, flight, hotel, food, weather research
   - activity recommendations
   - budget estimation
   - itinerary planning
   - validation
   - final plan generation
6. Workflow events are logged, published to Redis pub/sub, and broadcast over WebSocket.
7. The final plan is written back to PostgreSQL and exposed through status/history APIs.

## Core packages

`app/api`

FastAPI transport layer. It owns route definitions, dependency injection, request/response contracts, and WebSocket endpoints.

`app/services`

Use-case layer. Services coordinate repositories, Redis memory, workflow execution, and booking tool calls. This layer is the transaction boundary for most business operations.

`app/orchestration`

Generic DAG workflow engine. It supports dependency management, parallel ready-node execution, retries, per-node timeout handling, failure propagation, and event hooks.

`app/agents`

Agent contracts and travel-specific agents. Each agent has one responsibility and writes a structured `AgentOutput`.

`app/tools`

Provider adapter boundary. Tools expose `execute(payload, context)` and centralize caching, rate limiting, retries, timeout handling, and logging.

`app/memory`

Redis-backed shared memory. The memory layer stores workflow context, supports TTLs, versioned updates, and lock-protected deep merges.

`app/db`

SQLAlchemy 2.0 async models and session lifecycle.

`app/repositories`

Persistence abstractions that keep SQLAlchemy access out of agents and API routes.

`app/monitoring`

Prometheus metrics and OpenTelemetry tracing setup.

## Agent responsibilities

| Agent | Responsibility |
| --- | --- |
| Supervisor | Coordinates workflow strategy and shared context |
| Requirement Analysis | Extracts destination, duration, travelers, budget, preferences, visa notes, and constraints |
| Destination Research | Produces destination highlights, safety notes, and seasonal insight |
| Flight & Transportation | Searches route options and local transport recommendations |
| Hotel & Stay | Recommends stay options and location scoring |
| Food & Restaurant | Suggests restaurants, cuisines, and local food |
| Activity & Attraction | Produces attractions, experiences, events, and ticket suggestions |
| Weather & Season | Adds forecast, seasonality, and packing guidance |
| Budget Estimation | Creates cost breakdown and optimization advice |
| Itinerary Planning | Builds day-wise itinerary with fatigue-aware grouping |
| Validation | Detects conflicts and feasibility issues |
| Final Plan Generator | Combines all outputs into a final exportable plan |

## Shared memory model

Redis keys:

- `travel:workflow:{workflow_id}:state`
- `travel:workflow:{workflow_id}:version`
- `travel:workflow:{workflow_id}:meta`
- `travel:workflow:{workflow_id}:events`

State updates use Redis locks and version checks to avoid lost updates. Agents write into separate top-level keys such as `requirements`, `flights`, `hotels`, `weather`, `budget`, `itinerary`, `validation`, and `final_plan`.

## Tooling model

Every provider integration should implement `BaseTool`.

The base tool already provides:

- async execution
- Redis caching
- Redis rate limiting
- retry support
- timeout handling
- structured logging
- deterministic fallback behavior for local development

Real integrations can replace the mock implementations in `app/tools/travel_tools.py` without changing agent contracts.

## Persistence model

PostgreSQL stores durable product state:

- users
- trips
- itineraries
- flights
- hotels
- bookings
- activities
- conversations
- agent logs
- execution graphs

Redis stores active workflow state, temporary coordination data, cache entries, rate-limit counters, distributed locks, sessions, and pub/sub events.

## API surface

Travel:

- `POST /api/v1/travel/plan`
- `POST /api/v1/travel/validate`
- `POST /api/v1/travel/replan`
- `GET /api/v1/travel/status/{workflow_id}`
- `GET /api/v1/travel/history`
- `WS /api/v1/travel/ws/{workflow_id}`

Booking:

- `POST /api/v1/booking/flight`
- `POST /api/v1/booking/hotel`

Operations:

- `GET /health`
- `GET /metrics`
- `GET /docs`

## Local infrastructure

Docker Compose runs:

- `api`: FastAPI app using the Dockerfile default command
- `worker`: background worker placeholder
- `postgres`: durable relational store
- `redis`: shared memory, cache, locks, pub/sub, rate limits
- `prometheus`: metrics scraping
- `grafana`: dashboards and visualization

Common commands are available through `make`:

- `make build`
- `make up`
- `make down`
- `make migrate`
- `make test`
- `make logs`
- `make shell`

## Production hardening path

Recommended next steps before real bookings/payments:

- Move from FastAPI background tasks to a durable queue such as Celery, Dramatiq, Temporal, or Arq.
- Store idempotency keys for booking operations.
- Add provider-specific adapters for flights, hotels, maps, weather, events, and payments.
- Persist full workflow event logs and execution graph snapshots.
- Add JWT-authenticated users and route-level RBAC enforcement.
- Use managed PostgreSQL and Redis with backups, encryption, and private networking.
- Add OpenTelemetry collector and centralized log storage.
- Add CI for linting, type checking, unit tests, integration tests, and migration checks.
- Add load tests for workflow fan-out and WebSocket event streaming.
