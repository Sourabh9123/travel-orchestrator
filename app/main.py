from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from time import perf_counter

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.api.exception_handlers import register_exception_handlers
from app.api.routes import booking, health, travel
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.monitoring.metrics import API_LATENCY
from app.monitoring.tracing import configure_tracing

settings = get_settings()
configure_logging(settings.debug)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage application startup and shutdown lifecycle events."""

    logger.info("app.starting", app=settings.app_name, environment=settings.environment)
    yield
    logger.info("app.stopping", app=settings.app_name)


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    debug=settings.debug,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
configure_tracing(app, settings)
register_exception_handlers(app)


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    """Record Prometheus latency metrics for every HTTP request."""

    start = perf_counter()
    response = await call_next(request)
    latency = perf_counter() - start
    API_LATENCY.labels(request.method, request.url.path, response.status_code).observe(latency)
    return response


@app.get("/metrics", include_in_schema=False)
async def metrics() -> Response:
    """Expose Prometheus metrics for scraping."""

    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


app.include_router(health.router)
app.include_router(travel.router, prefix=settings.api_prefix)
app.include_router(booking.router, prefix=settings.api_prefix)
