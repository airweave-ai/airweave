"""Middleware for the FastAPI application.

This module contains middleware that process requests and responses.
"""

import asyncio
import time
import traceback
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable

from fastapi import Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from starlette.middleware.base import BaseHTTPMiddleware

from airweave.api.context import ApiContext
from airweave.core.config import settings
from airweave.core.exceptions import (
    AirweaveException,
    InvalidStateError,
    NotFoundException,
    PermissionException,
    RateLimitExceededException,
    TokenRefreshError,
    unpack_validation_error,
)
from airweave.core.logging import logger
from airweave.core.protocols import HttpMetrics


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


# Paths that are exempt from the request timeout (long-running operations)
TIMEOUT_EXEMPT_PATHS = [
    "/agentic-search",  # Agentic search involves multiple LLM calls
]


async def request_timeout_middleware(request: Request, call_next: callable) -> Response:
    """Middleware to enforce request timeout.

    Wraps request processing in asyncio.wait_for() to prevent long-running requests
    from tying up resources. Some paths are exempt from timeout (e.g., agentic search).

    Args:
    ----
        request (Request): The incoming request.
        call_next (callable): The next middleware in the chain.

    Returns:
    -------
        Response: The response to the incoming request or 504 on timeout.

    """
    # Check if this path is exempt from timeout
    path = request.url.path
    for exempt_path in TIMEOUT_EXEMPT_PATHS:
        if exempt_path in path:
            return await call_next(request)

    try:
        response = await asyncio.wait_for(
            call_next(request), timeout=settings.API_REQUEST_TIMEOUT_SECONDS
        )
        return response
    except asyncio.TimeoutError:
        logger.warning(
            f"Request timeout after {settings.API_REQUEST_TIMEOUT_SECONDS}s: "
            f"{request.method} {request.url}"
        )
        return JSONResponse(
            status_code=504,
            content={
                "detail": f"Request timeout after {settings.API_REQUEST_TIMEOUT_SECONDS} seconds"
            },
        )


async def request_body_size_middleware(request: Request, call_next: callable) -> Response:
    """Middleware to enforce request body size limit.

    Checks the Content-Length header and rejects requests exceeding the configured limit.
    This prevents large payloads from consuming excessive server resources.

    Args:
    ----
        request (Request): The incoming request.
        call_next (callable): The next middleware in the chain.

    Returns:
    -------
        Response: The response to the incoming request or 413 if body is too large.

    """
    # Check Content-Length header if present
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            content_length_bytes = int(content_length)
            if content_length_bytes > settings.API_REQUEST_BODY_SIZE_LIMIT:
                max_size_mb = settings.API_REQUEST_BODY_SIZE_LIMIT / (1024 * 1024)
                actual_size_mb = content_length_bytes / (1024 * 1024)
                logger.warning(
                    f"Request body too large: {actual_size_mb:.2f}MB exceeds limit "
                    f"of {max_size_mb:.2f}MB for {request.method} {request.url}"
                )
                return JSONResponse(
                    status_code=413,
                    content={
                        "detail": (
                            f"Request body too large. Maximum size is {max_size_mb:.2f}MB, "
                            f"but request is {actual_size_mb:.2f}MB"
                        )
                    },
                )
        except ValueError:
            logger.warning(f"Invalid Content-Length header: {content_length}")

    return await call_next(request)


