"""AgenticSearch compiled query schema.

Represents a compiled vector database query in a DB-agnostic way.
The raw query (with embeddings) is stored separately from the display version.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, PrivateAttr


class AgenticSearchCompiledQuery(BaseModel):
    """A compiled vector database query.

    Contains both the raw executable query and a cleaned display version
    for logging/history (without embeddings which can be huge).

    The raw query is stored as a Pydantic PrivateAttr so it's excluded from
    serialization (to JSON/dict). This prevents embeddings from appearing in
    history, logs, or prompts while still being accessible for query execution.

    Attributes:
        vector_db: Name of the vector database (e.g., "vespa", "qdrant").
        display: Human-readable query string for logging (no embeddings).
        _raw: Private attribute containing the full query for execution.
    """

    vector_db: str = Field(..., description="Vector database name (e.g., 'vespa', 'qdrant')")
    display: str = Field(..., description="Human-readable query for logging (no embeddings)")

    _raw: Any = PrivateAttr()

    def __init__(self, *, raw: Any, **data: Any) -> None:
        """Initialize with raw query stored as private attribute.

        Args:
            raw: The full query object for execution (includes embeddings).
            **data: Other fields (vector_db, display).
        """
        super().__init__(**data)
        self._raw = raw

    @property
    def raw(self) -> Any:
        """Get the raw query for execution.

        Returns:
            The full query object (format depends on vector_db).
        """
        return self._raw

    def to_md(self) -> str:
        """Render for display in prompts and logs.

        Returns:
            Markdown string showing the compiled query.
        """
        return f"**Compiled Query** (Vector DB: {self.vector_db})\n\n```\n{self.display}\n```"
