"""Comprehensive input validation utilities for API endpoints.

This module provides validation functions for various types of inputs
to ensure security, consistency, and proper error handling in the API.
"""

import re
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from urllib.parse import urlparse

from fastapi import HTTPException

from airweave.core.logging import logger

validation_logger = logger.with_prefix("Input Validation: ")


# Common validation patterns
UUID_PATTERN = r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
API_KEY_PATTERN = r"^[A-Za-z0-9_\-\.]+$"
EMAIL_PATTERN = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
CRON_PATTERN = (
    r"^(\*|[0-9]{1,2}|[0-9]{1,2}-[0-9]{1,2}|[0-9]{1,2}/[0-9]{1,2}|[0-9]{1,2},[0-9]{1,2}|\*\/[0-9]{1,2}) "
    r"(\*|[0-9]{1,2}|[0-9]{1,2}-[0-9]{1,2}|[0-9]{1,2}/[0-9]{1,2}|[0-9]{1,2},[0-9]{1,2}|\*\/[0-9]{1,2}) "
    r"(\*|[0-9]{1,2}|[0-9]{1,2}-[0-9]{1,2}|[0-9]{1,2}/[0-9]{1,2}|[0-9]{1,2},[0-9]{1,2}|\*\/[0-9]{1,2}) "
    r"(\*|[0-9]{1,2}|JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC|"
    r"[0-9]{1,2}-[0-9]{1,2}|[0-9]{1,2}/[0-9]{1,2}|[0-9]{1,2},[0-9]{1,2}|\*\/[0-9]{1,2}) "
    r"(\*|[0-6]|SUN|MON|TUE|WED|THU|FRI|SAT|[0-6]-[0-6]|[0-6]/[0-6]|[0-6],[0-6]|\*\/[0-6])$"
)
URL_PATTERN = r"^https?:\/\/(www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b([-a-zA-Z0-9()@:%_\+.~#?&//=]*)$"
JWT_PATTERN = r"^[A-Za-z0-9-_=]+\.[A-Za-z0-9-_=]+\.[A-Za-z0-9-_.+/=]*$"
AUTH_CODE_PATTERN = r"^[A-Za-z0-9\-_\.]+$"

# Common dangerous patterns in inputs
SQL_INJECTION_PATTERNS = [
    r"(?i)(\b(select|update|insert|delete|drop|alter|create|truncate)\b.*\b(from|table|database|into)\b)",
    r"(?i)(\b(union|join)\b.*\b(select)\b)",
    r"(?i)(--.*$)",  # SQL line comment
    r"(?i)(\/\*.*\*\/)",  # SQL block comment
]

XSS_PATTERNS = [
    r"(?i)(<script\b[^>]*>.*?<\/script>)",
    r"(?i)(javascript\s*:)",
    r"(?i)(onload\s*=|onerror\s*=|onmouseover\s*=)",
    r"(?i)(<img[^>]+\bsrc\s*=[^>]+>)",
]

COMMAND_INJECTION_PATTERNS = [
    r"(?i)(;.*?(bash|sh|ksh|csh|echo|ls|pwd|cd|cat|curl|wget|nc|ncat|python|perl|ruby))",
    r"(?i)(\|.*?(bash|sh|ksh|csh|echo|ls|pwd|cd|cat|curl|wget|nc|ncat|python|perl|ruby))",
    r"(?i)(&&.*?(bash|sh|ksh|csh|echo|ls|pwd|cd|cat|curl|wget|nc|ncat|python|perl|ruby))",
]


class InputValidationError(Exception):
    """Custom exception for input validation errors."""

    def __init__(self, field: str, message: str):
        """Initialize with field name and error message.
        
        Args:
            field: The field that failed validation
            message: The error message
        """
        self.field = field
        self.message = message
        super().__init__(f"{field}: {message}")


