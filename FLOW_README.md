# API to Downstream Flow

This document explains how the travel-orchestrator backend is connected from the HTTP API layer down to services, workflow orchestration, agents, tools, Redis memory, database persistence, WebSockets, and booking flows.

## Big Picture

```text
Client
  -> FastAPI app in app/main.py
  -> API route in app/api/routes/*.py
  -> dependency factory in app/api/deps.py
  -> service in app/services/*.py
  -> repositories, workflow engine, agents, tools, memory
  -> PostgreSQL, Redis, WebSocket events, final response/state
```

The API layer stays thin. It validates request schemas, injects a service, and delegates business work. Services own transaction boundaries and workflow startup. The workflow engine owns DAG execution. Agents own travel-domain steps. Tools own provider-style operations such as flights, hotels, weather, destination research, budgets, and bookings.

## Application Startup

### app/main.py

This file creates and configures the FastAPI application.

- `settings = get_settings()` loads config from `app/core/config.py`.
- `configure_logging(settings.debug)` configures structured logging.
- `app = FastAPI(...)` creates the app.
- `app.add_middleware(CORSMiddleware, ...)` enables CORS.
- `configure_tracing(app, settings)` wires OpenTelemetry tracing.
- `register_exception_handlers(app)` installs shared error handlers.
- `metrics_middleware(...)` records Prometheus latency for every HTTP request.
- `metrics()` exposes `GET /metrics`.
- `app.include_router(health.router)` registers health routes.
- `app.include_router(travel.router, prefix=settings.api_prefix)` registers travel routes, usually under `/api/v1`.
- `app.include_router(booking.router, prefix=settings.api_prefix)` registers booking routes.

The most important downstream connection is:

```text
app/main.py
  imports app.api.routes.travel
  includes it with prefix settings.api_prefix
  exposes routes like /api/v1/travel/plan
```

## Dependency Wiring

### app/api/deps.py

Routes do not manually construct services. FastAPI injects them through dependency functions:

- `get_current_roles(...)` reads an optional bearer token and returns roles.
- `get_travel_service(...)` receives:
  - `AsyncSession` from `app/db/session.py:get_db_session`
  - `Redis` from `app/memory/redis.py:get_redis`
  - `Settings` from `app/core/config.py:get_settings`
  - then yields `TravelPlanningService(session, redis, settings)`
- `get_booking_service(...)` does the same wiring for `BookingService`.

This means route handlers can depend on `TravelPlanningService` or `BookingService` without knowing how database, Redis, or settings are created.

## Travel Planning API Flow

### Entry Point: POST /api/v1/travel/plan

File: `app/api/routes/travel.py`

Method:

```python
plan_travel(request, background_tasks, service)
```

Flow:

```text
Client POST /api/v1/travel/plan
  -> TravelPlanRequest schema validates body
  -> plan_travel(...)
  -> service.start_plan(request)
  -> background_tasks.add_task(service.run_plan, workflow_id, request, trip_id)
  -> returns TravelPlanResponse immediately with 202 Accepted
```

`plan_travel(...)` intentionally returns before the full plan is generated. The full workflow runs in a FastAPI background task.

### Request and Response Schemas

File: `app/schemas/travel.py`

Important models:

- `TravelPlanRequest`: incoming user prompt, origin, destination, dates, travelers, budget, currency, preferences, style.
- `TravelPlanResponse`: returned `workflow_id`, `trip_id`, status, optional plan and validation.
- `TravelRequirements`: normalized requirements created by the requirement agent.
- `AgentOutput`: standard output object returned by every agent.
- `ValidationResult`: consistency check result.
- `ReplanRequest`: request body for replanning.
- `BookingRequest`: request body for booking endpoints.

## TravelPlanningService

File: `app/services/travel_service.py`

This is the main use-case service for travel planning.

### __init__(session, redis, settings)

Stores dependencies and creates:

```python
self.memory = SharedMemory(redis, ttl_seconds=settings.memory_ttl_seconds)
```

