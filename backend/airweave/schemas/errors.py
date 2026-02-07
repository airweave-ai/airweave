"""Shared error response schemas for the Airweave API.

This module defines standardized error response models used across all API endpoints.
These schemas provide consistent error formatting for OpenAPI documentation and
client SDK generation.
"""

from typing import List

from pydantic import BaseModel, Field


class ValidationErrorDetail(BaseModel):
    """Details about a validation error for a specific field."""

    loc: List[str] = Field(
        ...,
        description="Location of the error (e.g., ['body', 'url'])",
        json_schema_extra={"example": ["body", "url"]},
    )
    msg: str = Field(
        ...,
        description="Human-readable error message",
        json_schema_extra={"example": "Invalid URL format"},
    )
    type: str = Field(
        ...,
        description="Error type identifier",
        json_schema_extra={"example": "value_error.url"},
    )


class ValidationErrorResponse(BaseModel):
    """Response returned when request validation fails (HTTP 422).

    This occurs when the request body contains invalid data, such as
    malformed URLs, invalid event types, or missing required fields.
    """

    detail: List[ValidationErrorDetail] = Field(
        ...,
        description="List of validation errors",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "detail": [
                    {
                        "loc": ["body", "url"],
                        "msg": "Invalid URL: scheme must be http or https",
                        "type": "value_error.url.scheme",
                    },
                    {
                        "loc": ["body", "event_types"],
                        "msg": "event_types cannot be empty",
                        "type": "value_error",
                    },
                ]
            }
        }
    }


class RateLimitErrorResponse(BaseModel):
    """Response returned when rate limit is exceeded (HTTP 429).

    The API enforces rate limits to ensure fair usage. When exceeded,
    wait for the duration specified in the Retry-After header before retrying.
    """

    detail: str = Field(
        ...,
        description="Error message explaining the rate limit",
        json_schema_extra={"example": "Rate limit exceeded. Please retry after 60 seconds."},
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "detail": "Rate limit exceeded. Please retry after 60 seconds.",
            }
        }
    }


class NotFoundErrorResponse(BaseModel):
    """Response returned when a resource is not found (HTTP 404)."""

    detail: str = Field(
        ...,
        description="Error message describing what was not found",
        json_schema_extra={"example": "Resource not found"},
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "detail": "Resource not found",
            }
        }
    }


class ConflictErrorResponse(BaseModel):
    """Response returned when a resource conflict occurs (HTTP 409).

    This typically occurs when attempting to create a resource that already exists,
    or when an operation cannot be completed due to the current state of a resource.
    """

    detail: str = Field(
        ...,
        description="Error message describing the conflict",
        json_schema_extra={"example": "A resource with this identifier already exists"},
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "detail": "A resource with this identifier already exists",
            }
        }
    }