async def rate_limit_headers_middleware(request: Request, call_next: callable) -> Response:
    """Middleware to add rate limit headers to responses.

    Follows standards defined in RFC 6585.

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
    rate_limit_result = getattr(request.state, "rate_limit_result", None)
    if rate_limit_result:
        response.headers["RateLimit-Limit"] = str(rate_limit_result.limit)
        response.headers["RateLimit-Remaining"] = str(rate_limit_result.remaining)
        response.headers["RateLimit-Reset"] = str(int(time.time() + rate_limit_result.retry_after))

    return response


class DynamicCORSMiddleware(BaseHTTPMiddleware):
    """Middleware to dynamically update CORS origins based on configuration.

    Simple CORS handling that permits OPTIONS preflight requests and adds appropriate headers.
    """

    def __init__(self, app, default_origins: list[str]):
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
    request: Request, exc: RequestValidationError | ValidationError
) -> JSONResponse:
    """Exception handler for validation errors that occur during request processing.

    This handler captures exceptions raised due to request data not passing the schema validation.

    It improves the client's ability to understand what part of their request was invalid
    and why, facilitating easier debugging and correction.

    Args:
    ----
        request (Request): The incoming request that triggered the exception.
        exc (RequestValidationError | ValidationError): The exception object that was raised.
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
                "errors": error_messages["errors"],
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

    Maps exception types to HTTP status codes. Checks base classes first so that
    any new domain exception inheriting from BadRequestError, ConflictError, etc.
    is automatically mapped without needing to register it here.

    Note: NotFoundException and PermissionException have dedicated handlers
    registered before this one, so their subclasses won't reach here.
    """
    # Map — any domain exception inheriting from a mapped base class gets
    # the right status code automatically, no per-exception registration needed.
    # Add new base classes here as they're introduced (BadRequestError, etc.).
    status_map = {
        TokenRefreshError: 401,
    }

    for exc_type, code in status_map.items():
        if isinstance(exc, exc_type):
            return JSONResponse(status_code=code, content={"detail": str(exc)})

    # Default for unmapped AirweaveException subclasses
    return JSONResponse(status_code=500, content={"detail": str(exc)})


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
    reset_timestamp = int(time.time() + exc.retry_after)

    return JSONResponse(
        status_code=429,
        content={"detail": str(exc)},
        headers={
            "Retry-After": str(int(exc.retry_after) + 1),
            "RateLimit-Limit": str(exc.limit),
            "RateLimit-Remaining": str(exc.remaining),
            "RateLimit-Reset": str(reset_timestamp),
        },
    )


_METRICS_SKIP_PREFIXES = (
    "/health",
    "/metrics",
    "/docs",
    "/openapi.json",
    "/favicon.ico",
    "/redoc",
)
_METRICS_SKIP_EXACT = frozenset(_METRICS_SKIP_PREFIXES)
_METRICS_SKIP_SLASH = tuple(p + "/" for p in _METRICS_SKIP_PREFIXES)


async def http_metrics_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Middleware to record HTTP metrics (counts, latency, in-flight).

    Reads the ``HttpMetrics`` implementation from ``request.app.state.http_metrics``
    so the middleware is decoupled from any concrete metrics library.

    Streaming responses (no ``content-length`` header) are wrapped so that
    duration and response-size are recorded when the body stream finishes
    rather than when headers are sent.
    """
    path = request.url.path
    if path in _METRICS_SKIP_EXACT or path.startswith(_METRICS_SKIP_SLASH):
        return await call_next(request)

    metrics = request.app.state.http_metrics
    method = request.method
    metrics.inc_in_progress(method)
    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        metrics.dec_in_progress(method)
        raise

    endpoint = _build_endpoint_name(request, fallback="unmatched")
    content_length = response.headers.get("content-length")

    if content_length is not None:
        # Non-streaming: record immediately (existing behaviour).
        duration = time.perf_counter() - start
        metrics.dec_in_progress(method)
        metrics.observe_request(
            method=method,
            endpoint=endpoint,
            status_code=str(response.status_code),
            duration=duration,
        )
        metrics.observe_response_size(
            method=method,
            endpoint=endpoint,
            size=int(content_length),
        )
    else:
        # Streaming: defer recording until the body stream completes.
        response.body_iterator = _StreamingMetricsIterator(
            response.body_iterator,
            metrics=metrics,
            method=method,
            endpoint=endpoint,
            status_code=str(response.status_code),
            start=start,
        )

    return response