Downstream dependencies:

- database session for trips
- Redis client for workflow metadata and shared memory
- settings for timeouts and TTLs
- `SharedMemory` for workflow state

### start_plan(request)

Responsibilities:

1. Generate a new `workflow_id`.
2. Create a `Trip` SQLAlchemy model with status `PLANNING`.
3. Persist it through `TripRepository(self.session).add(trip)`.
4. Commit the database transaction.
5. Store workflow metadata in Redis:

```text
travel:workflow:{workflow_id}:meta
  status = accepted
  trip_id = {trip.id}
```

6. Return `TravelPlanResponse(workflow_id, trip_id, status="accepted")`.

Connections:

```text
TravelPlanningService.start_plan
  -> app.db.models.Trip
  -> app.repositories.trips.TripRepository.add
  -> SQLAlchemy AsyncSession.commit
  -> Redis hset/expire
```

### run_plan(workflow_id, request, trip_id)

This method runs in the background after `POST /travel/plan` responds.

Responsibilities:

1. Mark workflow metadata as `running` in Redis.
2. Build a `WorkflowEngine`.
3. Build the default agent registry.
4. Build the default tool registry.
5. Build the travel planning graph.
6. Execute the graph.
7. Persist the final plan back to the trip row.
8. Mark workflow metadata as `completed`.
9. On failure, mark workflow and trip as `failed`.

Main construction:

```python
engine = WorkflowEngine(
    agents=build_agent_registry(),
    memory=self.memory,
    tools=build_tool_registry(self.redis, self.settings),
    event_hooks=[self._publish_event],
    default_timeout_seconds=self.settings.agent_timeout_seconds,
)
graph = build_travel_planning_graph(self.settings.agent_timeout_seconds)
final_state = await engine.execute(...)
```

Connections:

```text
TravelPlanningService.run_plan
  -> app.agents.travel_agents.build_agent_registry
  -> app.tools.registry.build_tool_registry
  -> app.workflows.travel.build_travel_planning_graph
  -> app.orchestration.engine.WorkflowEngine.execute
  -> app.repositories.trips.TripRepository.get
  -> Trip.final_plan / Trip.requirements / Trip.status
  -> SQLAlchemy commit
```

### validate(workflow_id)

Reads workflow state from Redis shared memory and returns validation:

```text
TravelPlanningService.validate
  -> SharedMemory.get(workflow_id)
  -> snapshot.state["validation"]
  -> ValidationResult.model_validate(...)
```

If validation has not run yet, it returns a default invalid result with `Plan not validated`.

### status(workflow_id)

Returns workflow metadata plus selected shared-state fields:

```text
TravelPlanningService.status
  -> Redis hgetall travel:workflow:{workflow_id}:meta
  -> SharedMemory.get(workflow_id)
  -> version, workflow, final_plan
```

This powers `GET /api/v1/travel/status/{workflow_id}`.

### history(user_id, limit)

Loads recent trips for a user:

```text
TravelPlanningService.history
  -> TripRepository.list_for_user(user_id, limit)
  -> list of id/title/status/destination/created_at
```

### _publish_event(event)

The workflow engine calls this hook whenever workflow or node events happen.

It publishes to:

- Redis pub/sub channel: `travel:workflow:{workflow_id}:events`
- in-process WebSocket manager: `websocket_manager.publish(...)`

Connections:

```text
WorkflowEngine._emit
  -> TravelPlanningService._publish_event
  -> Redis publish
  -> app.websocket.manager.websocket_manager.publish
```

## Workflow Graph

### app/workflows/travel.py

The method `build_travel_planning_graph(timeout_seconds)` defines the DAG.

Each `WorkflowNode` has:

- `name`: node key in the DAG.
- `agent_name`: key used to find an agent in the agent registry.
- `depends_on`: upstream node names that must complete first.
- `timeout_seconds`: timeout passed to node execution.
- `max_retries`: retry count, default from `WorkflowNode`.

