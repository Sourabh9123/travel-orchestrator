import asyncio
from collections.abc import AsyncIterator

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.core.exceptions import ExternalServiceError
from app.core.logging import get_logger

settings = get_settings()
logger = get_logger(__name__)
engine = create_async_engine(str(settings.database_url), pool_pre_ping=True, future=True)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_db_session() -> AsyncIterator[AsyncSession]:
    """Yield an async SQLAlchemy session after the database is reachable."""

    await wait_for_database()
    async with async_session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def wait_for_database() -> None:
    """Wait briefly for PostgreSQL DNS and connectivity to become available."""

    last_error: Exception | None = None
    for attempt in range(1, settings.db_connect_retry_attempts + 1):
        try:
            async with engine.connect():
                return
        except (OSError, SQLAlchemyError) as exc:
            last_error = exc
            logger.warning(
                "database.connection_retry",
                attempt=attempt,
                max_attempts=settings.db_connect_retry_attempts,
                error=str(exc),
            )
            await asyncio.sleep(settings.db_connect_retry_delay_seconds)
    raise ExternalServiceError(
        "Database is not reachable",
        details={"host": settings.postgres_host, "port": settings.postgres_port},
    ) from last_error
