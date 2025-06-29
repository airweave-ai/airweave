"""Shared exceptions module.

This module defines standardized exceptions for the Airweave platform to ensure
consistent error handling, logging, and reporting throughout the application.
Each exception is designed to map to specific HTTP status codes and provide
clear, actionable error messages for API responses.
"""

from enum import Enum
from typing import Any, Dict, List, Optional, Type, Union

from fastapi import HTTPException, status
from pydantic import ValidationError


class PermissionException(Exception):
    """Exception raised when a user does not have the necessary permissions to perform an action."""

    def __init__(
        self,
        message: Optional[str] = "User does not have the right to perform this action",
    ):
        """Create a new PermissionException instance.

        Args:
        ----
            message (str, optional): The error message. Has default message.

        """
        self.message = message
        super().__init__(self.message)


class NotFoundException(Exception):
    """Exception raised when an object is not found."""

    def __init__(self, message: Optional[str] = "Object not found"):
        """Create a new NotFoundException instance.

        Args:
        ----
            message (str, optional): The error message. Has default message.

        """
        self.message = message
        super().__init__(self.message)


class ImmutableFieldError(Exception):
    """Exception raised for attempts to modify immutable fields in a database model."""

    def __init__(self, field_name: str, message: str = "Cannot modify immutable field"):
        """Create a new ImmutableFieldError instance.

        Args:
        ----
            field_name (str): The name of the immutable field.
            message (str, optional): The error message. Has default message.

        """
        self.field_name = field_name
        self.message = message
        super().__init__(f"{message}: {field_name}")


class TokenRefreshError(Exception):
    """Exception raised when a token refresh fails."""

    def __init__(self, message: Optional[str] = "Token refresh failed"):
        """Create a new TokenRefreshError instance.

        Args:
        ----
            message (str, optional): The error message. Has default message.

        """
        self.message = message
        super().__init__(self.message)


class ErrorCode(str, Enum):
    """Error codes for the Airweave platform.
    
    These error codes provide standardized identifiers for different types of errors,
    making it easier to track, categorize, and handle errors consistently.
    
    Format: ERROR_CATEGORY_SPECIFIC_ERROR
    """
    # Authentication & Authorization errors
    AUTH_INVALID_CREDENTIALS = "auth_invalid_credentials"
    AUTH_EXPIRED_TOKEN = "auth_expired_token"
    AUTH_MISSING_TOKEN = "auth_missing_token"
    AUTH_INSUFFICIENT_PERMISSIONS = "auth_insufficient_permissions"
    AUTH_OAUTH_FAILURE = "auth_oauth_failure"
    
    # Resource errors
    RESOURCE_NOT_FOUND = "resource_not_found"
    RESOURCE_ALREADY_EXISTS = "resource_already_exists"
    RESOURCE_INVALID_STATE = "resource_invalid_state"
    RESOURCE_IMMUTABLE_FIELD = "resource_immutable_field"
    
    # Input validation errors
    VALIDATION_INVALID_INPUT = "validation_invalid_input"
    VALIDATION_MISSING_FIELD = "validation_missing_field"
    VALIDATION_INVALID_FORMAT = "validation_invalid_format"
    
    # Integration errors
    INTEGRATION_CONNECTION_ERROR = "integration_connection_error"
    INTEGRATION_AUTHENTICATION_ERROR = "integration_authentication_error"
    INTEGRATION_RATE_LIMIT = "integration_rate_limit"
    INTEGRATION_CONFIG_ERROR = "integration_config_error"
    
    # Synchronization errors
    SYNC_EXECUTION_ERROR = "sync_execution_error"
    SYNC_INVALID_STATE = "sync_invalid_state"
    SYNC_TIMEOUT = "sync_timeout"
    
    # Infrastructure errors
    INFRA_DATABASE_ERROR = "infra_database_error"
    INFRA_CACHE_ERROR = "infra_cache_error"
    INFRA_STORAGE_ERROR = "infra_storage_error"
    
    # Server errors
    SERVER_INTERNAL_ERROR = "server_internal_error"
    SERVER_DEPENDENCY_ERROR = "server_dependency_error"
    SERVER_TIMEOUT = "server_timeout"
    