Current graph:

```text
supervise
  -> requirements
      -> destination
          -> activities
      -> flights
      -> hotels
      -> food
      -> weather
      -> budget depends on requirements + flights + hotels
      -> itinerary depends on activities + weather + hotels
      -> validation depends on itinerary + budget + flights
      -> final_plan depends on validation
```

Important detail: after `requirements`, multiple nodes can run in parallel because they all depend only on `requirements`.

## Workflow Engine

### app/orchestration/graph.py

Classes:

- `WorkflowNode`: describes one executable DAG node.
- `WorkflowGraph`: stores nodes and finds ready work.

Method:

```python
WorkflowGraph.ready_nodes(completed, running, failed)
```

This returns all nodes whose dependencies are complete and that are not already completed, running, or failed.

### app/orchestration/engine.py

Class:

```python
WorkflowEngine
```

#### execute(workflow_id, graph, initial_state, user_id)

This is the main DAG runner.

Steps:

1. Initialize Redis shared memory:

```python
await self.memory.initialize(
    workflow_id,
    {
        **initial_state,
        "workflow": {"status": "running", "completed_nodes": [], "failed_nodes": []},
    },
)
```

2. Emit `WORKFLOW_STARTED`.
3. Loop until all graph nodes are completed or failed.
4. Ask the graph for ready nodes with `graph.ready_nodes(...)`.
5. Run ready nodes concurrently with `asyncio.gather(...)`.
6. If a node fails, emit `NODE_FAILED` and raise `WorkflowExecutionError`.
7. When all nodes complete, update shared memory workflow status to `completed`.
8. Emit `WORKFLOW_COMPLETED`.
9. Return the final shared state.

#### _run_node(workflow_id, node, user_id)

This executes one DAG node.

Steps:

1. Resolve the agent:

```python
agent = self.agents[node.agent_name]
```

2. Emit `NODE_STARTED`.
3. Read the latest shared state:

```python
snapshot = await self.memory.get(workflow_id)
```

4. Build `AgentContext`:

```python
AgentContext(
    workflow_id=str(workflow_id),
    user_id=user_id,
    memory=self.memory,
    tools=self.tools,
)
```

5. Run the agent with timeout:

```python
output = await asyncio.wait_for(agent.run(snapshot.state, context), timeout=...)
```

6. Merge the agent output into shared memory:

```python
await self.memory.update(
    workflow_id,
    {
        **output.data,
        "agent_outputs": {agent.name: output.model_dump(mode="json")},
        "workflow": {"last_completed_node": node.name},
    },
)
```

7. Emit `NODE_COMPLETED`.

The engine is generic; it does not know travel details. Travel-specific behavior lives in the agents.

## Agents

### Base Agent

File: `app/agents/base.py`

Class:

```python
BaseAgent
```

Required class attributes:

- `name`
- `description`
- `system_prompt`

Important methods:

- `run(state, context)`: wrapper that logs latency and converts unknown exceptions into `AgentExecutionError`.
- `_run(state, context)`: abstract method implemented by each agent.
- `metadata()`: returns name, description, and system prompt.

Context:

```python
AgentContext(
    workflow_id,
    user_id,
    memory,
    tools,
)
```

Agents receive the current shared state and can call registered tools through `context.tools`.

### Agent Registry

File: `app/agents/travel_agents.py`

Method:

```python
build_agent_registry()
```

Returns a dictionary:

```text
agent.name -> agent instance
```

The workflow engine uses `WorkflowNode.agent_name` to pick the right agent from this registry.

### Agent-by-Agent Flow

#### SupervisorAgent

- Node: `supervise`
- Agent name: `supervisor`
- Input state: initial request.
- Output key: `supervisor`
- Purpose: records workflow strategy metadata.

#### RequirementAnalysisAgent