def validate_and_sanitize_input(
    data: Dict[str, Any], 
    validation_rules: Dict[str, Dict[str, Any]], 
    raise_exception: bool = True
) -> Tuple[Dict[str, Any], List[Dict[str, str]]]:
    """Validate and sanitize input data based on rules.
    
    Args:
        data: Dictionary of input data to validate
        validation_rules: Dictionary mapping field names to validation rules
        raise_exception: Whether to raise HTTPException on validation failure
        
    Returns:
        Tuple of (sanitized_data, validation_errors)
        
    Raises:
        HTTPException: If validation fails and raise_exception is True
    """
    sanitized_data = data.copy()
    errors = []
    
    for field, rules in validation_rules.items():
        # Skip if field is not in data and not required
        if field not in data and not rules.get("required", False):
            continue
            
        # Check required fields
        if rules.get("required", False) and (field not in data or data[field] is None):
            error = {"field": field, "message": "This field is required"}
            errors.append(error)
            continue
            
        # Skip further validation if field is not present
        if field not in data or data[field] is None:
            continue
            
        value = data[field]
        field_type = rules.get("type")
        
        try:
            # Type validation
            if field_type:
                if field_type == "uuid":
                    validate_uuid(value, field)
                elif field_type == "email":
                    validate_email(value, field)
                elif field_type == "url":
                    validate_url(value, field)
                elif field_type == "datetime":
                    validate_datetime(value, field)
                elif field_type == "cron":
                    validate_cron_schedule(value, field)
                elif field_type == "string":
                    validate_string(value, field, rules.get("min_length"), rules.get("max_length"), rules.get("pattern"))
                elif field_type == "integer":
                    validate_integer(value, field, rules.get("min_value"), rules.get("max_value"))
                elif field_type == "float":
                    validate_float(value, field, rules.get("min_value"), rules.get("max_value"))
                elif field_type == "boolean":
                    validate_boolean(value, field)
                elif field_type == "list":
                    validate_list(value, field, rules.get("item_type"), rules.get("min_items"), rules.get("max_items"))
                elif field_type == "dict":
                    validate_dict(value, field, rules.get("key_type"), rules.get("value_type"))
                elif field_type == "api_key":
                    validate_api_key(value, field)
                elif field_type == "auth_code":
                    validate_auth_code(value, field)
                elif field_type == "jwt":
                    validate_jwt(value, field)
                
            # Security validation if enabled
            if rules.get("security_check", False):
                validate_security(value, field)
                
            # Apply sanitization if specified
            if rules.get("sanitize", False):
                sanitized_value = sanitize_input(value, field_type, rules.get("sanitize_method"))
                sanitized_data[field] = sanitized_value
                
        except InputValidationError as e:
            errors.append({"field": e.field, "message": e.message})
    
    # Handle errors
    if errors and raise_exception:
        error_details = {error["field"]: error["message"] for error in errors}
        validation_logger.warning(f"Input validation failed: {error_details}")
        raise HTTPException(status_code=422, detail={"errors": errors})
        
    return sanitized_data, errors


def validate_uuid(value: Any, field: str) -> None:
    """Validate a UUID string.
    
    Args:
        value: The value to validate
        field: Field name for error reporting
        
    Raises:
        InputValidationError: If validation fails
    """
    if isinstance(value, uuid.UUID):
        return
        
    if not isinstance(value, str):
        raise InputValidationError(field, "Must be a UUID string")
        
    if not re.match(UUID_PATTERN, value.lower()):
        try:
            uuid.UUID(value)
        except ValueError:
            raise InputValidationError(field, "Invalid UUID format")


def validate_email(value: Any, field: str) -> None:
    """Validate an email address.
    
    Args:
        value: The value to validate
        field: Field name for error reporting
        
    Raises:
        InputValidationError: If validation fails
    """
    if not isinstance(value, str):
        raise InputValidationError(field, "Must be a string")
        
    if not re.match(EMAIL_PATTERN, value):
        raise InputValidationError(field, "Invalid email format")


def validate_url(value: Any, field: str) -> None:
    """Validate a URL.
    
    Args:
        value: The value to validate
        field: Field name for error reporting
        
    Raises:
        InputValidationError: If validation fails
    """
    if not isinstance(value, str):
        raise InputValidationError(field, "Must be a string")
        
    if not re.match(URL_PATTERN, value):
        try:
            result = urlparse(value)
            if not all([result.scheme, result.netloc]):
                raise InputValidationError(field, "Invalid URL format")
        except Exception:
            raise InputValidationError(field, "Invalid URL format")


def validate_datetime(value: Any, field: str) -> None:
    """Validate a datetime string or object.
    
    Args:
        value: The value to validate
        field: Field name for error reporting
        
    Raises:
        InputValidationError: If validation fails
    """
    if isinstance(value, datetime):
        return
        
    if not isinstance(value, str):
        raise InputValidationError(field, "Must be a valid ISO datetime string")
        
    try:
        datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        raise InputValidationError(field, "Invalid datetime format, expected ISO format")