class _StreamingMetricsIterator:
    """Wrap a streaming body iterator to record metrics on completion.

    Accumulates total bytes while proxying chunks.  Cleanup runs in
    ``aclose()`` which ASGI servers call on iterator disposal — even
    when the body is never iterated or the client disconnects.
    """

    __slots__ = (
        "_body_iterator",
        "_inner_iter",
        "_metrics",
        "_method",
        "_endpoint",
        "_status_code",
        "_start",
        "_total_bytes",
        "_closed",
    )

    def __init__(
        self,
        body_iterator: AsyncIterator[bytes | str],
        *,
        metrics: HttpMetrics,
        method: str,
        endpoint: str,
        status_code: str,
        start: float,
    ) -> None:
        self._body_iterator = body_iterator
        self._inner_iter = body_iterator.__aiter__()
        self._metrics = metrics
        self._method = method
        self._endpoint = endpoint
        self._status_code = status_code
        self._start = start
        self._total_bytes = 0
        self._closed = False

    def __aiter__(self) -> "_StreamingMetricsIterator":
        return self

    async def __anext__(self) -> bytes | str:
        try:
            chunk = await self._inner_iter.__anext__()
        except StopAsyncIteration:
            await self.aclose()
            raise
        # BaseException is intentional: we must record metrics on
        # GeneratorExit (client disconnect) and CancelledError
        # (task cancellation), both BaseException subclasses.
        except BaseException:
            await self.aclose()
            raise

        if isinstance(chunk, str):
            self._total_bytes += len(chunk.encode("utf-8"))
        else:
            self._total_bytes += len(chunk)
        return chunk

    async def aclose(self) -> None:
        if self._closed:
            return
        self._closed = True

        duration = time.perf_counter() - self._start
        self._metrics.dec_in_progress(self._method)
        self._metrics.observe_request(
            method=self._method,
            endpoint=self._endpoint,
            status_code=self._status_code,
            duration=duration,
        )
        self._metrics.observe_response_size(
            method=self._method,
            endpoint=self._endpoint,
            size=self._total_bytes,
        )

        # Propagate close to the underlying iterator if possible.
        inner_close = getattr(self._body_iterator, "aclose", None)
        if inner_close is not None:
            await inner_close()


async def analytics_middleware(request: Request, call_next):
    """Track API calls automatically via middleware.

    Extracts context from request.state.api_context (set by deps.py) and tracks
    API calls with PostHog analytics including user_id, org_id, and request_id.
    """
    start_time = time.monotonic()

    if _should_skip_analytics(request):
        return await call_next(request)

    response = await call_next(request)

    duration_ms = (time.monotonic() - start_time) * 1000

    context = getattr(request.state, "api_context", None)
    if context:
        try:
            await _track_api_call_async(context, response, duration_ms, request)
        except Exception as e:
            logger.warning(f"Failed to track API analytics: {e}")

    return response


def _build_endpoint_name(request: Request, *, fallback: str | None = None) -> str:
    """Build endpoint name using FastAPI's route information.

    Uses the matched route path template from FastAPI, which already contains
    parameter placeholders like {uuid}, {readable_id}, etc.

    Args:
        request: The incoming request.
        fallback: Value to return when no route is matched.  Defaults to the
            raw request path (stripped of trailing slash).  The Prometheus
            middleware passes ``"unmatched"`` to cap label cardinality from
            404-scanning bots.

    Returns:
        str: endpoint_path_template like "/collections/{readable_id}/search"
    """
    # Get the matched route from FastAPI
    route = request.scope.get("route")

    if route and hasattr(route, "path"):
        # FastAPI provides the path template with {param} placeholders
        # e.g., "/collections/{readable_id}/sources/{source_short_name}"
        return route.path

    # Fallback to raw path if route not available (shouldn't happen in normal operation)
    return fallback if fallback is not None else request.url.path.rstrip("/")


def _should_skip_analytics(request: Request) -> bool:
    """Skip analytics for certain paths (including sub-paths)."""
    path = request.url.path
    return path in _METRICS_SKIP_EXACT or path.startswith(_METRICS_SKIP_SLASH)


async def _track_api_call_async(
    context: ApiContext, response: Response, duration_ms: float, request: Request
):
    """Track API call asynchronously.

    Uses the contextual analytics service from ApiContext which already has
    user/org/headers configured. This avoids duplication and ensures consistency.
    """
    # Build endpoint identifier from FastAPI route template
    endpoint = _build_endpoint_name(request)

    # Build properties specific to API calls
    # Note: auth_method, organization_name, and headers are automatically added
    # by the contextual analytics service
    properties = {
        "endpoint": endpoint,
        "request_method": request.method,
        "request_path": request.url.path,
        "status_code": response.status_code,
        "duration_ms": duration_ms,
    }

    # Flatten all path parameters directly into properties
    # Convert all values to strings to ensure JSON serialization works
    if request.path_params:
        properties.update({k: str(v) for k, v in request.path_params.items()})

    # Determine event name
    event_name = "api_call_error" if response.status_code >= 400 else "api_call"

    # Track event using contextual analytics service
    # This automatically adds: auth_method, organization_name, request_id,
    # user_agent, client_name, sdk_name, session_id, and other headers
    context.analytics.track_event(event_name, properties)
