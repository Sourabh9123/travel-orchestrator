from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Query, WebSocket, WebSocketDisconnect

from app.api.deps import get_travel_service
from app.schemas.travel import (
    ReplanRequest,
    TravelPlanRequest,
    TravelPlanResponse,
    ValidationResult,
)
from app.services.travel_service import TravelPlanningService
from app.websocket.manager import websocket_manager

router = APIRouter(prefix="/travel", tags=["travel"])


@router.post("/plan", response_model=TravelPlanResponse, status_code=202)
async def plan_travel(
    request: TravelPlanRequest,
    background_tasks: BackgroundTasks,
    service: TravelPlanningService = Depends(get_travel_service),
) -> TravelPlanResponse:
    """Accept a travel planning request and start background orchestration."""

    response = await service.start_plan(request)
    background_tasks.add_task(service.run_plan, response.workflow_id, request, response.trip_id)
    return response


@router.post("/validate", response_model=ValidationResult)
async def validate_plan(
    workflow_id: UUID,
    service: TravelPlanningService = Depends(get_travel_service),
) -> ValidationResult:
    """Return the validation result for a workflow."""

    return await service.validate(workflow_id)


@router.post("/replan", response_model=TravelPlanResponse, status_code=202)
async def replan(
    request: ReplanRequest,
    background_tasks: BackgroundTasks,
    service: TravelPlanningService = Depends(get_travel_service),
) -> TravelPlanResponse:
    """Start a new workflow using requirements from a previous plan."""

    status = await service.status(request.workflow_id)
    original = status.get("state", {}).get("final_plan", {}).get("requirements", {})
    plan_request = TravelPlanRequest(prompt=request.prompt, **original)
    response = await service.start_plan(plan_request)
    background_tasks.add_task(
        service.run_plan, response.workflow_id, plan_request, response.trip_id
    )
    return response


@router.get("/status/{workflow_id}")
async def status(
    workflow_id: UUID,
    service: TravelPlanningService = Depends(get_travel_service),
) -> dict:
    """Return workflow status and available final plan data."""

    return await service.status(workflow_id)


@router.get("/history")
async def history(
    user_id: UUID = Query(...),
    limit: int = Query(default=25, ge=1, le=100),
    service: TravelPlanningService = Depends(get_travel_service),
) -> list[dict]:
    """Return recent trip history for a user."""

    return await service.history(user_id=user_id, limit=limit)


@router.websocket("/ws/{workflow_id}")
async def workflow_ws(websocket: WebSocket, workflow_id: UUID) -> None:
    """Stream workflow events to a WebSocket client."""

    await websocket_manager.connect(workflow_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        websocket_manager.disconnect(workflow_id, websocket)