def validate_cron_schedule(value: Any, field: str) -> None:
    """Validate a cron schedule string.
    
    Args:
        value: The value to validate
        field: Field name for error reporting
        
    Raises:
        InputValidationError: If validation fails
    """
    if not isinstance(value, str):
        raise InputValidationError(field, "Must be a string")
        
    if not re.match(CRON_PATTERN, value):
        raise InputValidationError(
            field, 
            "Invalid cron schedule format (e.g., '0 */6 * * *')"
        )


def validate_string(
    value: Any, 
    field: str, 
    min_length: Optional[int] = None, 
    max_length: Optional[int] = None,
    pattern: Optional[str] = None
) -> None:
    """Validate a string.
    
    Args:
        value: The value to validate
        field: Field name for error reporting
        min_length: Minimum string length
        max_length: Maximum string length
        pattern: Regex pattern to match
        
    Raises:
        InputValidationError: If validation fails
    """
    if not isinstance(value, str):
        raise InputValidationError(field, "Must be a string")
        
    if min_length is not None and len(value) < min_length:
        raise InputValidationError(field, f"Must be at least {min_length} characters")
        
    if max_length is not None and len(value) > max_length:
        raise InputValidationError(field, f"Must be at most {max_length} characters")
        
    if pattern is not None and not re.match(pattern, value):
        raise InputValidationError(field, "Invalid format")


def validate_integer(
    value: Any, 
    field: str, 
    min_value: Optional[int] = None, 
    max_value: Optional[int] = None
) -> None:
    """Validate an integer.
    
    Args:
        value: The value to validate
        field: Field name for error reporting
        min_value: Minimum allowed value
        max_value: Maximum allowed value
        
    Raises:
        InputValidationError: If validation fails
    """
    if isinstance(value, str):
        try:
            value = int(value)
        except ValueError:
            raise InputValidationError(field, "Must be an integer")
    
    if not isinstance(value, int) or isinstance(value, bool):
        raise InputValidationError(field, "Must be an integer")
        
    if min_value is not None and value < min_value:
        raise InputValidationError(field, f"Must be at least {min_value}")
        
    if max_value is not None and value > max_value:
        raise InputValidationError(field, f"Must be at most {max_value}")


def validate_float(
    value: Any, 
    field: str, 
    min_value: Optional[float] = None, 
    max_value: Optional[float] = None
) -> None:
    """Validate a floating point number.
    
    Args:
        value: The value to validate
        field: Field name for error reporting
        min_value: Minimum allowed value
        max_value: Maximum allowed value
        
    Raises:
        InputValidationError: If validation fails
    """
    if isinstance(value, str):
        try:
            value = float(value)
        except ValueError:
            raise InputValidationError(field, "Must be a number")
    
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise InputValidationError(field, "Must be a number")
        
    if min_value is not None and value < min_value:
        raise InputValidationError(field, f"Must be at least {min_value}")
        
    if max_value is not None and value > max_value:
        raise InputValidationError(field, f"Must be at most {max_value}")


def validate_boolean(value: Any, field: str) -> None:
    """Validate a boolean value.
    
    Args:
        value: The value to validate
        field: Field name for error reporting
        
    Raises:
        InputValidationError: If validation fails
    """
    # Allow string values "true"/"false" and convert them
    if isinstance(value, str):
        value_lower = value.lower()
        if value_lower in ("true", "false"):
            return
            
    if not isinstance(value, bool):
        raise InputValidationError(field, "Must be a boolean value")


def validate_list(
    value: Any, 
    field: str, 
    item_type: Optional[str] = None,
    min_items: Optional[int] = None,
    max_items: Optional[int] = None
) -> None:
    """Validate a list.
    
    Args:
        value: The value to validate
        field: Field name for error reporting
        item_type: Type of list items
        min_items: Minimum number of items
        max_items: Maximum number of items
        
    Raises:
        InputValidationError: If validation fails
    """
    if not isinstance(value, list):
        raise InputValidationError(field, "Must be a list")
        
    if min_items is not None and len(value) < min_items:
        raise InputValidationError(field, f"Must have at least {min_items} items")
        
    if max_items is not None and len(value) > max_items:
        raise InputValidationError(field, f"Must have at most {max_items} items")
        
    if item_type:
        for i, item in enumerate(value):
            try:
                if item_type == "string":
                    validate_string(item, f"{field}[{i}]")
                elif item_type == "integer":
                    validate_integer(item, f"{field}[{i}]")
                elif item_type == "float":
                    validate_float(item, f"{field}[{i}]")
                elif item_type == "boolean":
                    validate_boolean(item, f"{field}[{i}]")
                elif item_type == "uuid":
                    validate_uuid(item, f"{field}[{i}]")
                elif item_type == "email":
                    validate_email(item, f"{field}[{i}]")
                elif item_type == "url":
                    validate_url(item, f"{field}[{i}]")
            except InputValidationError as e:
                raise InputValidationError(field, f"Item at index {i}: {e.message}")


