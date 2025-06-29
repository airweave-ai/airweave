"""Exception handling middleware for FastAPI.

This middleware provides centralized error handling for the API,
ensuring consistent error responses and proper logging.
"""

import time
import traceback
from typing import Callable, Dict, Any, Optional

from fastapi import FastAPI, Request, Response, status
from fastapi.responses import JSONResponse
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

from airweave.core.exceptions import (
    ErrorCode,
    StandardizedError, 
    PermissionException,
    NotFoundException,
    ImmutableFieldError, 
    TokenRefreshError,
)
from airweave.core.logging import logger


error_logger = logger.with_prefix("Error Handler: ")


async def log_request_details(request: Request) -> Dict[str, Any]:
    """Log details about the request that caused an error.
    
    Args:
        request: The FastAPI request object
        
    Returns:
        Dictionary with request information
    """
    request_info = {
        "method": request.method,
        "url": str(request.url),
        "headers": dict(request.headers),
        "client_host": request.client.host if request.client else None,
    }
    
    try:
        # Try to get the request body, but don't fail if it can't be read
        body = await request.body()
        if body:
            # Limit body size in logs to avoid huge log entries
            request_info["body"] = str(body)[:1000] + "..." if len(body) > 1000 else str(body)
    except Exception:
        request_info["body"] = "<unavailable>"
    
    return request_info


async def handle_standardized_error(
    request: Request, exc: StandardizedError
) -> JSONResponse:
    """Handle errors derived from StandardizedError.
    
    Args:
        request: The FastAPI request object
        exc: The standardized error
        
    Returns:
        JSONResponse with appropriate status code and error details
    """
    # Log the error with context
    request_details = await log_request_details(request)
    
    error_logger.error(
        f"{exc.error_code}: {exc.message}",
        extra={
            "request": request_details,
            "error_details": exc.details,
            "status_code": exc.status_code,
            "traceback": traceback.format_exc(),
        },
    )
    
    # Return the formatted error response
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.to_dict(),
    )


async def handle_validation_error(
    request: Request, exc: PydanticValidationError
) -> JSONResponse:
    """Handle Pydantic validation errors.
    
    Args:
        request: The FastAPI request object
        exc: The validation error
        
    Returns:
        JSONResponse with appropriate status code and error details
    """
    # Format field errors
    field_errors = {}
    for error in exc.errors():
        field = ".".join(str(loc) for loc in error["loc"])
        message = error["msg"]
        field_errors[field] = message
    
    # Log the validation error
    request_details = await log_request_details(request)
    error_logger.warning(
        f"Validation error: {len(field_errors)} field errors",
        extra={
            "request": request_details,
            "field_errors": field_errors,
        },
    )
    
    # Return formatted validation error response
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": {
                "code": ErrorCode.VALIDATION_INVALID_INPUT,
                "message": "Validation error",
                "details": {
                    "field_errors": field_errors,
                },
            }
        },
    )


async def handle_sqlalchemy_error(
    request: Request, exc: SQLAlchemyError
) -> JSONResponse:
    """Handle SQLAlchemy errors.
    
    Args:
        request: The FastAPI request object
        exc: The SQLAlchemy error
        
    Returns:
        JSONResponse with appropriate status code and error details
    """
    request_details = await log_request_details(request)
    
    # Different handling based on error type
    if isinstance(exc, IntegrityError):
        error_code = ErrorCode.RESOURCE_ALREADY_EXISTS
        message = "Database integrity error"
        status_code = status.HTTP_409_CONFLICT
    else:
        error_code = ErrorCode.INFRA_DATABASE_ERROR
        message = "Database error"
        status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    
    # Log database error with full traceback
    error_logger.error(
        f"Database error: {str(exc)}",
        extra={
            "request": request_details,
            "error_type": exc.__class__.__name__,
            "traceback": traceback.format_exc(),
        },
    )
    
    # Return standardized error response
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": error_code,
                "message": message,
                "details": {
                    "error": str(exc),
                }
            }
        },
    )


