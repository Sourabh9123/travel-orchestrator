# travel-orchestrator

AI-powered multi-agent travel orchestration platform built with FastAPI, AsyncIO, Redis, PostgreSQL, SQLAlchemy 2.0, and a DAG-based agent workflow engine.

## What is included

- Supervisor-led multi-agent workflow
- Requirement, destination, flight, hotel, food, activity, budget, weather, validation, and final-plan agents
- Versioned Redis shared memory with TTL and distributed locks
- Async tool interface with caching, retries, rate-limit-ready boundaries, logging, and timeouts
- FastAPI APIs for planning, validation, replanning, status, history, bookings, metrics, and WebSockets
- PostgreSQL domain models and Alembic migration
- Docker Compose with API, worker, Postgres, Redis, Prometheus, and Grafana
- Production-oriented docs and tests

## Run locally

```bash
cp .env.example .env
docker compose up --build
```

Then open:

- API docs: `http://localhost:8000/docs`
- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3000`

Run migrations inside the API container:

```bash
docker compose exec api alembic upgrade head
```

## Example request

```bash
curl -X POST http://localhost:8000/api/v1/travel/plan \
  -H 'Content-Type: application/json' \
  -d '{
    "prompt": "Plan a 5 day culture and food trip to Lisbon for two people under 2500 USD",
    "origin": "New York",
    "destination": "Lisbon",
    "travelers": 2,
    "budget_amount": 2500,
    "currency": "USD",
    "preferences": ["food", "walkable neighborhoods", "history"],
    "travel_style": "culture"
  }'
```

See [docs/architecture.md](docs/architecture.md) for design details.

For a detailed API-to-downstream flow map, see [FLOW_README.md](FLOW_README.md).

For a deeper production architecture walkthrough, see [ARCHITECTURE_README.md](ARCHITECTURE_README.md).

## Postman

Import these files into Postman for local API testing:

- Collection: `docs/postman/travel-orchestrator.postman_collection.json`
- Environment: `docs/postman/travel-orchestrator.local.postman_environment.json`

Run `Create Travel Plan` first; its test script stores `workflow_id` and `trip_id` for follow-up requests.