class StandardizedError(Exception):
    """Base class for standardized exceptions in the Airweave platform.
    
    This provides a consistent interface for all application exceptions,
    ensuring that errors can be properly logged, tracked, and returned to users.
    """
    
    def __init__(
        self,
        message: str,
        error_code: ErrorCode,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: Optional[Dict[str, Any]] = None,
    ):
        """Initialize the standardized error.
        
        Args:
            message: Human-readable error message
            error_code: Standardized error code from ErrorCode enum
            status_code: HTTP status code to return (default 500)
            details: Additional error details/context
        """
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the exception to a dictionary for API responses.
        
        Returns:
            Dictionary representation of the error
        """
        return {
            "error": {
                "code": self.error_code,
                "message": self.message,
                "details": self.details
            }
        }
        
    def to_http_exception(self) -> HTTPException:
        """Convert to FastAPI HTTPException.
        
        Returns:
            HTTPException with appropriate status code and details
        """
        return HTTPException(
            status_code=self.status_code,
            detail=self.to_dict(),
        )


class PermissionException(StandardizedError):
    """Exception raised when a user does not have the necessary permissions."""

    def __init__(
        self,
        message: str = "User does not have permission to perform this action",
        details: Optional[Dict[str, Any]] = None,
    ):
        """Initialize permission exception.
        
        Args:
            message: Error message
            details: Additional error details/context
        """
        super().__init__(
            message=message,
            error_code=ErrorCode.AUTH_INSUFFICIENT_PERMISSIONS,
            status_code=status.HTTP_403_FORBIDDEN,
            details=details,
        )


class NotFoundException(StandardizedError):
    """Exception raised when a resource is not found."""

    def __init__(
        self,
        message: str = "Resource not found",
        resource_type: Optional[str] = None, 
        resource_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        """Initialize not found exception.
        
        Args:
            message: Error message
            resource_type: Type of resource that was not found
            resource_id: Identifier of the resource
            details: Additional error details/context
        """
        error_details = details or {}
        if resource_type:
            error_details["resource_type"] = resource_type
        if resource_id:
            error_details["resource_id"] = resource_id
            
        super().__init__(
            message=message,
            error_code=ErrorCode.RESOURCE_NOT_FOUND,
            status_code=status.HTTP_404_NOT_FOUND,
            details=error_details,
        )


class ImmutableFieldError(StandardizedError):
    """Exception raised for attempts to modify immutable fields."""

    def __init__(
        self,
        field_name: str,
        message: str = "Cannot modify immutable field",
        details: Optional[Dict[str, Any]] = None,
    ):
        """Initialize immutable field error.
        
        Args:
            field_name: Name of the immutable field
            message: Error message
            details: Additional error details/context
        """
        error_details = details or {}
        error_details["field_name"] = field_name
        
        super().__init__(
            message=f"{message}: {field_name}",
            error_code=ErrorCode.RESOURCE_IMMUTABLE_FIELD,
            status_code=status.HTTP_400_BAD_REQUEST,
            details=error_details,
        )


class TokenRefreshError(StandardizedError):
    """Exception raised when a token refresh fails."""

    def __init__(
        self,
        message: str = "Token refresh failed",
        integration_name: Optional[str] = None,
        connection_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        """Initialize token refresh error.
        
        Args:
            message: Error message
            integration_name: Name of the integration
            connection_id: ID of the connection
            details: Additional error details/context
        """
        error_details = details or {}
        if integration_name:
            error_details["integration_name"] = integration_name
        if connection_id:
            error_details["connection_id"] = connection_id
            
        super().__init__(
            message=message,
            error_code=ErrorCode.AUTH_OAUTH_FAILURE,
            status_code=status.HTTP_400_BAD_REQUEST,
            details=error_details,
        )


class ValidationError(StandardizedError):
    """Exception raised for validation errors."""
    
    def __init__(
        self,
        message: str = "Validation error",
        field_errors: Optional[Dict[str, str]] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        """Initialize validation error.
        
        Args:
            message: Error message
            field_errors: Map of field names to error messages
            details: Additional error details/context
        """
        error_details = details or {}
        if field_errors:
            error_details["field_errors"] = field_errors
            
        super().__init__(
            message=message,
            error_code=ErrorCode.VALIDATION_INVALID_INPUT,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details=error_details,
        )


class IntegrationError(StandardizedError):
    """Exception raised when an integration operation fails."""
    
    def __init__(
        self,
        message: str = "Integration error",
        integration_name: Optional[str] = None,
        error_code: ErrorCode = ErrorCode.INTEGRATION_CONNECTION_ERROR,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        details: Optional[Dict[str, Any]] = None,
    ):
        """Initialize integration error.
        
        Args:
            message: Error message
            integration_name: Name of the integration
            error_code: Specific error code
            status_code: HTTP status code
            details: Additional error details/context
        """
        error_details = details or {}
        if integration_name:
            error_details["integration_name"] = integration_name
            
        super().__init__(
            message=message,
            error_code=error_code,
            status_code=status_code,
            details=error_details,
        )


class SyncError(StandardizedError):
    """Exception raised when a synchronization operation fails."""
    
    def __init__(
        self,
        message: str = "Synchronization error",
        sync_id: Optional[str] = None,
        error_code: ErrorCode = ErrorCode.SYNC_EXECUTION_ERROR,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        details: Optional[Dict[str, Any]] = None,
    ):
        """Initialize sync error.
        
        Args:
            message: Error message
            sync_id: ID of the sync
            error_code: Specific error code
            status_code: HTTP status code
            details: Additional error details/context
        """
        error_details = details or {}
        if sync_id:
            error_details["sync_id"] = sync_id
            
        super().__init__(
            message=message,
            error_code=error_code,
            status_code=status_code,
            details=error_details,
        )


class ServerError(StandardizedError):
    """Exception raised for internal server errors."""
    
    def __init__(
        self,
        message: str = "Internal server error",
        error_code: ErrorCode = ErrorCode.SERVER_INTERNAL_ERROR,
        details: Optional[Dict[str, Any]] = None,
    ):
        """Initialize server error.
        
        Args:
            message: Error message
            error_code: Specific error code
            details: Additional error details/context
        """
        super().__init__(
            message=message,
            error_code=error_code,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=details,
        )


def unpack_validation_error(exc: ValidationError) -> dict:
    """Unpack a Pydantic validation error into a dictionary.

    Args:
        exc: The Pydantic validation error

    Returns:
        Dictionary representation of the validation error
    """
    error_messages = []
    for error in exc.errors():
        field = ".".join(str(loc) for loc in error["loc"])
        message = error["msg"]
        error_messages.append({field: message})

    return {"errors": error_messages}
