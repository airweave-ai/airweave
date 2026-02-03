"""Spotlight-specific database schemas.

These minimal schemas define exactly what spotlight needs from the database layer.
They decouple spotlight from Airweave's API schemas, which have computed fields
and enrichments that don't map directly from the database.

The database adapter is responsible for mapping from SQLAlchemy models to these schemas.
"""

from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class SpotlightCollection(BaseModel):
    """Minimal collection info needed by spotlight."""

    id: UUID = Field(..., description="Collection UUID")
    readable_id: str = Field(..., description="Human-readable collection ID")


class SpotlightSourceConnection(BaseModel):
    """Minimal source connection info needed by spotlight."""

    short_name: str = Field(..., description="Source type identifier (e.g., 'slack', 'github')")
    sync_id: Optional[UUID] = Field(None, description="ID of the latest sync, if any")


class SpotlightSource(BaseModel):
    """Minimal source definition info needed by spotlight."""

    short_name: str = Field(..., description="Source type identifier")
    output_entity_definition_ids: list[UUID] = Field(
        default_factory=list,
        description="IDs of entity definitions this source produces",
    )


class SpotlightEntityDefinition(BaseModel):
    """Minimal entity definition info needed by spotlight."""

    id: UUID = Field(..., description="Entity definition UUID")
    name: str = Field(..., description="Entity type name (e.g., 'SlackMessage', 'GitHubIssue')")
    entity_schema: dict = Field(..., description="JSON schema with field names and descriptions")


class SpotlightEntityCount(BaseModel):
    """Entity count for a source connection."""

    count: int = Field(..., description="Number of entities of this type")
