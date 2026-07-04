import uuid
from contextlib import asynccontextmanager
from typing import Any

import structlog
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response

from app.api.v1 import analytics, notifications, preferences, webhooks
from app.core.config import settings
from app.core.exceptions import (
    ConflictError,
    NotFoundError,
    RateLimitError,
    ValidationError,
    conflict_handler,
    not_found_handler,
    rate_limit_handler,
    validation_error_handler,
)
from app.core.logging import setup_logging
from app.core.metrics import get_all_metrics

setup_logging()
logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("startup", env=settings.APP_ENV)
    yield
    logger.info("shutdown")


app = FastAPI(
    title="Notification Service",
    description="Multi-channel notification service with priority queue, retry, and idempotency.",
    version="1.0.0",
    lifespan=lifespan,
)

# Exception handlers
app.add_exception_handler(NotFoundError, not_found_handler)
app.add_exception_handler(ConflictError, conflict_handler)
app.add_exception_handler(ValidationError, validation_error_handler)
app.add_exception_handler(RateLimitError, rate_limit_handler)


@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(correlation_id=correlation_id)
    response = await call_next(request)
    response.headers["X-Correlation-ID"] = correlation_id
    return response


@app.get("/health", tags=["Health"])
async def health() -> dict:
    return {"status": "ok", "service": "notification-service", "version": "1.0.0"}


@app.get("/metrics", tags=["Observability"])
async def metrics() -> Response:
    metrics_text = await get_all_metrics()
    return Response(content=metrics_text, media_type="text/plain")


app.include_router(notifications.router, prefix="/api/v1", tags=["Notifications"])
app.include_router(preferences.router, prefix="/api/v1", tags=["Preferences"])
app.include_router(webhooks.router, prefix="/api/v1", tags=["Webhooks"])
app.include_router(analytics.router, prefix="/api/v1", tags=["Analytics"])

