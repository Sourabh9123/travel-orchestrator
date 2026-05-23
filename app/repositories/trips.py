from uuid import UUID

from sqlalchemy import select

from app.db.models import Booking, BookingStatus, Trip, TripStatus
from app.repositories.base import AsyncRepository


class TripRepository(AsyncRepository[Trip]):
    """Repository for trip aggregate persistence."""

    model = Trip

    async def list_for_user(self, user_id: UUID, limit: int = 25) -> list[Trip]:
        """Return recent trips owned by a user."""

        result = await self.session.execute(select(Trip).where(Trip.user_id == user_id).order_by(Trip.created_at.desc()).limit(limit))
        return list(result.scalars().all())

    async def set_status(self, trip_id: UUID, status: TripStatus) -> None:
        """Update trip status when the trip exists."""

        trip = await self.get(trip_id)
        if trip is not None:
            trip.status = status
            await self.session.flush()


class BookingRepository(AsyncRepository[Booking]):
    """Repository for booking persistence."""

    model = Booking

    async def create_pending(
        self,
        trip_id: UUID,
        booking_type: str,
        provider: str,
        payload: dict,
    ) -> Booking:
        """Create a pending booking record for a provider request."""

        booking = Booking(
            trip_id=trip_id,
            booking_type=booking_type,
            provider=provider,
            status=BookingStatus.PENDING,
            payload=payload,
        )
        return await self.add(booking)
