"""HERB Documents entity schemas."""

from datetime import datetime
from typing import Optional

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import BaseEntity


class HerbDocumentEntity(BaseEntity):
    """Document (PRD, vision doc, system design, etc.) from the HERB benchmark dataset."""

    doc_id: str = AirweaveField(
        ...,
        description="HERB document ID (e.g. 'backaix_market_research_report')",
        is_entity_id=True,
    )
    title: str = AirweaveField(
        ...,
        description="Document title derived from ID",
        is_name=True,
        embeddable=True,
    )
    content: str = AirweaveField(
        ...,
        description="Full document content",
        embeddable=True,
    )
    doc_type: str = AirweaveField(
        ...,
        description="Document type (e.g. 'Market Research Report')",
        embeddable=True,
    )
    author_id: str = AirweaveField(
        ...,
        description="Author employee ID",
        embeddable=True,
    )
    author_name: Optional[str] = AirweaveField(
        None,
        description="Resolved author name from employee directory",
        embeddable=True,
    )
    feedback: Optional[str] = AirweaveField(
        None,
        description="Document feedback (present on ~200 of 400 docs)",
        embeddable=True,
    )
    document_link: Optional[str] = AirweaveField(
        None,
        description="Document URL (synthetic)",
    )
    doc_created_at: Optional[datetime] = AirweaveField(
        None,
        description="Document creation date",
        is_created_at=True,
    )
    product_name: str = AirweaveField(
        ...,
        description="HERB product name this document belongs to",
        embeddable=True,
    )
