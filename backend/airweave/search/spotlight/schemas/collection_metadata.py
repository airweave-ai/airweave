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

    def to_md(self) -> str:
        """Convert source metadata to markdown format."""
        lines = [
            f"### {self.short_name}",
            f"{self.description}",
            "",
        ]

        for entity_type in self.entity_types:
            count = self.counts.get(entity_type, 0)
            lines.append(f"- **{entity_type}**: {count} entities")

        return "\n".join(lines)


class SpotlightCollectionMetadata(BaseModel):
    """Collection metadata schema."""

    collection_id: str = Field(..., description="The collection ID.")
    collection_readable_id: str = Field(..., description="The collection readable ID.")
    sources: list[SpotlightSourceMetadata] = Field(..., description="Sources of the collection.")

    def to_md(self) -> str:
        """Convert collection metadata to markdown format for LLM context."""
        lines = [
            f"**Collection:** `{self.collection_readable_id}` (ID: `{self.collection_id}`)",
            "",
        ]

        for source in sorted(self.sources, key=lambda s: s.short_name):
            lines.append(source.to_md())
            lines.append("")

        return "\n".join(lines)
