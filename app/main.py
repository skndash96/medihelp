"""FastAPI application entry point for the elderly fall-alert system."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import models
from app.database import engine
from app.routers import alerts, pages

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    models.Base.metadata.create_all(bind=engine)
    logger.info("Database tables ensured")
    yield


app = FastAPI(
    title="Elderly Fall-Alert System",
    version="0.1.0",
    description=(
        "College-project prototype: receives fall alerts (PWA, web, future "
        "ESP32), stores them in SQLite and triggers Twilio SMS/voice alerts."
    ),
    lifespan=lifespan,
)

# CORS is permissive for local development. The PWA/admin use relative URLs
# (same origin) so this mainly helps when testing from another origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(alerts.router)
app.include_router(pages.router)


# --- Error handling --------------------------------------------------------

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    """Return clean JSON for Pydantic validation failures, no stack traces."""
    logger.warning("Validation error on %s: %s", request.url.path, exc)
    return JSONResponse(
        status_code=422,
        content={"error": True, "detail": "Invalid request input."},
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request, exc):
    """Return JSON for HTTP exceptions (including our 4xx errors)."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": True, "detail": exc.detail},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request, exc):
    """Never leak internals to the browser."""
    logger.error("Unhandled error on %s: %s", request.url.path, exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": True, "detail": "Internal server error."},
    )
