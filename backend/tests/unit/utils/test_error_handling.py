"""Tests for error handling utilities."""

import pytest
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
from airweave.utils.error_handling import (
    with_error_handling,
    api_error_handling,
    service_error_handling,
    integration_error_handling,
)


class TestStandardizedErrors:
    """Test the standardized error classes."""
    
    def test_error_codes_are_unique(self):
        """Test that all error codes are unique."""
        codes = [e.value for e in ErrorCode]
        assert len(codes) == len(set(codes)), "Error codes must be unique"
    
    def test_standardized_error_initialization(self):
        """Test initialization of StandardizedError."""
        error = StandardizedError(
            message="Test error",
            error_code=ErrorCode.VALIDATION_INVALID_INPUT,
            status_code=status.HTTP_400_BAD_REQUEST,
            details={"test": "detail"}
        )
        
        assert error.message == "Test error"
        assert error.error_code == ErrorCode.VALIDATION_INVALID_INPUT
        assert error.status_code == status.HTTP_400_BAD_REQUEST
        assert error.details == {"test": "detail"}
    
    def test_error_to_dict(self):
        """Test conversion of StandardizedError to dictionary."""
        error = StandardizedError(
            message="Test error",
            error_code=ErrorCode.VALIDATION_INVALID_INPUT,
            status_code=status.HTTP_400_BAD_REQUEST,
            details={"test": "detail"}
        )
        
        error_dict = error.to_dict()
        
        assert "error" in error_dict
        assert error_dict["error"]["code"] == ErrorCode.VALIDATION_INVALID_INPUT
        assert error_dict["error"]["message"] == "Test error"
        assert error_dict["error"]["details"] == {"test": "detail"}
    
    def test_error_to_http_exception(self):
        """Test conversion of StandardizedError to HTTPException."""
        error = StandardizedError(
            message="Test error",
            error_code=ErrorCode.VALIDATION_INVALID_INPUT,
            status_code=status.HTTP_400_BAD_REQUEST,
            details={"test": "detail"}
        )
        
        http_exc = error.to_http_exception()
        
        assert isinstance(http_exc, HTTPException)
        assert http_exc.status_code == status.HTTP_400_BAD_REQUEST
        assert http_exc.detail == error.to_dict()
    
    def test_permission_exception(self):
        """Test PermissionException initialization."""
        error = PermissionException("No permission")
        
        assert error.message == "No permission"
        assert error.error_code == ErrorCode.AUTH_INSUFFICIENT_PERMISSIONS
        assert error.status_code == status.HTTP_403_FORBIDDEN
    
    def test_not_found_exception(self):
        """Test NotFoundException initialization."""
        error = NotFoundException(
            "User not found", 
            resource_type="user",
            resource_id="123"
        )
        
        assert error.message == "User not found"
        assert error.error_code == ErrorCode.RESOURCE_NOT_FOUND
        assert error.status_code == status.HTTP_404_NOT_FOUND
        assert error.details["resource_type"] == "user"
        assert error.details["resource_id"] == "123"
    
    def test_validation_error(self):
        """Test ValidationError initialization."""
        field_errors = {"name": "Name is required", "email": "Invalid email format"}
        error = ValidationError(
            "Validation failed",
            field_errors=field_errors
        )
        
        assert error.message == "Validation failed"
        assert error.error_code == ErrorCode.VALIDATION_INVALID_INPUT
        assert error.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert error.details["field_errors"] == field_errors


