import asyncio

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger

settings = get_settings()
configure_logging(settings.debug)
logger = get_logger(__name__)


async def main() -> None:
    logger.info("worker.started", queue="travel-workflows")
    while True:
        await asyncio.sleep(60)


if __name__ == "__main__":
    asyncio.run(main())
