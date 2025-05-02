"""Main module of the FastAPI application.

This module sets up the FastAPI application and the middleware to log incoming requests
and unhandled exceptions.
"""

import subprocess
import time
import traceback
import uuid
from contextlib import asynccontextmanager
from typing import Union

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import ValidationError
from starlette.middleware.cors import CORSMiddleware

from airweave.api.router import TrailingSlashRouter
from airweave.api.v1.api import api_router
from airweave.core.config import settings
from airweave.core.exceptions import NotFoundException, PermissionException, unpack_validation_error
from airweave.core.logging import logger
from airweave.db.init_db import init_db
from airweave.db.session import AsyncSessionLocal
from airweave.platform.db_sync import sync_platform_components
from airweave.platform.entities._base import ensure_file_entity_models
from airweave.platform.scheduler import platform_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    # Startup
    async with AsyncSessionLocal() as db:
        if settings.RUN_ALEMBIC_MIGRATIONS:
            logger.info("Running alembic migrations...")
            subprocess.run(["alembic", "upgrade", "head"], check=True)
        if settings.RUN_DB_SYNC:
            # Ensure all FileEntity subclasses have their parent and chunk models created
            ensure_file_entity_models()
            await sync_platform_components("airweave/platform", db)
        await init_db(db)

    # Start the sync scheduler
    await platform_scheduler.start()

    yield

    # Shutdown
    # Stop the sync scheduler
    await platform_scheduler.stop()


# Create FastAPI app with our custom router and disable FastAPI's built-in redirects
app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url="/openapi.json",
    lifespan=lifespan,
    router=TrailingSlashRouter(),
    redirect_slashes=False,  # Critical: disable FastAPI's built-in slash redirects
)

app.include_router(api_router)


@app.middleware("http")
async def add_request_id(request: Request, call_next: callable) -> Response:
    """Middleware to generate and add a request ID to the request for tracing.

    Args:
    ----
        request (Request): The incoming request.
        call_next (callable): The next middleware in the chain.

    Returns:
    -------
        Response: The response to the incoming request.

    """
    request.state.request_id = str(uuid.uuid4())
    return await call_next(request)


@app.middleware("http")
async def log_requests(request: Request, call_next: callable) -> Response:
    """Middleware to log incoming requests.

    Args:
    ----
        request (Request): The incoming request.
        call_next (callable): The next middleware in the chain.

    Returns:
    -------
        Response: The response to the incoming request.

    """
    start_time = time.time()
    response = await call_next(request)
    duration = time.time() - start_time
    logger.info(
        (
            f"Handled request {request.method} {request.url} in {duration:.2f} seconds."
            f"Response code: {response.status_code}"
        )
    )
    return response


@app.middleware("http")
async def exception_logging_middleware(request: Request, call_next: callable) -> Response:
    """Middleware to log unhandled exceptions.

    Args:
    ----
        request (Request): The incoming request.
        call_next (callable): The next middleware in the chain.

    Returns:
    -------
        Response: The response to the incoming request.

    """
    try:
        response = await call_next(request)
        return response
    except Exception as exc:
        if settings.LOCAL_CURSOR_DEVELOPMENT:
            logger.error(f"Unhandled exception: {exc}\n{traceback.format_exc()}")
        else:
            logger.error(f"Unhandled exception: {exc}")
        return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})


@app.exception_handler(RequestValidationError)
@app.exception_handler(ValidationError)
async def validation_exception_handler(
    request: Request, exc: Union[RequestValidationError, ValidationError]
) -> JSONResponse:
    """Exception handler for validation errors that occur during request processing.

    This handler captures exceptions raised due to request data not passing the schema validation.

    It improves the client's ability to understand what part of their request was invalid
    and why, facilitating easier debugging and correction.

    Args:
    ----
        request (Request): The incoming request that triggered the exception.
        exc (Union[RequestValidationError, ValidationError]): The exception object that was raised.
            This can either be a RequestValidationError for request body/schema validation issues,
            or a ValidationError for other data model validations within FastAPI.

    Returns:
    -------
        JSONResponse: A 422 Unprocessable Entity status response that details the validation
            errors. Each error message is a dictionary where the key is the location
            of the validation error in the request, and the value is the associated error message.

    Example of JSON output:
        {
            "errors": [
                {"body.email": "field required"},
                {"body.age": "value is not a valid integer"}
            ],
            "source": "RequestValidationError",
            "request_path": "/api/users",
            "request_method": "POST",
            "schema_info": {
                "name": "UserCreate",
                "module": "airweave.schemas.user",
                "file_path": "/airweave/schemas/user.py"
            },
            "validation_context": [
                "airweave.api.v1.endpoints.users:create_user:42",
                "airweave.schemas.user:UserCreate:15"
            ]
        }

    """
    # Extract basic error messages
    error_messages = unpack_validation_error(exc)

    if settings.LOCAL_CURSOR_DEVELOPMENT:
        # Additional diagnostic information
        exception_type = exc.__class__.__name__
        exception_str = str(exc)
        class_name = exception_str.split("\n")[0].split(" ")[-1]

        # Extract a simplified stack trace focusing on schema validation
        stack_trace = []
        if hasattr(exc, "__traceback__") and exc.__traceback__ is not None:
            stack_frames = traceback.extract_tb(exc.__traceback__)

            # Create a simplified version for the response
            for frame in stack_frames:
                # Only include frames from our backend code
                if "site-packages" not in frame.filename and "/airweave" in frame.filename:
                    context = f"{frame.filename.split('/')[-1]}:{frame.name}:{frame.lineno}"
                    stack_trace.append(context)

        return JSONResponse(
            status_code=422,
            content={
                "class_name": class_name,
                "stack_trace": stack_trace,
                "type": exception_type,
                "error_messages": error_messages,
            },
        )
    logger.error(f"Validation error: {error_messages}")

    return JSONResponse(status_code=422, content=error_messages)


@app.exception_handler(PermissionException)
async def permission_exception_handler(request: Request, exc: PermissionException) -> JSONResponse:
    """Exception handler for PermissionException.

    Args:
    ----
        request (Request): The incoming request that triggered the exception.
        exc (PermissionException): The exception object that was raised.

    Returns:
    -------
        JSONResponse: A 403 Forbidden status response that details the error message.

    """
    return JSONResponse(status_code=403, content={"detail": str(exc)})


@app.exception_handler(NotFoundException)
async def not_found_exception_handler(request: Request, exc: NotFoundException) -> JSONResponse:
    """Exception handler for NotFoundException.

    Args:
    ----
        request (Request): The incoming request that triggered the exception.
        exc (NotFoundException): The exception object that was raised.

    Returns:
    -------
        JSONResponse: A 404 Not Found status response that details the error message.

    """
    return JSONResponse(status_code=404, content={"detail": str(exc)})


CORS_ORIGINS = [
    "http://localhost:5173",
    "localhost:8001",
    "http://localhost:8080",
    "https://app.dev-airweave.com",
    "https://app.stg-airweave.com",
    "https://app.airweave.ai",
    "https://docs.airweave.ai",
]

if settings.ADDITIONAL_CORS_ORIGINS:
    additional_origins = settings.ADDITIONAL_CORS_ORIGINS.split(",")
    CORS_ORIGINS.extend(additional_origins)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
