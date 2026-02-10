"""Collection metadata schema."""

from pydantic import BaseModel, Field


class AgenticSearchEntityTypeMetadata(BaseModel):
    """Entity type metadata with fields."""

    name: str = Field(..., description="Entity type name (e.g., 'NotionPageEntity').")
    count: int = Field(..., description="Number of entities of this type.")
    fields: dict[str, str] = Field(..., description="Field names mapped to their descriptions.")

    def to_md(self) -> str:
        """Convert entity type metadata to compact markdown format.

        Shows entity type name, count, and field names as a comma-separated list.
        Field descriptions are omitted to save tokens — the field names are
        self-explanatory enough for the LLM to craft queries and filters.
        """
        field_names = ", ".join(sorted(self.fields.keys()))
        return f"- **{self.name}** ({self.count}) — fields: {field_names}"


class AgenticSearchSourceMetadata(BaseModel):
    """Source schema."""

    short_name: str = Field(..., description="Short name of the source.")
    description: str = Field(..., description="Description of the source.")
    entity_types: list[AgenticSearchEntityTypeMetadata] = Field(
        ..., description="Entity types with their fields and counts."
    )

    def to_md(self) -> str:
        """Convert source metadata to compact markdown format.

        Skips entity types with 0 entities to reduce prompt size.
        """
        # Only show entity types that actually have entities
        non_empty = [et for et in self.entity_types if et.count > 0]
        if not non_empty:
            return f"### {self.short_name}\n{self.description}\n\n*(no entities)*"

        total = sum(et.count for et in non_empty)
        lines = [
            f"### {self.short_name} ({total} entities total)",
            f"{self.description}",
            "",
        ]

        for entity_type in non_empty:
            lines.append(entity_type.to_md())

        return "\n".join(lines)


class AgenticSearchCollectionMetadata(BaseModel):
    """Collection metadata schema."""

    collection_id: str = Field(..., description="The collection ID.")
    collection_readable_id: str = Field(..., description="The collection readable ID.")
    sources: list[AgenticSearchSourceMetadata] = Field(
        ..., description="Sources of the collection."
    )

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
