from typing import Any
from uuid import UUID, uuid4

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.travel_agents import build_agent_registry
from app.core.config import Settings
from app.db.models import Trip, TripStatus
from app.memory.shared_memory import SharedMemory
from app.orchestration.engine import WorkflowEngine
from app.orchestration.events import WorkflowEvent
from app.repositories.trips import TripRepository
from app.schemas.travel import TravelPlanRequest, TravelPlanResponse, ValidationResult
from app.tools.registry import build_tool_registry
from app.websocket.manager import websocket_manager
from app.workflows.travel import build_travel_planning_graph


class TravelPlanningService:
    def __init__(self, session: AsyncSession, redis: Redis, settings: Settings) -> None:
        self.session = session
        self.redis = redis
        self.settings = settings
        self.memory = SharedMemory(redis, ttl_seconds=settings.memory_ttl_seconds)

    async def start_plan(self, request: TravelPlanRequest) -> TravelPlanResponse:
        workflow_id = uuid4()
        trip = Trip(
            user_id=request.user_id,
            title=f"Trip to {request.destination or 'selected destination'}",
            status=TripStatus.PLANNING,
            origin=request.origin,
            destination=request.destination,
            start_date=request.start_date,
            end_date=request.end_date,
            requirements=request.model_dump(mode="json"),
        )
        await TripRepository(self.session).add(trip)
        await self.session.commit()

        await self.redis.hset(
            f"travel:workflow:{workflow_id}:meta",
            mapping={"status": "accepted", "trip_id": str(trip.id)},
        )
        await self.redis.expire(f"travel:workflow:{workflow_id}:meta", self.settings.memory_ttl_seconds)
        return TravelPlanResponse(workflow_id=workflow_id, trip_id=trip.id, status="accepted")

    async def run_plan(self, workflow_id: UUID, request: TravelPlanRequest, trip_id: UUID | None) -> None:
        user_id = str(request.user_id) if request.user_id else None
        await self.redis.hset(f"travel:workflow:{workflow_id}:meta", mapping={"status": "running"})
        try:
            engine = WorkflowEngine(
                agents=build_agent_registry(),
                memory=self.memory,
                tools=build_tool_registry(self.redis, self.settings),
                event_hooks=[self._publish_event],
                default_timeout_seconds=self.settings.agent_timeout_seconds,
            )
            graph = build_travel_planning_graph(self.settings.agent_timeout_seconds)
            final_state = await engine.execute(
                workflow_id=workflow_id,
                graph=graph,
                initial_state={"request": request.model_dump(mode="json")},
                user_id=user_id,
            )
            if trip_id is not None:
                trip = await TripRepository(self.session).get(trip_id)
                if trip is not None:
                    trip.status = TripStatus.READY
                    trip.final_plan = final_state.get("final_plan", {})
                    trip.requirements = final_state.get("requirements", trip.requirements)
                    await self.session.commit()
            await self.redis.hset(f"travel:workflow:{workflow_id}:meta", mapping={"status": "completed"})
        except Exception as exc:
            await self.redis.hset(
                f"travel:workflow:{workflow_id}:meta",
                mapping={"status": "failed", "error": str(exc)},
            )
            if trip_id is not None:
                await TripRepository(self.session).set_status(trip_id, TripStatus.FAILED)
                await self.session.commit()
            raise

    async def validate(self, workflow_id: UUID) -> ValidationResult:
        snapshot = await self.memory.get(workflow_id)
        raw = snapshot.state.get("validation", {"is_valid": False, "conflicts": ["Plan not validated"]})
        return ValidationResult.model_validate(raw)

    async def status(self, workflow_id: UUID) -> dict[str, Any]:
        meta = await self.redis.hgetall(f"travel:workflow:{workflow_id}:meta")
        state: dict[str, Any] = {}
        try:
            snapshot = await self.memory.get(workflow_id)
            state = {
                "version": snapshot.version,
                "workflow": snapshot.state.get("workflow", {}),
                "final_plan": snapshot.state.get("final_plan"),
            }
        except Exception:
            state = {}
        return {"workflow_id": str(workflow_id), "meta": meta, "state": state}

    async def history(self, user_id: UUID, limit: int = 25) -> list[dict[str, Any]]:
        trips = await TripRepository(self.session).list_for_user(user_id, limit=limit)
        return [
            {
                "id": str(trip.id),
                "title": trip.title,
                "status": trip.status.value,
                "destination": trip.destination,
                "created_at": trip.created_at.isoformat(),
            }
            for trip in trips
        ]

    async def _publish_event(self, event: WorkflowEvent) -> None:
        await self.redis.publish(f"travel:workflow:{event.workflow_id}:events", event.model_dump_json())
        await websocket_manager.publish(event.workflow_id, event.model_dump(mode="json"))