def validate_dict(
    value: Any, 
    field: str, 
    key_type: Optional[str] = None,
    value_type: Optional[str] = None
) -> None:
    """Validate a dictionary.
    
    Args:
        value: The value to validate
        field: Field name for error reporting
        key_type: Type of dictionary keys
        value_type: Type of dictionary values
        
    Raises:
        InputValidationError: If validation fails
    """
    if not isinstance(value, dict):
        raise InputValidationError(field, "Must be a dictionary")
        
    if key_type or value_type:
        for k, v in value.items():
            if key_type:
                try:
                    if key_type == "string":
                        validate_string(k, f"{field} key")
                    elif key_type == "integer":
                        validate_integer(k, f"{field} key")
                    elif key_type == "uuid":
                        validate_uuid(k, f"{field} key")
                except InputValidationError as e:
                    raise InputValidationError(field, f"Key '{k}': {e.message}")
                    
            if value_type:
                try:
                    if value_type == "string":
                        validate_string(v, f"{field}[{k}]")
                    elif value_type == "integer":
                        validate_integer(v, f"{field}[{k}]")
                    elif value_type == "float":
                        validate_float(v, f"{field}[{k}]")
                    elif value_type == "boolean":
                        validate_boolean(v, f"{field}[{k}]")
                    elif value_type == "uuid":
                        validate_uuid(v, f"{field}[{k}]")
                    elif value_type == "email":
                        validate_email(v, f"{field}[{k}]")
                    elif value_type == "url":
                        validate_url(v, f"{field}[{k}]")
                    elif value_type == "dict":
                        validate_dict(v, f"{field}[{k}]")
                    elif value_type == "list":
                        validate_list(v, f"{field}[{k}]")
                except InputValidationError as e:
                    raise InputValidationError(field, f"Value for key '{k}': {e.message}")


def validate_api_key(value: Any, field: str) -> None:
    """Validate an API key.
    
    Args:
        value: The value to validate
        field: Field name for error reporting
        
    Raises:
        InputValidationError: If validation fails
    """
    if not isinstance(value, str):
        raise InputValidationError(field, "Must be a string")
        
    if not re.match(API_KEY_PATTERN, value):
        raise InputValidationError(field, "Invalid API key format")
        
    if len(value) < 8:
        raise InputValidationError(field, "API key must be at least 8 characters")


def validate_auth_code(value: Any, field: str) -> None:
    """Validate an OAuth authorization code.
    
    Args:
        value: The value to validate
        field: Field name for error reporting
        
    Raises:
        InputValidationError: If validation fails
    """
    if not isinstance(value, str):
        raise InputValidationError(field, "Must be a string")
        
    if not re.match(AUTH_CODE_PATTERN, value):
        raise InputValidationError(field, "Invalid authorization code format")


def validate_jwt(value: Any, field: str) -> None:
    """Validate a JWT token.
    
    Args:
        value: The value to validate
        field: Field name for error reporting
        
    Raises:
        InputValidationError: If validation fails
    """
    if not isinstance(value, str):
        raise InputValidationError(field, "Must be a string")
        
    if not re.match(JWT_PATTERN, value):
        raise InputValidationError(field, "Invalid JWT format")


def validate_security(value: Any, field: str) -> None:
    """Validate input for common security issues.
    
    Args:
        value: The value to validate
        field: Field name for error reporting
        
    Raises:
        InputValidationError: If validation fails
    """
    if not isinstance(value, str):
        return
        
    # Check for SQL injection patterns
    for pattern in SQL_INJECTION_PATTERNS:
        if re.search(pattern, value):
            validation_logger.warning(f"Potential SQL injection detected in field {field}")
            raise InputValidationError(field, "Invalid input contains potentially unsafe characters")
            
    # Check for XSS patterns
    for pattern in XSS_PATTERNS:
        if re.search(pattern, value):
            validation_logger.warning(f"Potential XSS detected in field {field}")
            raise InputValidationError(field, "Invalid input contains potentially unsafe characters")
            
    # Check for command injection patterns
    for pattern in COMMAND_INJECTION_PATTERNS:
        if re.search(pattern, value):
            validation_logger.warning(f"Potential command injection detected in field {field}")
            raise InputValidationError(field, "Invalid input contains potentially unsafe characters")


