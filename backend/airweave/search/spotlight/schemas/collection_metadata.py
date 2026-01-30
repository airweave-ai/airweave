"""Collection metadata schema."""

from pydantic import BaseModel, Field


class SpotlightSourceMetadata(BaseModel):
    """Source schema."""

    short_name: str = Field(..., description="Short name of the source.")
    description: str = Field(..., description="Description of the source.")
    entity_types: list[str] = Field(..., description="Entity types of the source.")
    counts: dict[str, int] = Field(
        ..., description="Counts of entities of each type in the source."
    )


class SpotlightCollectionMetadata(BaseModel):
    """Collection metadata schema."""

    collection_id: str = Field(..., description="The collection ID.")
    collection_readable_id: str = Field(..., description="The collection readable ID.")
    sources: list[SpotlightSourceMetadata] = Field(..., description="Sources of the collection.")