async def handle_generic_error(
    request: Request, exc: Exception
) -> JSONResponse:
    """Handle generic Python exceptions.
    
    Args:
        request: The FastAPI request object
        exc: The exception
        
    Returns:
        JSONResponse with appropriate status code and error details
    """
    request_details = await log_request_details(request)
    
    # Log unexpected error with full stack trace
    error_logger.error(
        f"Unexpected error: {str(exc)}",
        extra={
            "request": request_details,
            "error_type": exc.__class__.__name__,
            "traceback": traceback.format_exc(),
        },
    )
    
    # Return a generic server error response
    # We don't want to leak internal error details to clients
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": ErrorCode.SERVER_INTERNAL_ERROR,
                "message": "An unexpected error occurred",
                # No detailed error info for security reasons
                "details": {"error_id": str(int(time.time()))}
            }
        },
    )


def add_error_handlers(app: FastAPI) -> None:
    """Add exception handlers to FastAPI app.
    
    Args:
        app: The FastAPI application
    """
    # Handle our standardized exceptions
    app.add_exception_handler(StandardizedError, handle_standardized_error)
    app.add_exception_handler(PermissionException, handle_standardized_error)
    app.add_exception_handler(NotFoundException, handle_standardized_error)
    app.add_exception_handler(ImmutableFieldError, handle_standardized_error)
    app.add_exception_handler(TokenRefreshError, handle_standardized_error)
    
    # Handle Pydantic validation errors
    app.add_exception_handler(PydanticValidationError, handle_validation_error)
    
    # Handle database errors
    app.add_exception_handler(SQLAlchemyError, handle_sqlalchemy_error)
    app.add_exception_handler(IntegrityError, handle_sqlalchemy_error)
    
    # Fallback handler for all other exceptions
    app.add_exception_handler(Exception, handle_generic_error)
    
    error_logger.info("Error handlers registered for FastAPI application")


class ExceptionMiddleware:
    """Middleware for handling exceptions from FastAPI.
    
    This middleware adds additional logging and context for exceptions
    that occur during request processing.
    """
    
    def __init__(self, app: FastAPI):
        """Initialize the exception middleware.
        
        Args:
            app: The FastAPI application
        """
        self.app = app
    
    async def __call__(self, scope, receive, send):
        """ASGI callable implementation.
        
        Args:
            scope: The ASGI connection scope
            receive: The ASGI receive channel
            send: The ASGI send channel
        """
        if scope["type"] != "http":
            # We only handle HTTP requests
            await self.app(scope, receive, send)
            return
            
        # Create a request object for logging purposes
        request = Request(scope=scope, receive=receive)
        
        # Track request timing
        start_time = time.time()
        
        # Override the send function to add error handling
        original_send = send
        
        # Create a wrapper around send to intercept responses
        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                # Check if the response is an error (status >= 400)
                status_code = message["status"]
                duration = time.time() - start_time
                
                if status_code >= 400:
                    # Log information about the error response
                    request_info = await log_request_details(request)
                    error_logger.info(
                        f"Error response: {status_code}",
                        extra={
                            "request": request_info,
                            "status_code": status_code,
                            "duration": duration,
                        }
                    )
                    
            # Pass the message to the original send function
            await original_send(message)
        
        # Call the app with our wrapped send function
        try:
            await self.app(scope, receive, send_wrapper)
        except Exception as exc:
            # This is a fallback in case something bypasses FastAPI's exception handlers
            request_info = await log_request_details(request)
            error_logger.critical(
                f"Unhandled exception in ASGI middleware: {str(exc)}",
                extra={
                    "request": request_info,
                    "error_type": exc.__class__.__name__,
                    "traceback": traceback.format_exc(),
                }
            )
            # Re-raise to let the underlying ASGI server handle it
            raise