- Node: `requirements`
- Agent name: `requirement_analysis`
- Depends on: `supervise`
- Input key: `request`
- Output key: `requirements`
- Main method: `_run(...)`
- Builds a `TravelRequirements` object from request fields.
- Uses `_maybe_date(...)` to parse optional dates.
- Uses `_guess_destination(...)` when destination is missing.

This output is central. Most downstream agents read `state["requirements"]`.

#### DestinationResearchAgent

- Node: `destination`
- Agent name: `destination_research`
- Depends on: `requirements`
- Input key: `requirements`
- Tool used: `places_research`
- Output key: `destination`

Call:

```python
context.tools.get("places_research").execute(requirements, tool_context)
```

#### FlightTransportationAgent

- Node: `flights`
- Agent name: `flight_transportation`
- Depends on: `requirements`
- Input key: `requirements`
- Tool used: `flight_search`
- Output key: `flights`
- Adds local `ground_transport` guidance after tool execution.

#### HotelStayAgent

- Node: `hotels`
- Agent name: `hotel_stay`
- Depends on: `requirements`
- Input key: `requirements`
- Tool used: `hotel_search`
- Output key: `hotels`

#### FoodRestaurantAgent

- Node: `food`
- Agent name: `food_restaurant`
- Depends on: `requirements`
- Input key: `requirements.destination`
- Output key: `food`
- Currently creates deterministic local specialties and restaurant examples.

#### WeatherSeasonAgent

- Node: `weather`
- Agent name: `weather_season`
- Depends on: `requirements`
- Input key: `requirements`
- Tool used: `weather_analysis`
- Output key: `weather`

#### BudgetEstimationAgent

- Node: `budget`
- Agent name: `budget_estimation`
- Depends on: `requirements`, `flights`, `hotels`
- Input key: `requirements`
- Tool used: `budget_estimator`
- Output key: `budget`
- Adds `estimated_total` by summing the tool breakdown.

#### ActivityAttractionAgent

- Node: `activities`
- Agent name: `activity_attraction`
- Depends on: `destination`
- Input key: `destination.highlights`
- Output key: `activities`
- Converts destination highlights into activity objects.

#### ItineraryPlanningAgent

- Node: `itinerary`
- Agent name: `itinerary_planning`
- Depends on: `activities`, `weather`, `hotels`
- Input keys: `requirements`, `activities`
- Output key: `itinerary`
- Distributes activities across `requirements["duration_days"]`.

#### ValidationAgent

- Node: `validation`
- Agent name: `validation`
- Depends on: `itinerary`, `budget`, `flights`
- Input keys: `requirements`, `budget`, `itinerary`
- Output key: `validation`
- Checks:
  - budget overrun
  - missing itinerary

#### FinalPlanGeneratorAgent

- Node: `final_plan`
- Agent name: `final_plan_generator`
- Depends on: `validation`
- Input keys: `requirements`, `destination`, `flights`, `hotels`, `food`, `activities`, `weather`, `budget`, `itinerary`, `validation`
- Output key: `final_plan`
- Assembles the final exportable payload.

## Tools

### Tool Registry

File: `app/tools/registry.py`

Method:

```python
build_tool_registry(redis, settings)
```

Creates:

- `FlightSearchTool`
- `HotelSearchTool`
- `WeatherTool`
- `PlacesTool`
- `BudgetTool`
- `BookingTool`

Each tool receives:

```python
{"redis": redis, "timeout_seconds": settings.tool_timeout_seconds}
```

The registry stores tools by `tool.name`, and agents retrieve them with:

```python
context.tools.get("tool_name")
```

### Base Tool Runtime

File: `app/tools/base.py`

Class:

```python
BaseTool
```

Important method:

```python
execute(payload, context)
```

Every tool execution gets:

- Redis-backed rate limiting through `_enforce_rate_limit(...)`
- Redis cache lookup through `_cache_key(payload)`
- timeout handling with `asyncio.wait_for(...)`
- retries through `tenacity.AsyncRetrying` when installed
- fallback retries through `_execute_with_simple_retries(...)`
- structured latency logging
- Redis cache write after successful execution

