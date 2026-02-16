"""Main module of the FastAPI application.

This module sets up the FastAPI application and the middleware to log incoming requests
and unhandled exceptions.
"""

import os
import subprocess
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse
from pydantic import ValidationError

from airweave.api.middleware import (
    DynamicCORSMiddleware,
    add_request_id,
    airweave_exception_handler,
    analytics_middleware,
    exception_logging_middleware,
    invalid_state_exception_handler,
    log_requests,
    not_found_exception_handler,
    payment_required_exception_handler,
    permission_exception_handler,
    rate_limit_exception_handler,
    rate_limit_headers_middleware,
    request_body_size_middleware,
    request_timeout_middleware,
    usage_limit_exceeded_exception_handler,
    validation_exception_handler,
)
from airweave.api.router import TrailingSlashRouter
from airweave.api.v1.api import api_router
from airweave.core.config import settings
from airweave.core.embedding_validation import validate_and_raise
from airweave.core.exceptions import (
    AirweaveException,
    InvalidStateError,
    NotFoundException,
    PaymentRequiredException,
    PermissionException,
    RateLimitExceededException,
    UsageLimitExceededException,
)
from airweave.core.logging import logger
from airweave.db.init_db import init_db
from airweave.db.session import AsyncSessionLocal
from airweave.platform.db_sync import sync_platform_components


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events.

    Initializes the DI container, runs alembic migrations, and syncs platform components.
    """
    # Initialize the dependency injection container (fail fast if wiring is broken)
    from airweave.core import container as container_mod
    from airweave.core.container import initialize_container

    logger.info("Initializing dependency injection container...")
    initialize_container(settings)
    logger.info("Container initialized successfully")

    # Initialize converters with OCR from the container
    from airweave.platform.converters import initialize_converters

    initialize_converters(ocr_provider=container_mod.container.ocr_provider)

    async with AsyncSessionLocal() as db:
        if settings.RUN_ALEMBIC_MIGRATIONS:
            logger.info("Running alembic migrations...")
            env = os.environ.copy()
            backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            env["PYTHONPATH"] = backend_dir
            subprocess.run(
                [sys.executable, "-m", "alembic", "upgrade", "heads"],
                check=True,
                cwd=backend_dir,
                env=env,
            )
        if settings.RUN_DB_SYNC:
            await sync_platform_components(db)
        await init_db(db)

    # Validate embedding stack configuration (raises if misconfigured)
    validate_and_raise()

    # Initialize cleanup schedule for stuck sync jobs (if Temporal is enabled)
    if settings.TEMPORAL_ENABLED:
        try:
            from airweave.platform.temporal.schedule_service import temporal_schedule_service

            logger.info("Initializing cleanup schedule for stuck sync jobs...")
            await temporal_schedule_service.create_cleanup_schedule()
            logger.info("Cleanup schedule initialized successfully")
        except Exception as e:
            logger.warning(
                f"Failed to initialize cleanup schedule (Temporal may not be available): {e}"
            )

        # Initialize API key expiration notification schedule
        try:
            logger.info("Initializing API key expiration notification schedule...")
            await temporal_schedule_service.create_api_key_notification_schedule()
            logger.info("API key notification schedule initialized successfully")
        except Exception as e:
            logger.warning(
                f"Failed to initialize API key notification schedule "
                f"(Temporal may not be available): {e}"
            )

    yield


# Create FastAPI app with our custom router and disable FastAPI's built-in redirects
app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url="/openapi.json",
    lifespan=lifespan,
    router=TrailingSlashRouter(),
    redirect_slashes=False,  # Critical: disable FastAPI's built-in slash redirects
)

app.include_router(api_router)

# Register middleware directly in the correct order
# Order matters: first registered = outermost middleware (processes request first)
app.middleware("http")(add_request_id)
app.middleware("http")(request_body_size_middleware)
app.middleware("http")(request_timeout_middleware)
app.middleware("http")(rate_limit_headers_middleware)
app.middleware("http")(log_requests)
app.middleware("http")(analytics_middleware)
app.middleware("http")(exception_logging_middleware)

# Register exception handlers
app.exception_handler(RequestValidationError)(validation_exception_handler)
app.exception_handler(ValidationError)(validation_exception_handler)
app.exception_handler(PermissionException)(permission_exception_handler)
app.exception_handler(NotFoundException)(not_found_exception_handler)
app.exception_handler(PaymentRequiredException)(payment_required_exception_handler)
app.exception_handler(UsageLimitExceededException)(usage_limit_exceeded_exception_handler)
app.exception_handler(RateLimitExceededException)(rate_limit_exception_handler)
app.exception_handler(InvalidStateError)(invalid_state_exception_handler)

# Register custom Airweave exception handlers
app.exception_handler(AirweaveException)(airweave_exception_handler)

# Default CORS origins - white labels and environment variables can extend this
CORS_ORIGINS = [
    "http://localhost:5173",
    "localhost:8001",
    "http://localhost:8080",
    "https://app.dev-airweave.com",
    "https://app.stg-airweave.com",
    "https://app.airweave.ai",
    "https://docs.airweave.ai",
    "localhost:3000",
]

if settings.ADDITIONAL_CORS_ORIGINS:
    additional_origins = settings.ADDITIONAL_CORS_ORIGINS.split(",")
    if settings.ENVIRONMENT == "local":
        CORS_ORIGINS.append("*")  # Allow all origins in local environment
    else:
        CORS_ORIGINS.extend(additional_origins)

# Add the dynamic CORS middleware that handles both default origins and white label specific origins
app.add_middleware(
    DynamicCORSMiddleware,
    default_origins=CORS_ORIGINS,
)


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def show_docs_reference() -> HTMLResponse:
    """Root endpoint to display the API documentation.

    Returns:
    -------
        HTMLResponse: The HTML content to display the API documentation.

    """
    html_content = """
<!DOCTYPE html>
<html>
    <head>
        <title>Airweave API</title>
    </head>
    <body>
        <h1>Welcome to the Airweave API</h1>
        <p>Please visit the <a href="https://docs.airweave.ai">docs</a> for more information.</p>
    </body>
</html>
    """
    return HTMLResponse(content=html_content)
