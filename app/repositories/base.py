from typing import Generic, TypeVar
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class AsyncRepository(Generic[ModelT]):
    """Generic async repository with common persistence operations."""

    model: type[ModelT]

    def __init__(self, session: AsyncSession) -> None:
        """Store the request-scoped database session."""

        self.session = session

    async def get(self, entity_id: UUID) -> ModelT | None:
        """Fetch one entity by primary key."""

        return await self.session.get(self.model, entity_id)

    async def add(self, entity: ModelT) -> ModelT:
        """Add an entity to the session and flush it."""

        self.session.add(entity)
        await self.session.flush()
        return entity