Concrete tools implement:

```python
_execute(payload, context)
```

### Concrete Travel Tools

File: `app/tools/travel_tools.py`

- `FlightSearchTool`
  - name: `flight_search`
  - returns mock flight options and route notes
- `HotelSearchTool`
  - name: `hotel_search`
  - returns mock hotel options
- `WeatherTool`
  - name: `weather_analysis`
  - returns forecast summary, packing, seasonal score
- `PlacesTool`
  - name: `places_research`
  - returns highlights, safety, best time to visit
- `BudgetTool`
  - name: `budget_estimator`
  - returns cost breakdown and optimization notes
- `BookingTool`
  - name: `booking`
  - returns placeholder provider booking status

These are deterministic mockable adapters today. Real provider integrations can replace the `_execute(...)` implementations while keeping the same tool interface.

## Shared Memory

File: `app/memory/shared_memory.py`

Class:

```python
SharedMemory
```

Redis keys:

```text
travel:workflow:{workflow_id}:state
travel:workflow:{workflow_id}:version
```

Methods:

- `initialize(workflow_id, state)`: writes initial state and version `1`.
- `get(workflow_id)`: reads state and version into `MemorySnapshot`.
- `update(workflow_id, patch, expected_version=None)`: lock-protected deep merge update.

Important behavior:

- Updates use a Redis lock: `travel:workflow:{workflow_id}:state:lock`
- Updates deep-merge dictionaries, so each agent can write its own key without replacing unrelated data.
- TTL is applied to both state and version keys.

Example state evolution:

```text
Initial:
{
  "request": {...},
  "workflow": {"status": "running", ...}
}

After RequirementAnalysisAgent:
{
  "request": {...},
  "requirements": {...},
  "agent_outputs": {"requirement_analysis": {...}},
  "workflow": {"last_completed_node": "requirements", ...}
}

After FinalPlanGeneratorAgent:
{
  ...
  "final_plan": {...},
  "validation": {...},
  "workflow": {"status": "completed", ...}
}
```

## Database and Repositories

### app/db/models.py

Important models:

- `Trip`: stores user trip request, status, requirements, and final plan.
- `Booking`: stores booking records.
- `AgentLog`: stores agent execution logs if used by future workflows.
- `ExecutionGraph`: stores graph snapshots if used by future persistence.

### app/repositories/base.py

Generic async repository helpers:

- `add(instance)`
- `get(id)`

### app/repositories/trips.py

`TripRepository`:

- `list_for_user(user_id, limit)`
- `set_status(trip_id, status)`

`BookingRepository`:

- `create_pending(trip_id, booking_type, provider, payload)`

Services use repositories so route handlers do not directly touch SQLAlchemy models.

## Status, Validation, Replan, and WebSocket Routes

### GET /api/v1/travel/status/{workflow_id}

File: `app/api/routes/travel.py`

Method:

```python
status(workflow_id, service)
```

Calls:

```text
TravelPlanningService.status
  -> Redis workflow meta
  -> SharedMemory.get
  -> returns version, workflow, final_plan
```

### POST /api/v1/travel/validate

Method:

```python
validate_plan(workflow_id, service)
```

Calls:

```text
TravelPlanningService.validate
  -> SharedMemory.get
  -> ValidationResult
```

### POST /api/v1/travel/replan

Method:

```python
replan(request, background_tasks, service)
```

Flow:

```text
request.workflow_id
  -> service.status(old_workflow_id)
  -> extract old final_plan.requirements
  -> create new TravelPlanRequest(prompt=request.prompt, **old_requirements)
  -> service.start_plan(new_request)
  -> background service.run_plan(...)
```

Replanning creates a new workflow and trip rather than mutating the old one.

### GET /api/v1/travel/history

Method:

```python
history(user_id, limit, service)
```

Calls:

