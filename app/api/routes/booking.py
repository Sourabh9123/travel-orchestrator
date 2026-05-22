from fastapi import APIRouter, Depends

from app.api.deps import get_booking_service
from app.schemas.travel import BookingRequest
from app.services.booking_service import BookingService

router = APIRouter(prefix="/booking", tags=["booking"])


@router.post("/flight", status_code=202)
async def book_flight(
    request: BookingRequest,
    service: BookingService = Depends(get_booking_service),
) -> dict:
    """Create a pending flight booking request."""

    return await service.create_booking("flight", request)


@router.post("/hotel", status_code=202)
async def book_hotel(
    request: BookingRequest,
    service: BookingService = Depends(get_booking_service),
) -> dict:
    """Create a pending hotel booking request."""

    return await service.create_booking("hotel", request)
