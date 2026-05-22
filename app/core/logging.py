import logging
import sys
from typing import Any

try:
    import structlog
except ImportError:  # pragma: no cover - used only in dependency-light local environments
    structlog = None  # type: ignore[assignment]


class _StdlibStructuredLogger:
    """Small structlog-compatible fallback used when structlog is unavailable."""

    def __init__(self, name: str) -> None:
        """Create a stdlib logger wrapper for the given logger name."""

        self._logger = logging.getLogger(name)

    def info(self, event: str, **kwargs: Any) -> None:
        """Log an informational structured event."""

        self._logger.info("%s %s", event, kwargs)

    def warning(self, event: str, **kwargs: Any) -> None:
        """Log a warning structured event."""

        self._logger.warning("%s %s", event, kwargs)

    def error(self, event: str, **kwargs: Any) -> None:
        """Log an error structured event."""

        self._logger.error("%s %s", event, kwargs)


def configure_logging(debug: bool = False) -> None:
    """Configure JSON structured logging for the process."""

    if structlog is None:
        logging.basicConfig(
            format="%(asctime)s %(levelname)s %(name)s %(message)s",
            stream=sys.stdout,
            level=logging.DEBUG if debug else logging.INFO,
        )
        return

    timestamper = structlog.processors.TimeStamper(fmt="iso", utc=True)
    processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        timestamper,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer(),
    ]

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=logging.DEBUG if debug else logging.INFO,
    )
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> Any:
    """Return a structured logger or a stdlib fallback logger."""

    if structlog is None:
        return _StdlibStructuredLogger(name)
    return structlog.get_logger(name)
