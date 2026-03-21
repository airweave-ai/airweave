"""Entity schemas for ServiceNow.

MVP entities: Incidents, Knowledge Base Articles, Change Requests,
Problem Records, Service Catalog Items.

Reference:
    ServiceNow Table API: https://www.servicenow.com/docs/r/washingtondc/api-reference/rest-apis/api-rest.html
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import computed_field

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import BaseEntity


def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
    """Parse ServiceNow datetime string (ISO-like) to datetime."""
    if not value:
        return None
    try:
        s = value.strip().replace("Z", "+00:00")
        if "T" in s:
            return datetime.fromisoformat(s)
        return datetime.strptime(s[:19], "%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return None


def _display_value(record: Dict[str, Any], key: str) -> Optional[str]:
    """Get display value from record; ServiceNow can return {value, display_value}."""
    raw = record.get(key)
    if raw is None:
        return None
    if isinstance(raw, dict):
        return raw.get("display_value") or raw.get("value")
    return str(raw) if raw else None


def _raw_value(record: Dict[str, Any], key: str) -> Optional[str]:
    """Get raw value from record."""
    raw = record.get(key)
    if raw is None:
        return None
    if isinstance(raw, dict):
        return raw.get("value") or raw.get("display_value")
    return str(raw) if raw else None


def _parse_bool(value: Any) -> Optional[bool]:
    """Parse ServiceNow boolean-like value (bool, str 'true'/'false', 0/1) to bool or None."""
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in ("true", "1", "yes")
    if isinstance(value, (int, float)):
        return bool(value)
    return None


def _build_record_url(base_url: str, table: str, sys_id: str) -> str:
    """Build user-facing URL for a record (UI navigates to list with sys_id)."""
    return f"{base_url}/now/nav/ui/classic/params/target/{table}.do%3Fsys_id={sys_id}"


class ServiceNowIncidentEntity(BaseEntity):
    """Schema for ServiceNow Incident.

    Table: incident
    """

    sys_id: str = AirweaveField(
        ...,
        description="Unique system ID of the incident.",
        embeddable=False,
        is_entity_id=True,
    )
    number: str = AirweaveField(
        ...,
        description="Human-readable incident number (e.g. INC0010001).",
        embeddable=True,
        is_name=True,
    )
    short_description: Optional[str] = AirweaveField(
        None,
        description="Short description of the incident.",
        embeddable=True,
    )
    description: Optional[str] = AirweaveField(
        None,
        description="Full description of the incident.",
        embeddable=True,
    )
    state: Optional[str] = AirweaveField(
        None,
        description="Incident state (e.g. New, In Progress, Resolved).",
        embeddable=True,
    )
    priority: Optional[str] = AirweaveField(
        None,
        description="Priority level.",
        embeddable=True,
    )
    category: Optional[str] = AirweaveField(
        None,
        description="Category of the incident.",
        embeddable=True,
    )
    assigned_to_name: Optional[str] = AirweaveField(
        None,
        description="Name of the assignee.",
        embeddable=True,
    )
    caller_id_name: Optional[str] = AirweaveField(
        None,
        description="Name of the caller/requester.",
        embeddable=True,
    )
    created_at: Optional[datetime] = AirweaveField(
        None,
        description="When the incident was created.",
        embeddable=True,
        is_created_at=True,
    )
    updated_at: Optional[datetime] = AirweaveField(
        None,
        description="When the incident was last updated.",
        embeddable=True,
        is_updated_at=True,
    )
    web_url_value: Optional[str] = AirweaveField(
        None,
        description="URL to view the incident in ServiceNow.",
        embeddable=False,
        unhashable=True,
    )

    @classmethod
    def from_api(cls, data: Dict[str, Any], *, base_url: str) -> ServiceNowIncidentEntity:
        """Construct from a ServiceNow Table API ``incident`` record."""
        sys_id = _raw_value(data, "sys_id") or data.get("sys_id", "")
        number = _display_value(data, "number") or _raw_value(data, "number") or sys_id
        created = _parse_datetime(_raw_value(data, "sys_created_on"))
        updated = _parse_datetime(_raw_value(data, "sys_updated_on"))
        return cls(
            entity_id=sys_id,
            breadcrumbs=[],
            name=number,
            sys_id=sys_id,
            number=number,
            short_description=_display_value(data, "short_description")
            or _raw_value(data, "short_description"),
            description=_display_value(data, "description") or _raw_value(data, "description"),
            state=_display_value(data, "state") or _raw_value(data, "state"),
            priority=_display_value(data, "priority") or _raw_value(data, "priority"),
            category=_display_value(data, "category") or _raw_value(data, "category"),
            assigned_to_name=_display_value(data, "assigned_to"),
            caller_id_name=_display_value(data, "caller_id"),
            created_at=created,
            updated_at=updated,
            web_url_value=_build_record_url(base_url, "incident", sys_id),
        )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """User-facing link to the incident."""
        return self.web_url_value or ""


class ServiceNowKnowledgeArticleEntity(BaseEntity):
    """Schema for ServiceNow Knowledge Base Article.

    Table: kb_knowledge
    """

    sys_id: str = AirweaveField(
        ...,
        description="Unique system ID of the article.",
        embeddable=False,
        is_entity_id=True,
    )
    number: str = AirweaveField(
        ...,
        description="Article number (e.g. KB0010001).",
        embeddable=True,
        is_name=True,
    )
    short_description: Optional[str] = AirweaveField(
        None,
        description="Short description or title of the article.",
        embeddable=True,
    )
    text: Optional[str] = AirweaveField(
        None,
        description="Full text content of the article.",
        embeddable=True,
    )
    author_name: Optional[str] = AirweaveField(
        None,
        description="Name of the author.",
        embeddable=True,
    )
    kb_knowledge_base_name: Optional[str] = AirweaveField(
        None,
        description="Knowledge base name.",
        embeddable=True,
    )
    category_name: Optional[str] = AirweaveField(
        None,
        description="Category of the article.",
        embeddable=True,
    )
    workflow_state: Optional[str] = AirweaveField(
        None,
        description="Workflow state (e.g. published, draft).",
        embeddable=True,
    )
    created_at: Optional[datetime] = AirweaveField(
        None,
        description="When the article was created.",
        embeddable=True,
        is_created_at=True,
    )
    updated_at: Optional[datetime] = AirweaveField(
        None,
        description="When the article was last updated.",
        embeddable=True,
        is_updated_at=True,
    )
    web_url_value: Optional[str] = AirweaveField(
        None,
        description="URL to view the article in ServiceNow.",
        embeddable=False,
        unhashable=True,
    )

    @classmethod
    def from_api(cls, data: Dict[str, Any], *, base_url: str) -> ServiceNowKnowledgeArticleEntity:
        """Construct from a ServiceNow Table API ``kb_knowledge`` record."""
        sys_id = _raw_value(data, "sys_id") or data.get("sys_id", "")
        number = _display_value(data, "number") or _raw_value(data, "number") or sys_id
        created = _parse_datetime(_raw_value(data, "sys_created_on"))
        updated = _parse_datetime(_raw_value(data, "sys_updated_on"))
        return cls(
            entity_id=sys_id,
            breadcrumbs=[],
            name=number,
            sys_id=sys_id,
            number=number,
            short_description=_display_value(data, "short_description")
            or _raw_value(data, "short_description"),
            text=_display_value(data, "text") or _raw_value(data, "text"),
            author_name=_display_value(data, "author"),
            kb_knowledge_base_name=_display_value(data, "kb_knowledge_base"),
            category_name=_display_value(data, "category"),
            workflow_state=_display_value(data, "workflow_state")
            or _raw_value(data, "workflow_state"),
            created_at=created,
            updated_at=updated,
            web_url_value=_build_record_url(base_url, "kb_knowledge", sys_id),
        )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """User-facing link to the article."""
        return self.web_url_value or ""


class ServiceNowChangeRequestEntity(BaseEntity):
    """Schema for ServiceNow Change Request.

    Table: change_request
    """

    sys_id: str = AirweaveField(
        ...,
        description="Unique system ID of the change request.",
        embeddable=False,
        is_entity_id=True,
    )
    number: str = AirweaveField(
        ...,
        description="Change request number (e.g. CHG0010001).",
        embeddable=True,
        is_name=True,
    )
    short_description: Optional[str] = AirweaveField(
        None,
        description="Short description of the change.",
        embeddable=True,
    )
    description: Optional[str] = AirweaveField(
        None,
        description="Full description of the change.",
        embeddable=True,
    )
    state: Optional[str] = AirweaveField(
        None,
        description="Change state (e.g. New, Assess, Authorize, Scheduled).",
        embeddable=True,
    )
    phase: Optional[str] = AirweaveField(
        None,
        description="Change phase.",
        embeddable=True,
    )
    priority: Optional[str] = AirweaveField(
        None,
        description="Priority level.",
        embeddable=True,
    )
    type: Optional[str] = AirweaveField(
        None,
        description="Type of change (normal, standard, emergency).",
        embeddable=True,
    )
    assigned_to_name: Optional[str] = AirweaveField(
        None,
        description="Name of the assignee.",
        embeddable=True,
    )
    requested_by_name: Optional[str] = AirweaveField(
        None,
        description="Name of the requester.",
        embeddable=True,
    )
    created_at: Optional[datetime] = AirweaveField(
        None,
        description="When the change was created.",
        embeddable=True,
        is_created_at=True,
    )
    updated_at: Optional[datetime] = AirweaveField(
        None,
        description="When the change was last updated.",
        embeddable=True,
        is_updated_at=True,
    )
    web_url_value: Optional[str] = AirweaveField(
        None,
        description="URL to view the change request in ServiceNow.",
        embeddable=False,
        unhashable=True,
    )

    @classmethod
    def from_api(cls, data: Dict[str, Any], *, base_url: str) -> ServiceNowChangeRequestEntity:
        """Construct from a ServiceNow Table API ``change_request`` record."""
        sys_id = _raw_value(data, "sys_id") or data.get("sys_id", "")
        number = _display_value(data, "number") or _raw_value(data, "number") or sys_id
        created = _parse_datetime(_raw_value(data, "sys_created_on"))
        updated = _parse_datetime(_raw_value(data, "sys_updated_on"))
        return cls(
            entity_id=sys_id,
            breadcrumbs=[],
            name=number,
            sys_id=sys_id,
            number=number,
            short_description=_display_value(data, "short_description")
            or _raw_value(data, "short_description"),
            description=_display_value(data, "description") or _raw_value(data, "description"),
            state=_display_value(data, "state") or _raw_value(data, "state"),
            phase=_display_value(data, "phase") or _raw_value(data, "phase"),
            priority=_display_value(data, "priority") or _raw_value(data, "priority"),
            type=_display_value(data, "type") or _raw_value(data, "type"),
            assigned_to_name=_display_value(data, "assigned_to"),
            requested_by_name=_display_value(data, "requested_by"),
            created_at=created,
            updated_at=updated,
            web_url_value=_build_record_url(base_url, "change_request", sys_id),
        )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """User-facing link to the change request."""
        return self.web_url_value or ""


class ServiceNowProblemEntity(BaseEntity):
    """Schema for ServiceNow Problem Record.

    Table: problem
    """

    sys_id: str = AirweaveField(
        ...,
        description="Unique system ID of the problem.",
        embeddable=False,
        is_entity_id=True,
    )
    number: str = AirweaveField(
        ...,
        description="Problem number (e.g. PRB0010001).",
        embeddable=True,
        is_name=True,
    )
    short_description: Optional[str] = AirweaveField(
        None,
        description="Short description of the problem.",
        embeddable=True,
    )
    description: Optional[str] = AirweaveField(
        None,
        description="Full description of the problem.",
        embeddable=True,
    )
    state: Optional[str] = AirweaveField(
        None,
        description="Problem state.",
        embeddable=True,
    )
    priority: Optional[str] = AirweaveField(
        None,
        description="Priority level.",
        embeddable=True,
    )
    category: Optional[str] = AirweaveField(
        None,
        description="Category of the problem.",
        embeddable=True,
    )
    assigned_to_name: Optional[str] = AirweaveField(
        None,
        description="Name of the assignee.",
        embeddable=True,
    )
    created_at: Optional[datetime] = AirweaveField(
        None,
        description="When the problem was created.",
        embeddable=True,
        is_created_at=True,
    )
    updated_at: Optional[datetime] = AirweaveField(
        None,
        description="When the problem was last updated.",
        embeddable=True,
        is_updated_at=True,
    )
    web_url_value: Optional[str] = AirweaveField(
        None,
        description="URL to view the problem in ServiceNow.",
        embeddable=False,
        unhashable=True,
    )

    @classmethod
    def from_api(cls, data: Dict[str, Any], *, base_url: str) -> ServiceNowProblemEntity:
        """Construct from a ServiceNow Table API ``problem`` record."""
        sys_id = _raw_value(data, "sys_id") or data.get("sys_id", "")
        number = _display_value(data, "number") or _raw_value(data, "number") or sys_id
        created = _parse_datetime(_raw_value(data, "sys_created_on"))
        updated = _parse_datetime(_raw_value(data, "sys_updated_on"))
        return cls(
            entity_id=sys_id,
            breadcrumbs=[],
            name=number,
            sys_id=sys_id,
            number=number,
            short_description=_display_value(data, "short_description")
            or _raw_value(data, "short_description"),
            description=_display_value(data, "description") or _raw_value(data, "description"),
            state=_display_value(data, "state") or _raw_value(data, "state"),
            priority=_display_value(data, "priority") or _raw_value(data, "priority"),
            category=_display_value(data, "category") or _raw_value(data, "category"),
            assigned_to_name=_display_value(data, "assigned_to"),
            created_at=created,
            updated_at=updated,
            web_url_value=_build_record_url(base_url, "problem", sys_id),
        )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """User-facing link to the problem."""
        return self.web_url_value or ""


class ServiceNowCatalogItemEntity(BaseEntity):
    """Schema for ServiceNow Service Catalog Item.

    Table: sc_cat_item
    """

    sys_id: str = AirweaveField(
        ...,
        description="Unique system ID of the catalog item.",
        embeddable=False,
        is_entity_id=True,
    )
    name: str = AirweaveField(
        ...,
        description="Name of the catalog item.",
        embeddable=True,
        is_name=True,
    )
    short_description: Optional[str] = AirweaveField(
        None,
        description="Short description of the catalog item.",
        embeddable=True,
    )
    description: Optional[str] = AirweaveField(
        None,
        description="Full description.",
        embeddable=True,
    )
    category_name: Optional[str] = AirweaveField(
        None,
        description="Category name.",
        embeddable=True,
    )
    price: Optional[str] = AirweaveField(
        None,
        description="Price if applicable.",
        embeddable=True,
    )
    active: Optional[bool] = AirweaveField(
        None,
        description="Whether the item is active.",
        embeddable=False,
    )
    created_at: Optional[datetime] = AirweaveField(
        None,
        description="When the item was created.",
        embeddable=True,
        is_created_at=True,
    )
    updated_at: Optional[datetime] = AirweaveField(
        None,
        description="When the item was last updated.",
        embeddable=True,
        is_updated_at=True,
    )
    web_url_value: Optional[str] = AirweaveField(
        None,
        description="URL to view the catalog item in ServiceNow.",
        embeddable=False,
        unhashable=True,
    )

    @classmethod
    def from_api(cls, data: Dict[str, Any], *, base_url: str) -> ServiceNowCatalogItemEntity:
        """Construct from a ServiceNow Table API ``sc_cat_item`` record."""
        sys_id = _raw_value(data, "sys_id") or data.get("sys_id", "")
        name = _display_value(data, "name") or _raw_value(data, "name") or sys_id
        created = _parse_datetime(_raw_value(data, "sys_created_on"))
        updated = _parse_datetime(_raw_value(data, "sys_updated_on"))
        active_raw = data.get("active")
        if isinstance(active_raw, dict):
            active_raw = active_raw.get("value") if active_raw else None
        return cls(
            entity_id=sys_id,
            breadcrumbs=[],
            name=name,
            sys_id=sys_id,
            short_description=_display_value(data, "short_description")
            or _raw_value(data, "short_description"),
            description=_display_value(data, "description") or _raw_value(data, "description"),
            category_name=_display_value(data, "category"),
            price=_display_value(data, "price") or _raw_value(data, "price"),
            active=_parse_bool(active_raw),
            created_at=created,
            updated_at=updated,
            web_url_value=_build_record_url(base_url, "sc_cat_item", sys_id),
        )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """User-facing link to the catalog item."""
        return self.web_url_value or ""
