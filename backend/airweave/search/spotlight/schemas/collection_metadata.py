"""Collection metadata schema."""

from pydantic import BaseModel, Field


class SpotlightEntityTypeMetadata(BaseModel):
    """Entity type metadata with fields."""

    name: str = Field(..., description="Entity type name (e.g., 'NotionPageEntity').")
    count: int = Field(..., description="Number of entities of this type.")
    fields: dict[str, str] = Field(..., description="Field names mapped to their descriptions.")

    def to_md(self) -> str:
        """Convert entity type metadata to markdown format."""
        lines = [
            f"#### {self.name} ({self.count} entities)",
            "",
            "| Field | Description |",
            "|-------|-------------|",
        ]

        for field_name, field_desc in sorted(self.fields.items()):
            # Escape pipe characters in descriptions
            escaped_desc = field_desc.replace("|", "\\|")
            lines.append(f"| {field_name} | {escaped_desc} |")

        return "\n".join(lines)


class SpotlightSourceMetadata(BaseModel):
    """Source schema."""

    short_name: str = Field(..., description="Short name of the source.")
    description: str = Field(..., description="Description of the source.")
    entity_types: list[SpotlightEntityTypeMetadata] = Field(
        ..., description="Entity types with their fields and counts."
    )

    def to_md(self) -> str:
        """Convert source metadata to markdown format."""
        lines = [
            f"### {self.short_name}",
            f"{self.description}",
            "",
        ]

        for entity_type in self.entity_types:
            lines.append(entity_type.to_md())
            lines.append("")

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
