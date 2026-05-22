from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import BookingError, ToolExecutionError
from app.repositories.trips import BookingRepository
from app.schemas.travel import BookingRequest
from app.tools.base import ToolContext
from app.tools.registry import build_tool_registry


class BookingService:
    """Use-case service for booking travel components."""

    def __init__(self, session: AsyncSession, redis: Redis, settings: Settings) -> None:
        """Create the service with database, Redis, and settings dependencies."""

        self.session = session
        self.redis = redis
        self.settings = settings

    async def create_booking(self, booking_type: str, request: BookingRequest) -> dict:
        """Create a pending booking through the configured booking tool."""

        try:
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
        except ToolExecutionError:
            await self.session.rollback()
            raise
        except Exception as exc:
            await self.session.rollback()
            raise BookingError(
                "Booking orchestration failed",
                details={"booking_type": booking_type, "trip_id": str(request.trip_id)},
            ) from exc


async def booking_status_placeholder(booking_id: UUID) -> dict:
    """Return a placeholder booking status until provider polling is implemented."""

    return {"booking_id": str(booking_id), "status": "pending"}
