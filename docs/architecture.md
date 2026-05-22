# travel-orchestrator architecture

## Overview

`travel-orchestrator` is a production-oriented, async-first travel planning backend. A supervisor workflow receives a user prompt, converts it into structured requirements, fans out specialized travel agents, validates the combined result, and produces an exportable final plan.

## Runtime flow

1. `POST /api/v1/travel/plan` creates a trip row and workflow id.
2. The FastAPI background task starts the DAG workflow.
3. `RequirementAnalysisAgent` writes structured requirements into Redis shared memory.
4. Destination, flight, hotel, food, weather, and activity agents run through dependency-aware parallel execution.
5. Budget and itinerary agents consume prior outputs.
6. `ValidationAgent` detects conflicts such as budget overrun or missing itinerary.
7. `FinalPlanGeneratorAgent` writes a single `final_plan` payload.
8. Clients poll `GET /api/v1/travel/status/{workflow_id}` or subscribe to `/api/v1/travel/ws/{workflow_id}`.

## Clean architecture boundaries

- `api`: transport layer and dependency wiring.
- `services`: use cases and transaction boundaries.
- `agents`: autonomous domain workers with explicit responsibilities.
- `orchestration`: generic DAG execution, retries, timeouts, and hooks.
- `tools`: provider adapters with caching, logging, retries, and timeout handling.
- `memory`: Redis-backed shared state with versioned updates and locks.
- `repositories`: persistence abstractions over SQLAlchemy models.
- `db`: SQLAlchemy 2.0 async models and session lifecycle.
- `monitoring`: metrics and tracing setup.

## Shared memory design

Redis stores workflow state under `travel:workflow:{workflow_id}:state` and a version counter under `travel:workflow:{workflow_id}:version`. Updates are protected by a Redis lock and use deep merge semantics so each agent can write its own output key without replacing the whole state. TTLs keep abandoned workflow context from growing forever.

## Agent and tool design

Agents expose a single async `run(state, context)` method. Tools expose `execute(payload, context)` and centralize retries, timeout handling, structured logging, Redis caching, and provider replacement. Mock provider tools are intentionally deterministic so tests and local demos do not require paid APIs.

## Deployment strategy

The compose stack runs API, worker, PostgreSQL, Redis, Prometheus, and Grafana. For production, split API and worker replicas, run PostgreSQL and Redis as managed services, use OTLP traces with a collector, and move secrets to a dedicated secret manager. Booking tools should be isolated behind provider-specific adapters with idempotency keys and payment authorization boundaries.
