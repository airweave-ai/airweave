"""Entity schemas for ServiceNow.

MVP entities: Incidents, Knowledge Base Articles, Change Requests,
Problem Records, Service Catalog Items.

Reference:
    ServiceNow Table API: https://www.servicenow.com/docs/r/washingtondc/api-reference/rest-apis/api-rest.html
"""

from datetime import datetime
from typing import Optional

from pydantic import computed_field

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import BaseEntity


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

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """User-facing link to the catalog item."""
        return self.web_url_value or ""
