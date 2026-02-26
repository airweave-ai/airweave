"""Connect session schemas for frontend integration flows.

These schemas support short-lived session tokens that enable
end customers to manage source connections via a hosted UI.
"""

from datetime import datetime
from enum import Enum
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ConnectSessionMode(str, Enum):
    """Mode for connect session determining allowed operations.

    - ALL: Can perform all operations (connect, manage, reauth)
    - CONNECT: Can only add new connections
    - MANAGE: Can only view/delete existing connections
    - REAUTH: Can only re-authenticate existing connections
    """

    ALL = "all"
    CONNECT = "connect"
    MANAGE = "manage"
    REAUTH = "reauth"


class ConnectSessionCreate(BaseModel):
    """Schema for creating a new connect session.

    The session token grants temporary access to manage source connections
    within a specific collection.
    """

    readable_collection_id: str = Field(
        ...,
        description="The readable ID of the collection to grant access to",
        examples=["finance-data-ab123"],
    )
    allowed_integrations: Optional[List[str]] = Field(
        None,
        description=(
            "Optional list of source short_names to restrict which integrations "
            "can be connected. If not provided, all integrations are allowed."
        ),
        examples=[["slack", "github", "notion"]],
    )
    mode: ConnectSessionMode = Field(
        ConnectSessionMode.ALL,
        description="Session mode determining allowed operations",
    )
    end_user_id: Optional[str] = Field(
        None,
        description=(
            "Optional identifier for the end user in your system. This is included "
            "in the session token and can be used for audit tracking and filtering."
        ),
        examples=["user_123", "cust_abc123"],
    )

    class Config:
        """Pydantic configuration."""

        from_attributes = True


class ConnectSessionResponse(BaseModel):
    """Response returned when creating a connect session.

    Contains the session token that should be passed to the frontend SDK.
    """

    session_id: UUID = Field(
        ...,
        description="Unique identifier for this session",
    )
    session_token: str = Field(
        ...,
        description="HMAC-signed token to use for authentication in subsequent requests",
    )
    expires_at: datetime = Field(
        ...,
        description="Timestamp when this session expires (typically 10 minutes)",
    )

    class Config:
        """Pydantic configuration."""

        from_attributes = True


class ConnectSessionContext(BaseModel):
    """Decoded session context from a validated token.

    This is returned by GET /connect/sessions and used internally
    for authorization in session-authenticated endpoints.
    """

    session_id: UUID = Field(
        ...,
        description="Unique identifier for this session",
    )
    organization_id: UUID = Field(
        ...,
        description="Organization that owns this session",
    )
    collection_id: str = Field(
        ...,
        description="Readable collection ID this session grants access to",
    )
    allowed_integrations: Optional[List[str]] = Field(
        None,
        description="List of allowed integration short_names, or None for all",
    )
    mode: ConnectSessionMode = Field(
        ...,
        description="Session mode determining allowed operations",
    )
    end_user_id: Optional[str] = Field(
        None,
        description="End user identifier from your system, if provided during session creation",
    )
    expires_at: datetime = Field(
        ...,
        description="Timestamp when this session expires",
    )

    class Config:
        """Pydantic configuration."""

        from_attributes = True