```text
TravelPlanningService.history
  -> TripRepository.list_for_user
```

### WebSocket /api/v1/travel/ws/{workflow_id}

Method:

```python
workflow_ws(websocket, workflow_id)
```

Flow:

```text
Client connects
  -> websocket_manager.connect(workflow_id, websocket)
  -> WorkflowEngine emits events
  -> TravelPlanningService._publish_event
  -> websocket_manager.publish(workflow_id, event)
  -> client receives event
```

## Booking Flow

### API Routes

File: `app/api/routes/booking.py`

Routes:

- `POST /api/v1/booking/flight`
- `POST /api/v1/booking/hotel`

Both call:

```python
service.create_booking("flight" or "hotel", request)
```

### BookingService

File: `app/services/booking_service.py`

Method:

```python
create_booking(booking_type, request)
```

Flow:

```text
Booking API route
  -> BookingService.create_booking
  -> build_tool_registry(...).get("booking")
  -> BookingTool.execute(...)
  -> BookingRepository.create_pending(...)
  -> database commit
  -> return booking_id + provider result
```

If tool execution fails, the service rolls back the database transaction and raises the error.

## Error Handling

### app/core/exceptions.py

Defines domain errors such as:

- `AppError`
- `AgentExecutionError`
- `WorkflowExecutionError`
- `ToolExecutionError`
- `BookingError`
- `MemoryStateError`
- `ValidationFailure`

### app/api/exception_handlers.py

`register_exception_handlers(app)` wires handlers that convert internal exceptions into API responses.

Common pattern:

```text
agent/tool/service raises AppError subclass
  -> FastAPI exception handler catches it
  -> response uses shared error envelope
```

## End-to-End Plan Example

When a client sends:

```http
POST /api/v1/travel/plan
```

With:

```json
{
  "prompt": "Plan a 5 day culture and food trip to Lisbon for two people under 2500 USD",
  "origin": "New York",
  "destination": "Lisbon",
  "travelers": 2,
  "budget_amount": 2500,
  "currency": "USD",
  "preferences": ["food", "walkable neighborhoods", "history"],
  "travel_style": "culture"
}
```

The system path is:

```text
app/main.py
  -> travel router mounted at /api/v1/travel
app/api/routes/travel.py:plan_travel
  -> app/api/deps.py:get_travel_service
  -> app/services/travel_service.py:TravelPlanningService.start_plan
  -> app/repositories/trips.py:TripRepository.add
  -> PostgreSQL trip row
  -> Redis workflow meta accepted
  -> return 202 Accepted
  -> background TravelPlanningService.run_plan
  -> app/agents/travel_agents.py:build_agent_registry
  -> app/tools/registry.py:build_tool_registry
  -> app/workflows/travel.py:build_travel_planning_graph
  -> app/orchestration/engine.py:WorkflowEngine.execute
  -> app/memory/shared_memory.py:SharedMemory.initialize
  -> SupervisorAgent
  -> RequirementAnalysisAgent
  -> destination/flights/hotels/food/weather agents in parallel where possible
  -> BudgetEstimationAgent and ActivityAttractionAgent
  -> ItineraryPlanningAgent
  -> ValidationAgent
  -> FinalPlanGeneratorAgent
  -> SharedMemory final state
  -> Trip.final_plan persisted in PostgreSQL
  -> Redis workflow meta completed
  -> WebSocket and Redis pub/sub events emitted along the way
```

## Quick File Map