def sanitize_input(value: Any, field_type: str, sanitize_method: Optional[str] = None) -> Any:
    """Sanitize input based on type and sanitization method.
    
    Args:
        value: The value to sanitize
        field_type: Type of the field
        sanitize_method: Sanitization method to apply
        
    Returns:
        Sanitized value
    """
    if sanitize_method == "strip" and isinstance(value, str):
        return value.strip()
        
    if sanitize_method == "lowercase" and isinstance(value, str):
        return value.lower()
        
    if sanitize_method == "uppercase" and isinstance(value, str):
        return value.upper()
        
    if sanitize_method == "title" and isinstance(value, str):
        return value.title()
        
    if sanitize_method == "trim_whitespace" and isinstance(value, str):
        return re.sub(r'\s+', ' ', value).strip()
        
    if sanitize_method == "none_if_empty" and isinstance(value, str) and not value.strip():
        return None
        
    return value


# Validation rule sets for common API inputs

AUTH_CODE_VALIDATION = {
    "code": {
        "type": "auth_code",
        "required": True,
        "security_check": True,
    },
    "client_id": {
        "type": "string",
        "required": False,
        "security_check": True,
    },
    "client_secret": {
        "type": "string",
        "required": False,
        "security_check": True,
    },
}

SOURCE_CONNECTION_CREATE_VALIDATION = {
    "name": {
        "type": "string",
        "required": True,
        "min_length": 4,
        "max_length": 42,
        "sanitize": True,
        "sanitize_method": "trim_whitespace",
    },
    "description": {
        "type": "string",
        "required": False,
        "max_length": 500,
        "sanitize": True,
        "sanitize_method": "trim_whitespace",
    },
    "short_name": {
        "type": "string",
        "required": True,
        "pattern": r"^[a-z0-9_]+$",
        "security_check": True,
    },
    "collection": {
        "type": "string",
        "required": False,
        "security_check": True,
    },
    "cron_schedule": {
        "type": "cron",
        "required": False,
    },
    "sync_immediately": {
        "type": "boolean",
        "required": False,
    },
    "white_label_id": {
        "type": "uuid",
        "required": False,
    },
}

API_KEY_CREATE_VALIDATION = {
    "name": {
        "type": "string",
        "required": True,
        "min_length": 3,
        "max_length": 50,
        "sanitize": True,
        "sanitize_method": "trim_whitespace",
    },
    "expiration_date": {
        "type": "datetime",
        "required": False,
    },
    "description": {
        "type": "string",
        "required": False,
        "max_length": 500,
        "sanitize": True,
        "sanitize_method": "trim_whitespace",
    },
}

OAUTH2_TOKEN_VALIDATION = {
    "access_token": {
        "type": "string",
        "required": True,
        "security_check": True,
    },
    "refresh_token": {
        "type": "string",
        "required": False,
        "security_check": True,
    },
    "expires_in": {
        "type": "integer",
        "required": False,
        "min_value": 0,
    },
    "token_type": {
        "type": "string",
        "required": False,
    },
}

# Helper function for API endpoints
def validate_request_data(data: Dict[str, Any], validation_type: str) -> Dict[str, Any]:
    """Validate request data based on predefined validation rules.
    
    Args:
        data: Request data to validate
        validation_type: Type of validation to apply
        
    Returns:
        Sanitized data
        
    Raises:
        HTTPException: If validation fails
    """
    validation_rules = {
        "auth_code": AUTH_CODE_VALIDATION,
        "source_connection_create": SOURCE_CONNECTION_CREATE_VALIDATION,
        "api_key_create": API_KEY_CREATE_VALIDATION,
        "oauth2_token": OAUTH2_TOKEN_VALIDATION,
    }.get(validation_type)
    
    if not validation_rules:
        validation_logger.error(f"Unknown validation type: {validation_type}")
        raise ValueError(f"Unknown validation type: {validation_type}")
        
    sanitized_data, _ = validate_and_sanitize_input(data, validation_rules, raise_exception=True)
    return sanitized_data