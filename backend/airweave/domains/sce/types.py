"""SCE domain types."""

from enum import Enum
from typing import List

from pydantic import BaseModel


class ExtractedRefType(str, Enum):
    """Type of extracted reference."""

    URL = "url"
    EMAIL = "email"
    MENTION = "mention"
    TICKET_ID = "ticket_id"
    FILE_PATH = "file_path"
    PERSON = "person"
    ORG = "org"
    PRODUCT = "product"
    EVENT = "event"
    TAG = "tag"
    GPE = "gpe"
    DATE = "date"
    LAW = "law"


class ExtractedRef(BaseModel):
    """A single extracted reference from text."""

    ref_type: ExtractedRefType
    value: str

    @property
    def prefixed(self) -> str:
        """Format for storage and deduplication.

        Returns ``{ref_type}:{value}``.
        """
        return f"{self.ref_type.value}:{self.value}"


class EntityExtractionInput(BaseModel):
    """Input for entity-level extraction."""

    entity_id: str
    text: str
    entity_type: str | None = None


class EntityAnnotations(BaseModel):
    """Stores the annotations that were extracted per entity."""

    entity_id: str
    refs: List[ExtractedRef]
