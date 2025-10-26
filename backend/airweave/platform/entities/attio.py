"""Attio entity schemas.

Attio is a CRM platform that organizes data into Objects (Companies, People, Deals)
and Lists (custom collections). Each object/list contains Records with custom attributes.
"""

from typing import Any, Dict, List, Optional

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import BaseEntity


class AttioObjectEntity(BaseEntity):
    """Schema for Attio Object (e.g., Companies, People, Deals).

    Objects are the core data types in Attio's CRM.

    Reference:
        https://docs.attio.com/rest-api/endpoint-reference/objects
    """

    # Base fields are inherited and set during entity creation:
    # - entity_id (the object ID)
    # - breadcrumbs (empty - objects are top-level)
    # - name (from singular_noun)
    # - created_at (from created_at timestamp)
    # - updated_at (None - objects don't have update timestamp)

    # API fields
    singular_noun: str = AirweaveField(
        ..., description="Singular name of the object (e.g., 'Company')", embeddable=True
    )
    plural_noun: str = AirweaveField(
        ..., description="Plural name of the object (e.g., 'Companies')", embeddable=True
    )
    api_slug: str = AirweaveField(..., description="API slug for the object", embeddable=False)
    icon: Optional[str] = AirweaveField(
        None, description="Icon representing this object", embeddable=False
    )


class AttioListEntity(BaseEntity):
    """Schema for Attio List.

    Lists are custom collections that can organize any type of record.

    Reference:
        https://docs.attio.com/rest-api/endpoint-reference/lists
    """

    # Base fields are inherited and set during entity creation:
    # - entity_id (the list ID)
    # - breadcrumbs (empty - lists are top-level)
    # - name (from list name)
    # - created_at (from created_at timestamp)
    # - updated_at (None - lists don't have update timestamp)

    # API fields
    workspace_id: str = AirweaveField(
        ..., description="ID of the workspace this list belongs to", embeddable=False
    )
    parent_object: Optional[str] = AirweaveField(
        None, description="Parent object type if applicable", embeddable=True
    )


class AttioRecordEntity(BaseEntity):
    """Schema for Attio Record.

    Records are individual entries in Objects or Lists (e.g., a specific company, person, or deal).

    Reference:
        https://docs.attio.com/rest-api/endpoint-reference/records
    """

    # Base fields are inherited and set during entity creation:
    # - entity_id (the record ID)
    # - breadcrumbs (object or list breadcrumb)
    # - name (from name attribute or record ID)
    # - created_at (from created_at timestamp)
    # - updated_at (from updated_at timestamp)

    # API fields
    object_id: Optional[str] = AirweaveField(
        None, description="ID of the object this record belongs to", embeddable=False
    )
    list_id: Optional[str] = AirweaveField(
        None, description="ID of the list this record belongs to", embeddable=False
    )
    parent_object_name: Optional[str] = AirweaveField(
        None, description="Name of the parent object/list", embeddable=True
    )

    # Dynamic attributes - these are the actual CRM data
    description: Optional[str] = AirweaveField(
        None, description="Description of the record", embeddable=True
    )
    email_addresses: List[Dict[str, Any]] = AirweaveField(
        default_factory=list,
        description="Email addresses associated with this record",
        embeddable=True,
    )
    phone_numbers: List[Dict[str, Any]] = AirweaveField(
        default_factory=list,
        description="Phone numbers associated with this record",
        embeddable=True,
    )
    domains: List[str] = AirweaveField(
        default_factory=list, description="Domain names (for company records)", embeddable=True
    )
    categories: List[str] = AirweaveField(
        default_factory=list, description="Categories/tags for this record", embeddable=True
    )

    # Custom attributes stored as structured data
    attributes: Dict[str, Any] = AirweaveField(
        default_factory=dict,
        description="Custom attributes and their values",
        embeddable=True,
    )

    # Metadata
    permalink_url: Optional[str] = AirweaveField(
        None, description="URL to view this record in Attio", embeddable=False
    )


class AttioNoteEntity(BaseEntity):
    """Schema for Attio Note.

    Notes are text entries attached to records for context and collaboration.

    Reference:
        https://docs.attio.com/rest-api/endpoint-reference/notes
    """

    # Base fields are inherited and set during entity creation:
    # - entity_id (the note ID)
    # - breadcrumbs (object/list and record breadcrumbs)
    # - name (from title or content preview)
    # - created_at (from created_at timestamp)
    # - updated_at (from updated_at timestamp)

    # API fields
    parent_record_id: str = AirweaveField(
        ..., description="ID of the record this note is attached to", embeddable=False
    )
    parent_object: Optional[str] = AirweaveField(
        None, description="Type of parent object", embeddable=False
    )

    # Note content
    title: Optional[str] = AirweaveField(None, description="Title of the note", embeddable=True)
    content: str = AirweaveField(..., description="Content of the note", embeddable=True)
    format: Optional[str] = AirweaveField(
        None, description="Format of the note (plaintext, markdown, etc.)", embeddable=False
    )

    # Author information
    author: Optional[Dict[str, Any]] = AirweaveField(
        None, description="User who created this note", embeddable=True
    )

    # Metadata
    permalink_url: Optional[str] = AirweaveField(
        None, description="URL to view this note in Attio", embeddable=False
    )


# Note: AttioCommentEntity was removed because the Attio API does not provide
# a way to fetch comments for notes through their public REST API.
# Comments are visible in the Attio UI but not accessible via /v2/threads or any other endpoint.
