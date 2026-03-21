"""Entity schemas for Slite (docs/notes)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import Field, computed_field

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import BaseEntity, Breadcrumb


def _parse_iso(s: Optional[str]) -> Optional[datetime]:
    """Parse ISO 8601 string to datetime (naive UTC)."""
    if not s:
        return None
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        if dt.tzinfo:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt
    except (ValueError, TypeError):
        return None


class SliteNoteEntity(BaseEntity):
    """Schema for a Slite note (document).

    Maps to Slite's Note/NoteWithContent from the public API.
    """

    # Identity (entity_id is set from note_id by the source)
    note_id: str = AirweaveField(
        ...,
        description="Slite note ID (id from API).",
        is_entity_id=True,
    )
    name: str = AirweaveField(
        ...,
        description="Title of the note",
        is_name=True,
        embeddable=True,
    )

    # Content
    content: Optional[str] = AirweaveField(
        None,
        description="Note body in Markdown or HTML",
        embeddable=True,
    )

    # Hierarchy
    parent_note_id: Optional[str] = Field(
        None,
        description="Parent note id (null if root).",
    )

    # Timestamps (critical for incremental sync)
    created_at: Optional[datetime] = AirweaveField(
        None,
        description="When the note was created (derived if not from API).",
        embeddable=True,
        is_created_at=True,
    )
    modified_at: Optional[datetime] = AirweaveField(
        None,
        description="When the note was last edited (lastEditedAt).",
        embeddable=True,
        is_updated_at=True,
    )
    updated_at: Optional[datetime] = AirweaveField(
        None,
        description="When the note was last updated (updatedAt).",
        embeddable=True,
    )

    # Metadata
    archived_at: Optional[datetime] = AirweaveField(
        None,
        description="When the note was archived (null if not archived).",
        embeddable=True,
    )
    review_state: Optional[str] = AirweaveField(
        None,
        description="Review state: Verified, Outdated, VerificationRequested.",
        embeddable=True,
    )
    owner: Optional[Dict[str, Any]] = AirweaveField(
        None,
        description="Owner (userId or groupId) for review.",
        embeddable=True,
    )
    columns: List[str] = AirweaveField(
        default_factory=list,
        description="Column names if note is in a collection.",
        embeddable=True,
    )
    attributes: List[str] = AirweaveField(
        default_factory=list,
        description="Attribute values if note is in a collection (ordered by column).",
        embeddable=True,
    )

    # User-facing URL (unhashable; URLs can change)
    web_url_value: Optional[str] = AirweaveField(
        None,
        description="URL to open the note in Slite.",
        embeddable=False,
        unhashable=True,
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """User-facing link to the note in Slite."""
        return self.web_url_value or ""

    @classmethod
    def from_api(cls, data: Dict[str, Any]) -> SliteNoteEntity:
        """Build a note entity from full API data (GET /v1/notes/{id})."""
        note_id = data.get("id")
        last_edited = _parse_iso(data.get("lastEditedAt"))
        updated = _parse_iso(data.get("updatedAt"))
        archived_dt = _parse_iso(data.get("archivedAt")) if data.get("archivedAt") else None

        owner = data.get("owner")
        if isinstance(owner, dict):
            owner = {k: v for k, v in owner.items() if v is not None}
        else:
            owner = None

        breadcrumbs: List[Breadcrumb] = []
        parent_id = data.get("parentNoteId")
        if parent_id:
            breadcrumbs.append(
                Breadcrumb(entity_id=parent_id, name=parent_id, entity_type="SliteNoteEntity")
            )

        return cls(
            entity_id=note_id,
            breadcrumbs=breadcrumbs,
            note_id=note_id,
            name=data.get("title") or note_id,
            content=data.get("content"),
            parent_note_id=data.get("parentNoteId"),
            created_at=last_edited or updated,
            modified_at=last_edited,
            updated_at=updated,
            archived_at=archived_dt,
            review_state=data.get("reviewState"),
            owner=owner,
            columns=data.get("columns") or [],
            attributes=data.get("attributes") or [],
            web_url_value=data.get("url"),
        )
