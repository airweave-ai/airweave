"""Base cursor class for incremental sync tracking."""

from pydantic import BaseModel, ConfigDict


class BaseCursor(BaseModel):
    """Base cursor class for incremental sync tracking.

    Leverages Pydantic's built-in serialization:
    - model_dump() for dict serialization
    - model_validate() for deserialization
    - JSON schema generation

    All cursor classes should inherit from this base class.
    """

    model_config = ConfigDict(
        # Allow extra fields for forward compatibility
        extra="allow",
        # Use JSON serialization mode by default
        ser_json_timedelta="iso8601",
    )




