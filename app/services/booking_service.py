from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.repositories.trips import BookingRepository
from app.schemas.travel import BookingRequest
from app.tools.base import ToolContext
from app.tools.registry import build_tool_registry


class BookingService:
    def __init__(self, session: AsyncSession, redis: Redis, settings: Settings) -> None:
        self.session = session
        self.redis = redis
        self.settings = settings

    async def create_booking(self, booking_type: str, request: BookingRequest) -> dict:
        tool = build_tool_registry(self.redis, self.settings).get("booking")
        result = await tool.execute(
            {
                "provider": request.provider,
                "selection_id": request.selection_id,
                "payment_token": request.payment_token,
                "metadata": request.metadata,
            },
            ToolContext(workflow_id=str(request.trip_id)),
        )
        booking = await BookingRepository(self.session).create_pending(
            trip_id=request.trip_id,
            booking_type=booking_type,
            provider=request.provider,
            payload=result,
        )
        await self.session.commit()
        return {"booking_id": str(booking.id), **result}


async def booking_status_placeholder(booking_id: UUID) -> dict:
    return {"booking_id": str(booking_id), "status": "pending"}