| Layer | File | Important methods/classes | Uses |
| --- | --- | --- | --- |
| App setup | `app/main.py` | `app`, `lifespan`, `metrics_middleware`, `metrics` | routers, settings, logging, tracing, metrics |
| API deps | `app/api/deps.py` | `get_travel_service`, `get_booking_service` | DB session, Redis, settings, services |
| Travel routes | `app/api/routes/travel.py` | `plan_travel`, `validate_plan`, `replan`, `status`, `history`, `workflow_ws` | `TravelPlanningService`, schemas, WebSocket manager |
| Booking routes | `app/api/routes/booking.py` | `book_flight`, `book_hotel` | `BookingService`, `BookingRequest` |
| Travel service | `app/services/travel_service.py` | `start_plan`, `run_plan`, `validate`, `status`, `history`, `_publish_event` | repositories, engine, graph, agents, tools, memory |
| Booking service | `app/services/booking_service.py` | `create_booking` | booking tool, booking repository |
| Workflow graph | `app/workflows/travel.py` | `build_travel_planning_graph` | `WorkflowGraph`, `WorkflowNode` |
| DAG engine | `app/orchestration/engine.py` | `execute`, `_run_node`, `_emit` | agents, shared memory, tool registry, event hooks |
| DAG model | `app/orchestration/graph.py` | `WorkflowNode`, `WorkflowGraph.ready_nodes` | dependency resolution |
| Agent base | `app/agents/base.py` | `BaseAgent.run`, `BaseAgent._run`, `AgentContext` | logging, errors, agent context |
| Travel agents | `app/agents/travel_agents.py` | all agent `_run` methods, `build_agent_registry` | schemas, tools, shared state |
| Tool base | `app/tools/base.py` | `BaseTool.execute`, `_execute`, `_cache_key`, `_enforce_rate_limit` | Redis cache/rate limit, retries, timeouts |
| Tool registry | `app/tools/registry.py` | `ToolRegistry.get`, `build_tool_registry` | concrete travel tools |
| Travel tools | `app/tools/travel_tools.py` | `_execute` per tool | deterministic provider-like data |
| Shared memory | `app/memory/shared_memory.py` | `initialize`, `get`, `update` | Redis state and version keys |
| Trip repository | `app/repositories/trips.py` | `list_for_user`, `set_status`, `create_pending` | SQLAlchemy models |
| Schemas | `app/schemas/travel.py` | request, response, requirements, output schemas | API validation and agent contracts |
| Models | `app/db/models.py` | `Trip`, `Booking`, `AgentLog`, `ExecutionGraph` | PostgreSQL persistence |

## How to Add a New Agent

1. Add a class in `app/agents/travel_agents.py` that extends `BaseAgent`.
2. Set `name`, `description`, and `system_prompt`.
3. Implement `_run(state, context)` and return `AgentOutput`.
4. Add the agent to `build_agent_registry()`.
5. Add a `WorkflowNode` in `app/workflows/travel.py`.
6. Set `depends_on` so the agent receives the state keys it needs.
7. If the agent needs external data, add or reuse a tool in `app/tools`.
8. Add tests in `tests/unit`.

## How to Add a New Tool

1. Add a class in `app/tools/travel_tools.py` or a new tool module.
2. Extend `BaseTool`.
3. Set `name` and `description`.
4. Implement `_execute(payload, context)`.
5. Register it in `build_tool_registry(...)`.
6. Call it from an agent with `context.tools.get("your_tool_name").execute(...)`.

## Where State Lives

| Data | Location | Writer | Reader |
| --- | --- | --- | --- |
| Request body | Redis shared memory `request` key | `WorkflowEngine.execute` | `RequirementAnalysisAgent` |
| Workflow metadata | Redis hash `travel:workflow:{id}:meta` | `TravelPlanningService` | `status(...)` |
| Agent outputs | Redis shared memory | `WorkflowEngine._run_node` | downstream agents, status |
| Final plan | Redis shared memory and `Trip.final_plan` | `FinalPlanGeneratorAgent`, `TravelPlanningService.run_plan` | status endpoint, database consumers |
| Trip row | PostgreSQL `trips` table | `TravelPlanningService.start_plan/run_plan` | history endpoint, booking flow |
| Booking row | PostgreSQL `bookings` table | `BookingService.create_booking` | future booking status/polling |
| Events | Redis pub/sub and WebSocket manager | `TravelPlanningService._publish_event` | WebSocket clients, subscribers |

