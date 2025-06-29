"""Tests for error handling middleware."""

import pytest
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from airweave.api.middleware.error_handler import (
    add_error_handlers,
    ExceptionMiddleware,
    handle_standardized_error,
    handle_validation_error,
    handle_sqlalchemy_error,
    handle_generic_error,
)
from airweave.core.exceptions import (
    ErrorCode,
    StandardizedError,
    PermissionException,
    NotFoundException,
)


@pytest.fixture
def test_app():
    """Create a FastAPI test app with error handlers."""
    app = FastAPI()
    add_error_handlers(app)
    
    @app.get("/test-standard-error")
    def test_standard_error():
        raise StandardizedError(
            message="Test error",
            error_code=ErrorCode.VALIDATION_INVALID_INPUT,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
        
    @app.get("/test-permission-error")
    def test_permission_error():
        raise PermissionException("No permission")
        
    @app.get("/test-not-found-error")
    def test_not_found_error():
        raise NotFoundException("Resource not found", "user", "123")
        
    @app.get("/test-http-exception")
    def test_http_exception():
        raise HTTPException(status_code=400, detail="Bad request")
        
    @app.get("/test-value-error")
    def test_value_error():
        raise ValueError("Invalid value")
        
    @app.get("/test-integrity-error")
    def test_integrity_error():
        raise IntegrityError("statement", "params", "orig")
        
    class TestModel(BaseModel):
        name: str = Field(..., min_length=3)
        age: int = Field(..., gt=0)
        
    @app.post("/test-validation")
    def test_validation(data: TestModel):
        return {"success": True}
    
    return app


class TestErrorHandlerMiddleware:
    """Tests for the error handler middleware."""
    
    def test_standardized_error_handling(self, test_app):
        """Test handling of StandardizedError."""
        client = TestClient(test_app)
        response = client.get("/test-standard-error")
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert "error" in response.json()
        assert response.json()["error"]["code"] == ErrorCode.VALIDATION_INVALID_INPUT
        assert response.json()["error"]["message"] == "Test error"
    
    def test_permission_exception_handling(self, test_app):
        """Test handling of PermissionException."""
        client = TestClient(test_app)
        response = client.get("/test-permission-error")
        
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "error" in response.json()
        assert response.json()["error"]["code"] == ErrorCode.AUTH_INSUFFICIENT_PERMISSIONS
        assert response.json()["error"]["message"] == "No permission"
    
    def test_not_found_exception_handling(self, test_app):
        """Test handling of NotFoundException."""
        client = TestClient(test_app)
        response = client.get("/test-not-found-error")
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "error" in response.json()
        assert response.json()["error"]["code"] == ErrorCode.RESOURCE_NOT_FOUND
        assert response.json()["error"]["message"] == "Resource not found"
        assert response.json()["error"]["details"]["resource_type"] == "user"
        assert response.json()["error"]["details"]["resource_id"] == "123"
    
    def test_validation_error_handling(self, test_app):
        """Test handling of validation errors."""
        client = TestClient(test_app)
        response = client.post("/test-validation", json={"name": "a", "age": 0})
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert "error" in response.json()
        assert response.json()["error"]["code"] == ErrorCode.VALIDATION_INVALID_INPUT
        assert "field_errors" in response.json()["error"]["details"]
    
    def test_integrity_error_handling(self, test_app):
        """Test handling of IntegrityError."""
        client = TestClient(test_app)
        response = client.get("/test-integrity-error")
        
        assert response.status_code == status.HTTP_409_CONFLICT
        assert "error" in response.json()
        assert response.json()["error"]["code"] == ErrorCode.RESOURCE_ALREADY_EXISTS
    
    def test_generic_error_handling(self, test_app):
        """Test handling of generic errors."""
        client = TestClient(test_app)
        response = client.get("/test-value-error")
        
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "error" in response.json()
        assert response.json()["error"]["code"] == ErrorCode.SERVER_INTERNAL_ERROR
        assert "details" in response.json()["error"]


@pytest.mark.asyncio
class TestErrorHandlers:
    """Tests for the individual error handler functions."""
    
    async def test_handle_standardized_error(self):
        """Test handle_standardized_error function."""
        error = StandardizedError(
            message="Test error",
            error_code=ErrorCode.VALIDATION_INVALID_INPUT,
            status_code=status.HTTP_400_BAD_REQUEST,
        )
        
        # Create a minimal request object for testing
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/test",
            "headers": [],
            "client": ("127.0.0.1", 8000),
        }
        request = Request(scope=scope)
        
        response = await handle_standardized_error(request, error)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        
        content = response.body.decode()
        assert "Test error" in content
        assert ErrorCode.VALIDATION_INVALID_INPUT in content
    
    async def test_handle_sqlalchemy_error_integrity(self):
        """Test handle_sqlalchemy_error function with integrity error."""
        error = IntegrityError("statement", "params", "Duplicate entry")
        
        # Create a minimal request object for testing
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/test",
            "headers": [],
            "client": ("127.0.0.1", 8000),
        }
        request = Request(scope=scope)
        
        response = await handle_sqlalchemy_error(request, error)
        assert response.status_code == status.HTTP_409_CONFLICT
        
        content = response.body.decode()
        assert ErrorCode.RESOURCE_ALREADY_EXISTS in content
    
    async def test_handle_sqlalchemy_error_generic(self):
        """Test handle_sqlalchemy_error function with generic error."""
        error = SQLAlchemyError("Database error")
        
        # Create a minimal request object for testing
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/test",
            "headers": [],
            "client": ("127.0.0.1", 8000),
        }
        request = Request(scope=scope)
        
        response = await handle_sqlalchemy_error(request, error)
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        
        content = response.body.decode()
        assert ErrorCode.INFRA_DATABASE_ERROR in content
    
    async def test_handle_generic_error(self):
        """Test handle_generic_error function."""
        error = ValueError("Test error")
        
        # Create a minimal request object for testing
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/test",
            "headers": [],
            "client": ("127.0.0.1", 8000),
        }
        request = Request(scope=scope)
        
        response = await handle_generic_error(request, error)
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        
        content = response.body.decode()
        assert ErrorCode.SERVER_INTERNAL_ERROR in content
        
        # Ensure we don't leak the actual error message to clients
        assert "Test error" not in content