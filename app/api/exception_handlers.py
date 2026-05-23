from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.exceptions import AppError
from app.core.logging import get_logger

logger = get_logger(__name__)


def register_exception_handlers(app: FastAPI) -> None:
    """Attach named exception handlers to the FastAPI application."""

    app.add_exception_handler(AppError, handle_app_error)
    app.add_exception_handler(RequestValidationError, handle_request_validation_error)
    app.add_exception_handler(StarletteHTTPException, handle_http_exception)
    app.add_exception_handler(Exception, handle_unexpected_error)


async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
    """Render domain exceptions as stable JSON API errors."""

    logger.warning("app.error", code=exc.code, message=exc.message, path=request.url.path)
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": exc.message, "details": exc.details or {}}},
    )


async def handle_request_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Render FastAPI/Pydantic validation failures with a named error code."""

    logger.warning("request.validation_error", path=request.url.path, errors=exc.errors())
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "request_validation_error",
                "message": "Request validation failed",
                "details": {"errors": exc.errors()},
            }
        },
    )


async def handle_http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Render framework HTTP exceptions in the platform error envelope."""

    logger.warning("http.error", status_code=exc.status_code, detail=exc.detail, path=request.url.path)
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": "http_error",
                "message": str(exc.detail),
                "details": {},
            }
        },
    )


async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    """Render uncaught exceptions without leaking internal implementation details."""

    logger.error("unexpected.error", path=request.url.path, error=str(exc))
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "internal_server_error",
                "message": "An unexpected error occurred",
                "details": {},
            }
        },
    )
