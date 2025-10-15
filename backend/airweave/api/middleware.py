"""Middleware for the FastAPI application.

This module contains middleware that process requests and responses.
"""

import asyncio
import time
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
    InvalidStateError,
    MinuteLevelScheduleException,
    NotFoundException,
    PaymentRequiredException,
    PermissionException,
    RateLimitExceededException,
    ScheduleNotExistsException,
    ScheduleOperationException,
    SyncDagNotFoundException,
    SyncJobNotFoundException,
    SyncNotFoundException,
    TokenRefreshError,
    UsageLimitExceededException,
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


async def request_timeout_middleware(request: Request, call_next: callable) -> Response:
    """Middleware to enforce request timeout.

    Wraps request processing in asyncio.wait_for() to prevent long-running requests
    from tying up resources.

    Args:
    ----
        request (Request): The incoming request.
        call_next (callable): The next middleware in the chain.

    Returns:
    -------
        Response: The response to the incoming request or 504 on timeout.

    """
    try:
        response = await asyncio.wait_for(
            call_next(request), timeout=settings.REQUEST_TIMEOUT_SECONDS
        )
        return response
    except asyncio.TimeoutError:
        logger.warning(
            f"Request timeout after {settings.REQUEST_TIMEOUT_SECONDS}s: "
            f"{request.method} {request.url}"
        )
        return JSONResponse(
            status_code=504,
            content={"detail": f"Request timeout after {settings.REQUEST_TIMEOUT_SECONDS} seconds"},
        )


async def rate_limit_headers_middleware(request: Request, call_next: callable) -> Response:
    """Middleware to add rate limit headers to responses.

    Rate limiting is performed in deps.py and stored in request.state.
    This middleware just adds the headers to the response.

    Args:
    ----
        request (Request): The incoming request.
        call_next (callable): The next middleware in the chain.

    Returns:
    -------
        Response: The response with rate limit headers added.

    """
    response = await call_next(request)

    # Add rate limit headers if available from request state
    rate_limit_info = getattr(request.state, "rate_limit_info", None)
    if rate_limit_info:
        response.headers["RateLimit-Limit"] = str(rate_limit_info.get("limit", 0))
        response.headers["RateLimit-Remaining"] = str(rate_limit_info.get("remaining", 0))
        response.headers["RateLimit-Reset"] = str(
            rate_limit_info.get("reset", int(time.time() + 1))
        )

    return response


class DynamicCORSMiddleware(BaseHTTPMiddleware):
    """Middleware to dynamically update CORS origins based on configuration.

    Simple CORS handling that permits OPTIONS preflight requests and adds appropriate headers.
    """

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
            # Check if origin is allowed
            is_allowed_origin = origin in self.default_origins

            if is_allowed_origin:
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

        # Add CORS headers to the response for allowed origins
        is_allowed_origin = origin in self.default_origins

        if is_allowed_origin:
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
    logger.error(f"Validation error: {error_messages}")

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

    # Get status code from map, checking for subclasses
    # This ensures that subclasses of the mapped exceptions are properly handled
    status_code = 500  # default
    for exc_type, code in status_code_map.items():
        if isinstance(exc, exc_type):
            status_code = code
            break

    return JSONResponse(status_code=status_code, content={"detail": str(exc)})


async def payment_required_exception_handler(
    request: Request, exc: PaymentRequiredException
) -> JSONResponse:
    """Exception handler for PaymentRequiredException.

    Args:
    ----
        request (Request): The incoming request that triggered the exception.
        exc (PaymentRequiredException): The exception object that was raised.

    Returns:
    -------
        JSONResponse: A 400 Bad Request status response that details the error message.

    """
    return JSONResponse(status_code=400, content={"detail": str(exc)})


async def usage_limit_exceeded_exception_handler(
    request: Request, exc: UsageLimitExceededException
) -> JSONResponse:
    """Exception handler for UsageLimitExceededException.

    Args:
    ----
        request (Request): The incoming request that triggered the exception.
        exc (UsageLimitExceededException): The exception object that was raised.

    Returns:
    -------
        JSONResponse: A 400 Bad Request status response that details the error message.

    """
    return JSONResponse(status_code=400, content={"detail": str(exc)})


async def invalid_state_exception_handler(request: Request, exc: InvalidStateError) -> JSONResponse:
    """Exception handler for InvalidStateError.

    Args:
    ----
        request (Request): The incoming request that triggered the exception.
        exc (InvalidStateError): The exception object that was raised.

    Returns:
    -------
        JSONResponse: A 400 Bad Request status response that details the error message.

    """
    return JSONResponse(status_code=400, content={"detail": str(exc)})


async def rate_limit_exception_handler(
    request: Request, exc: RateLimitExceededException
) -> JSONResponse:
    """Exception handler for RateLimitExceededException.

    Args:
    ----
        request (Request): The incoming request that triggered the exception.
        exc (RateLimitExceededException): The exception object that was raised.

    Returns:
    -------
        JSONResponse: A 429 Too Many Requests status response with rate limit headers.

    """
    return JSONResponse(
        status_code=429,
        content={"detail": str(exc)},
        headers={
            "Retry-After": str(int(exc.retry_after) + 1),
            "RateLimit-Limit": str(exc.limit),
            "RateLimit-Remaining": str(exc.remaining),
            "RateLimit-Reset": str(int(time.time() + exc.retry_after)),
        },
    )
