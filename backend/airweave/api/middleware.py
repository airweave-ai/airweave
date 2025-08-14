"""Middleware for the FastAPI application.

This module contains middleware that process requests and responses.
"""

import re
import traceback
import uuid
from typing import List, Union

from fastapi import Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from starlette.middleware.base import BaseHTTPMiddleware

from airweave.core.config import settings
from airweave.core.exceptions import (
    AirweaveException,
    CollectionNotFoundException,
    ImmutableFieldError,
    InvalidScheduleOperationException,
    MinuteLevelScheduleException,
    NotFoundException,
    PermissionException,
    ScheduleNotExistsException,
    ScheduleOperationException,
    SyncDagNotFoundException,
    SyncJobNotFoundException,
    SyncNotFoundException,
    TokenRefreshError,
    unpack_validation_error,
)
from airweave.core.logging import logger


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
    import time

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
        # Always log the full exception details
        logger.error(f"Unhandled exception: {exc}\n{traceback.format_exc()}")

        # Create error message with actual exception details
        error_message = f"Internal Server Error: {exc.__class__.__name__}: {str(exc)}"

        # Build response content
        response_content = {"detail": error_message}

        # Include stack trace only in development mode
        if settings.LOCAL_CURSOR_DEVELOPMENT or settings.DEBUG:
            response_content["trace"] = traceback.format_exc()

        return JSONResponse(status_code=500, content=response_content)


class DynamicCORSMiddleware(BaseHTTPMiddleware):
    """Middleware to dynamically update CORS origins based on configuration.

    Simple CORS handling that permits OPTIONS preflight requests and adds appropriate headers.
    White label endpoint authorization is handled separately in the endpoints.
    """

    # OAuth endpoint patterns that should always pass OPTIONS requests
    OAUTH_ENDPOINTS = [
        r"/white-labels/[^/]+/oauth2/auth_url",
        r"/white-labels/[^/]+/oauth2/code",
    ]
    OAUTH_PATTERNS = [re.compile(pattern) for pattern in OAUTH_ENDPOINTS]

    def __init__(self, app, default_origins: List[str]):
        """Initialize the middleware.

        Args:
            app: The FastAPI application
            default_origins: Default CORS origins to allow
        """
        super().__init__(app)
        self.default_origins = default_origins

    async def dispatch(self, request: Request, call_next):
        """Process the request and add dynamic CORS headers.

        Args:
            request: The incoming request
            call_next: The next middleware function to call

        Returns:
            The response with appropriate CORS headers
        """
        # Get origin from request headers
        origin = request.headers.get("origin")
        path = request.url.path

        # If no origin, no CORS headers needed
        if not origin:
            return await call_next(request)

        # Handle OPTIONS preflight requests - only if allowed
        if request.method == "OPTIONS":
            # Check if this is an OAuth endpoint that should always pass OPTIONS
            is_oauth_endpoint = any(pattern.match(path) for pattern in self.OAUTH_PATTERNS)

            # Other endpoints need to be either white-label endpoints or have allowed origin
            is_white_label_endpoint = "white-labels" in path
            is_allowed_origin = origin in self.default_origins

            if is_oauth_endpoint or is_white_label_endpoint or is_allowed_origin:
                # Create a response with appropriate CORS headers
                response = Response()
                response.headers["Access-Control-Allow-Origin"] = origin
                response.headers["Access-Control-Allow-Methods"] = (
                    "GET,POST,PUT,DELETE,OPTIONS,PATCH"
                )
                response.headers["Access-Control-Allow-Headers"] = "*"
                response.headers["Access-Control-Allow-Credentials"] = "true"
                logger.debug(f"Handled OPTIONS preflight for {path} from origin {origin}")
                return response
            else:
                # Not allowed, return 403
                logger.debug(
                    f"Rejected OPTIONS preflight for {path} from disallowed origin {origin}"
                )
                return Response(status_code=403)

        # For non-OPTIONS requests, process the request
        response = await call_next(request)

        # Add CORS headers to the response for allowed origins or white-label endpoints
        is_oauth_endpoint = any(pattern.match(path) for pattern in self.OAUTH_PATTERNS)
        is_white_label_endpoint = "white-labels" in path
        is_allowed_origin = origin in self.default_origins

        if is_oauth_endpoint or is_white_label_endpoint or is_allowed_origin:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
            logger.debug(f"Added CORS headers for origin {origin}")

        return response


# Exception handlers
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


async def airweave_exception_handler(request: Request, exc: AirweaveException) -> JSONResponse:
    """Generic exception handler for all AirweaveException types.

    Maps different exception types to appropriate HTTP status codes based on their semantic meaning.

    Args:
    ----
        request (Request): The incoming request that triggered the exception.
        exc (AirweaveException): The exception object that was raised.

    Returns:
    -------
        JSONResponse: HTTP response with appropriate status code and error details.
    """
    # Map exception types to HTTP status codes
    status_code_map = {
        # 404 Not Found - Resource doesn't exist
        SyncNotFoundException: 404,
        SyncJobNotFoundException: 404,
        SyncDagNotFoundException: 404,
        CollectionNotFoundException: 404,
        # 400 Bad Request - Client error
        InvalidScheduleOperationException: 400,
        ScheduleNotExistsException: 400,
        ImmutableFieldError: 400,
        # 401 Unauthorized - Authentication issues
        TokenRefreshError: 401,
        # 403 Forbidden - Permission issues (already handled by permission_exception_handler)
        PermissionException: 403,
        # 500 Internal Server Error - Server/operation failures
        MinuteLevelScheduleException: 500,
        ScheduleOperationException: 500,
    }

    # Get status code from map, default to 500 for unknown exceptions
    status_code = status_code_map.get(type(exc), 500)

    return JSONResponse(status_code=status_code, content={"detail": str(exc)})
