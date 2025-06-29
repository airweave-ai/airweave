"""Utilities for consistent error handling.

This module provides functions and decorators to help maintain
consistent error handling throughout the application.
"""

import functools
import inspect
import traceback
from typing import Any, Callable, Dict, Optional, Type, TypeVar, cast

from fastapi import HTTPException, status

from airweave.core.exceptions import (
    ErrorCode,
    StandardizedError,
    PermissionException, 
    NotFoundException,
    ValidationError,
    IntegrationError,
    ServerError,
)
from airweave.core.logging import logger

error_logger = logger.with_prefix("Error Handling: ")

F = TypeVar("F", bound=Callable[..., Any])


def with_error_handling(
    error_map: Optional[Dict[Type[Exception], Type[StandardizedError]]] = None,
) -> Callable[[F], F]:
    """Decorator to standardize error handling in service methods.
    
    This decorator catches exceptions and converts them to StandardizedError
    instances based on the provided error_map. If no mapping exists for a
    particular exception, it will be converted to a ServerError.
    
    Args:
        error_map: Mapping from exception types to StandardizedError types
        
    Returns:
        Decorator function
        
    Example:
        @with_error_handling({
            ValueError: lambda e: ValidationError(str(e)),
            KeyError: lambda e: NotFoundException(str(e)),
        })
        async def get_user(user_id: str) -> User:
            # Method implementation...
    """
    error_map = error_map or {}
    
    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper_async(*args: Any, **kwargs: Any) -> Any:
            try:
                return await func(*args, **kwargs)
            except StandardizedError:
                # Already a StandardizedError, so just re-raise
                raise
            except HTTPException as exc:
                # Convert FastAPI HTTPExceptions to StandardizedError
                if exc.status_code == status.HTTP_404_NOT_FOUND:
                    raise NotFoundException(exc.detail)
                elif exc.status_code == status.HTTP_403_FORBIDDEN:
                    raise PermissionException(exc.detail)
                elif exc.status_code == status.HTTP_401_UNAUTHORIZED:
                    raise PermissionException(
                        exc.detail,
                        {"error_code": ErrorCode.AUTH_INVALID_CREDENTIALS}
                    )
                else:
                    # Generic HTTP exception conversion
                    raise StandardizedError(
                        message=str(exc.detail),
                        error_code=ErrorCode.SERVER_INTERNAL_ERROR,
                        status_code=exc.status_code,
                    )
            except Exception as exc:
                # Check if we have a mapping for this exception type
                for exc_type, error_factory in error_map.items():
                    if isinstance(exc, exc_type):
                        if callable(error_factory):
                            # If the factory is callable, call it with the exception
                            raise error_factory(exc)
                        else:
                            # Otherwise, use it as a type with default constructor
                            raise error_factory(str(exc))
                
                # If no specific handling is defined, log and convert to generic server error
                error_logger.error(
                    f"Unhandled exception in {func.__name__}: {str(exc)}",
                    extra={
                        "function": func.__name__,
                        "module": func.__module__,
                        "exception_type": exc.__class__.__name__,
                        "traceback": traceback.format_exc(),
                    }
                )
                raise ServerError(f"Error in {func.__name__}: {str(exc)}")
        
        @functools.wraps(func)
        def wrapper_sync(*args: Any, **kwargs: Any) -> Any:
            try:
                return func(*args, **kwargs)
            except StandardizedError:
                # Already a StandardizedError, so just re-raise
                raise
            except HTTPException as exc:
                # Convert FastAPI HTTPExceptions to StandardizedError
                if exc.status_code == status.HTTP_404_NOT_FOUND:
                    raise NotFoundException(exc.detail)
                elif exc.status_code == status.HTTP_403_FORBIDDEN:
                    raise PermissionException(exc.detail)
                elif exc.status_code == status.HTTP_401_UNAUTHORIZED:
                    raise PermissionException(
                        exc.detail,
                        {"error_code": ErrorCode.AUTH_INVALID_CREDENTIALS}
                    )
                else:
                    # Generic HTTP exception conversion
                    raise StandardizedError(
                        message=str(exc.detail),
                        error_code=ErrorCode.SERVER_INTERNAL_ERROR,
                        status_code=exc.status_code,
                    )
            except Exception as exc:
                # Check if we have a mapping for this exception type
                for exc_type, error_factory in error_map.items():
                    if isinstance(exc, exc_type):
                        if callable(error_factory):
                            # If the factory is callable, call it with the exception
                            raise error_factory(exc)
                        else:
                            # Otherwise, use it as a type with default constructor
                            raise error_factory(str(exc))
                
                # If no specific handling is defined, log and convert to generic server error
                error_logger.error(
                    f"Unhandled exception in {func.__name__}: {str(exc)}",
                    extra={
                        "function": func.__name__,
                        "module": func.__module__,
                        "exception_type": exc.__class__.__name__,
                        "traceback": traceback.format_exc(),
                    }
                )
                raise ServerError(f"Error in {func.__name__}: {str(exc)}")
        
        # Choose the appropriate wrapper based on whether the function is async or not
        if inspect.iscoroutinefunction(func):
            return cast(F, wrapper_async)
        return cast(F, wrapper_sync)
    
    return decorator


