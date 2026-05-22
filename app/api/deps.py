from collections.abc import AsyncIterator

from fastapi import Depends, Header
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.security import Role, decode_access_token
from app.db.session import get_db_session
from app.memory.redis import get_redis


async def get_current_roles(
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> list[Role]:
    """Resolve current request roles from an optional bearer token."""

    if not authorization:
        return [Role.USER]
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return [Role.USER]
    payload = decode_access_token(settings, token)
    return [Role(role) for role in payload.get("roles", [Role.USER.value])]


async def get_travel_service(
    session: AsyncSession = Depends(get_db_session),
    redis: Redis = Depends(get_redis),
    settings: Settings = Depends(get_settings),
) -> AsyncIterator:
    """Provide a request-scoped travel planning service."""

    from app.services.travel_service import TravelPlanningService

    yield TravelPlanningService(session=session, redis=redis, settings=settings)


async def get_booking_service(
    session: AsyncSession = Depends(get_db_session),
    redis: Redis = Depends(get_redis),
    settings: Settings = Depends(get_settings),
) -> AsyncIterator:
    """Provide a request-scoped booking service."""

    from app.services.booking_service import BookingService

    yield BookingService(session=session, redis=redis, settings=settings)