@pytest.mark.asyncio
class TestErrorHandlingDecorators:
    """Test the error handling decorators."""
    
    async def test_with_error_handling_async_success(self):
        """Test successful async function execution with error handling."""
        @with_error_handling()
        async def test_func(value):
            return value * 2
        
        result = await test_func(5)
        assert result == 10
    
    async def test_with_error_handling_async_standardized_error(self):
        """Test handling of StandardizedError in async function."""
        @with_error_handling()
        async def test_func():
            raise PermissionException("No permission")
        
        with pytest.raises(PermissionException) as exc_info:
            await test_func()
            
        assert exc_info.value.message == "No permission"
    
    async def test_with_error_handling_async_mapped_error(self):
        """Test error mapping in async function."""
        error_map = {
            ValueError: lambda e: ValidationError(str(e)),
            KeyError: lambda e: NotFoundException(str(e)),
        }
        
        @with_error_handling(error_map)
        async def test_func(error_type):
            if error_type == "value_error":
                raise ValueError("Invalid value")
            elif error_type == "key_error":
                raise KeyError("Missing key")
            return "OK"
        
        with pytest.raises(ValidationError) as exc_info:
            await test_func("value_error")
        assert exc_info.value.message == "Invalid value"
        
        with pytest.raises(NotFoundException) as exc_info:
            await test_func("key_error")
        assert "Missing key" in exc_info.value.message
    
    async def test_with_error_handling_async_unmapped_error(self):
        """Test handling of unmapped errors in async function."""
        @with_error_handling()
        async def test_func():
            raise RuntimeError("Something went wrong")
        
        with pytest.raises(ServerError) as exc_info:
            await test_func()
            
        assert "Something went wrong" in exc_info.value.message
    
    def test_with_error_handling_sync_success(self):
        """Test successful sync function execution with error handling."""
        @with_error_handling()
        def test_func(value):
            return value * 2
        
        result = test_func(5)
        assert result == 10
    
    def test_with_error_handling_sync_mapped_error(self):
        """Test error mapping in sync function."""
        error_map = {
            ValueError: lambda e: ValidationError(str(e)),
        }
        
        @with_error_handling(error_map)
        def test_func():
            raise ValueError("Invalid value")
        
        with pytest.raises(ValidationError) as exc_info:
            test_func()
            
        assert exc_info.value.message == "Invalid value"
    
    def test_api_error_handling_decorator(self):
        """Test the api_error_handling decorator."""
        @api_error_handling
        def test_func(error_type):
            if error_type == "value_error":
                raise ValueError("Invalid value")
            elif error_type == "key_error":
                raise KeyError("user_id")
            elif error_type == "permission_error":
                raise PermissionError("No permission")
            return "OK"
        
        with pytest.raises(ValidationError):
            test_func("value_error")
            
        with pytest.raises(NotFoundException) as exc_info:
            test_func("key_error")
        assert "user_id" in exc_info.value.message
            
        with pytest.raises(PermissionException):
            test_func("permission_error")
    
    def test_service_error_handling_decorator(self):
        """Test the service_error_handling decorator."""
        @service_error_handling
        def test_func(error_type):
            if error_type == "value_error":
                raise ValueError("Invalid value")
            elif error_type == "key_error":
                raise KeyError("resource_id")
            return "OK"
            
        with pytest.raises(ValidationError) as exc_info:
            test_func("value_error")
        assert "Invalid input" in exc_info.value.message
            
        with pytest.raises(NotFoundException) as exc_info:
            test_func("key_error")
        assert "resource_id" in exc_info.value.message
    
    @pytest.mark.asyncio
    async def test_integration_error_handling_decorator(self):
        """Test the integration_error_handling decorator."""
        @integration_error_handling("github")
        async def test_func(error_type):
            if error_type == "connection_error":
                raise ConnectionError("Failed to connect")
            elif error_type == "timeout_error":
                raise TimeoutError("Connection timed out")
            elif error_type == "permission_error":
                raise PermissionError("Authentication failed")
            return "OK"
            
        with pytest.raises(IntegrationError) as exc_info:
            await test_func("connection_error")
        assert "github" in exc_info.value.message
        assert "Failed to connect" in exc_info.value.message
        assert exc_info.value.error_code == ErrorCode.INTEGRATION_CONNECTION_ERROR
            
        with pytest.raises(IntegrationError) as exc_info:
            await test_func("timeout_error")
        assert exc_info.value.status_code == status.HTTP_504_GATEWAY_TIMEOUT
            
        with pytest.raises(IntegrationError) as exc_info:
            await test_func("permission_error")
        assert exc_info.value.error_code == ErrorCode.INTEGRATION_AUTHENTICATION_ERROR