def api_error_handling(func: F) -> F:
    """Decorator specifically for API endpoint functions.
    
    This provides a standard set of exception mappings suitable for API endpoints.
    
    Args:
        func: The function to decorate
        
    Returns:
        Decorated function
        
    Example:
        @router.get("/users/{user_id}")
        @api_error_handling
        async def get_user(user_id: str):
            # Endpoint implementation...
    """
    standard_error_map = {
        ValueError: lambda e: ValidationError(
            message=str(e),
            field_errors={"": str(e)},
        ),
        KeyError: lambda e: NotFoundException(
            message=f"Resource not found: {str(e).strip('\"')}",
        ),
        PermissionError: lambda e: PermissionException(
            message=str(e),
        ),
        TypeError: lambda e: ValidationError(
            message=str(e),
            field_errors={"": str(e)},
        ),
    }
    
    return with_error_handling(standard_error_map)(func)


def service_error_handling(func: F) -> F:
    """Decorator specifically for service methods.
    
    This provides a standard set of exception mappings suitable for service methods.
    
    Args:
        func: The function to decorate
        
    Returns:
        Decorated function
        
    Example:
        @service_error_handling
        async def create_user(user_data: Dict[str, Any]) -> User:
            # Service method implementation...
    """
    standard_error_map = {
        ValueError: lambda e: ValidationError(
            message=f"Invalid input: {str(e)}",
            field_errors={"": str(e)},
        ),
        KeyError: lambda e: NotFoundException(
            message=f"Required resource not found: {str(e).strip('\"')}",
            details={"missing_key": str(e).strip('\"')},
        ),
        PermissionError: lambda e: PermissionException(
            message=str(e),
        ),
    }
    
    return with_error_handling(standard_error_map)(func)


def integration_error_handling(integration_name: str) -> Callable[[F], F]:
    """Create a decorator for integration-specific error handling.
    
    Args:
        integration_name: Name of the integration (e.g., "stripe", "github")
        
    Returns:
        Decorator function
        
    Example:
        @integration_error_handling("github")
        async def fetch_github_repos(user_id: str) -> List[Repo]:
            # Integration method implementation...
    """
    def decorator(func: F) -> F:
        error_map = {
            ConnectionError: lambda e: IntegrationError(
                message=f"Failed to connect to {integration_name}: {str(e)}",
                integration_name=integration_name,
                error_code=ErrorCode.INTEGRATION_CONNECTION_ERROR,
            ),
            TimeoutError: lambda e: IntegrationError(
                message=f"Timeout connecting to {integration_name}: {str(e)}",
                integration_name=integration_name,
                error_code=ErrorCode.INTEGRATION_CONNECTION_ERROR,
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            ),
            PermissionError: lambda e: IntegrationError(
                message=f"Authentication error with {integration_name}: {str(e)}",
                integration_name=integration_name,
                error_code=ErrorCode.INTEGRATION_AUTHENTICATION_ERROR,
                status_code=status.HTTP_401_UNAUTHORIZED,
            ),
        }
        
        return with_error_handling(error_map)(func)
    
    return decorator