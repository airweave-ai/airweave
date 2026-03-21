"""Linear entity schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import computed_field

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import BaseEntity, Breadcrumb, FileEntity


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    """Parse Linear ISO8601 timestamps into timezone-aware datetimes."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _team_breadcrumbs(team_ids: List[str], team_names: List[str]) -> List[Breadcrumb]:
    """Build Breadcrumb list from parallel team ID / name lists."""
    return [
        Breadcrumb(entity_id=tid, name=tname or "Team", entity_type="LinearTeamEntity")
        for tid, tname in zip(team_ids, team_names, strict=False)
        if tid
    ]


class LinearTeamEntity(BaseEntity):
    """Schema for Linear team entities."""

    team_id: str = AirweaveField(
        ..., description="Unique Linear ID for the team.", is_entity_id=True
    )
    team_name: str = AirweaveField(
        ..., description="Display name of the team.", embeddable=True, is_name=True
    )
    created_time: datetime = AirweaveField(
        ..., description="When the team was created.", is_created_at=True
    )
    updated_time: datetime = AirweaveField(
        ..., description="When the team was last updated.", is_updated_at=True
    )
    key: str = AirweaveField(..., description="The team's unique key used in URLs", embeddable=True)
    description: Optional[str] = AirweaveField(
        None, description="The team's description", embeddable=True
    )
    color: Optional[str] = AirweaveField(None, description="The team's color", embeddable=False)
    icon: Optional[str] = AirweaveField(None, description="The icon of the team", embeddable=False)
    private: Optional[bool] = AirweaveField(
        None, description="Whether the team is private or not", embeddable=False
    )
    timezone: Optional[str] = AirweaveField(
        None, description="The timezone of the team", embeddable=False
    )
    parent_id: Optional[str] = AirweaveField(
        None, description="ID of the parent team, if this is a sub-team", embeddable=False
    )
    parent_name: Optional[str] = AirweaveField(
        None, description="Name of the parent team, if this is a sub-team", embeddable=True
    )
    issue_count: Optional[int] = AirweaveField(
        None, description="Number of issues in the team", embeddable=False
    )
    web_url_value: Optional[str] = AirweaveField(
        None, description="URL to view the team in Linear", embeddable=False, unhashable=True
    )

    @classmethod
    def from_api(cls, data: Dict[str, Any]) -> LinearTeamEntity:
        """Construct from a Linear GraphQL ``teams`` node."""
        team_id = data["id"]
        team_name = data.get("name", "")
        team_key = data.get("key", "")
        parent = data.get("parent") or {}
        created = _parse_dt(data.get("createdAt")) or datetime.utcnow()
        updated = _parse_dt(data.get("updatedAt")) or created

        return cls(
            entity_id=team_id,
            breadcrumbs=[
                Breadcrumb(
                    entity_id=team_id,
                    name=team_name or team_key or "Team",
                    entity_type=cls.__name__,
                )
            ],
            name=team_name,
            created_at=created,
            updated_at=updated,
            team_id=team_id,
            team_name=team_name,
            created_time=created,
            updated_time=updated,
            key=team_key,
            description=data.get("description", ""),
            color=data.get("color", ""),
            icon=data.get("icon", ""),
            private=data.get("private", False),
            timezone=data.get("timezone", ""),
            parent_id=parent.get("id", ""),
            parent_name=parent.get("name", ""),
            issue_count=data.get("issueCount", 0),
            web_url_value=f"https://linear.app/team/{team_key}",
        )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Browser URL for the team."""
        return self.web_url_value or ""


class LinearProjectEntity(BaseEntity):
    """Schema for Linear project entities."""

    project_id: str = AirweaveField(
        ..., description="Unique Linear ID of the project.", is_entity_id=True
    )
    project_name: str = AirweaveField(
        ..., description="Display name of the project.", embeddable=True, is_name=True
    )
    created_time: datetime = AirweaveField(
        ..., description="When the project was created.", is_created_at=True
    )
    updated_time: datetime = AirweaveField(
        ..., description="When the project was last updated.", is_updated_at=True
    )
    slug_id: str = AirweaveField(..., description="The project's unique URL slug", embeddable=True)
    description: Optional[str] = AirweaveField(
        None, description="The project's description", embeddable=True
    )
    priority: Optional[int] = AirweaveField(
        None, description="The priority level of the project", embeddable=False
    )
    state: Optional[str] = AirweaveField(
        None, description="The current state/status name of the project", embeddable=True
    )
    completed_at: Optional[Any] = AirweaveField(
        None, description="When the project was completed, if applicable", embeddable=False
    )
    started_at: Optional[Any] = AirweaveField(
        None, description="When the project was started, if applicable", embeddable=False
    )
    target_date: Optional[str] = AirweaveField(
        None, description="The estimated completion date of the project", embeddable=True
    )
    start_date: Optional[str] = AirweaveField(
        None, description="The estimated start date of the project", embeddable=True
    )
    team_ids: Optional[List[str]] = AirweaveField(
        None, description="IDs of the teams this project belongs to", embeddable=False
    )
    team_names: Optional[List[str]] = AirweaveField(
        None, description="Names of the teams this project belongs to", embeddable=True
    )
    progress: Optional[float] = AirweaveField(
        None, description="The overall progress of the project", embeddable=False
    )
    lead: Optional[str] = AirweaveField(
        None, description="Name of the project lead, if any", embeddable=True
    )
    web_url_value: Optional[str] = AirweaveField(
        None, description="URL to view the project in Linear", embeddable=False, unhashable=True
    )

    @classmethod
    def from_api(cls, data: Dict[str, Any]) -> LinearProjectEntity:
        """Construct from a Linear GraphQL ``projects`` node."""
        project_id = data["id"]
        project_name = data.get("name", "")
        created = _parse_dt(data.get("createdAt")) or datetime.utcnow()
        updated = _parse_dt(data.get("updatedAt")) or created

        team_ids = [t["id"] for t in data.get("teams", {}).get("nodes", []) if t.get("id")]
        team_names = [t.get("name", "") for t in data.get("teams", {}).get("nodes", [])]
        lead_obj = data.get("lead") or {}

        return cls(
            entity_id=project_id,
            breadcrumbs=_team_breadcrumbs(team_ids, team_names),
            name=project_name,
            created_at=created,
            updated_at=updated,
            project_id=project_id,
            project_name=project_name,
            created_time=created,
            updated_time=updated,
            slug_id=data.get("slugId", ""),
            description=data.get("description"),
            priority=data.get("priority"),
            state=data.get("state"),
            completed_at=_parse_dt(data.get("completedAt")),
            started_at=_parse_dt(data.get("startedAt")),
            target_date=data.get("targetDate"),
            start_date=data.get("startDate"),
            team_ids=team_ids or None,
            team_names=team_names or None,
            progress=data.get("progress"),
            lead=lead_obj.get("name"),
            web_url_value=f"https://linear.app/project/{data.get('slugId', '')}",
        )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Browser URL for the project."""
        return self.web_url_value or ""


class LinearUserEntity(BaseEntity):
    """Schema for Linear user entities."""

    user_id: str = AirweaveField(
        ..., description="Unique Linear ID for the user.", is_entity_id=True
    )
    display_name: str = AirweaveField(
        ...,
        description="The user's display name, unique within the organization.",
        embeddable=True,
        is_name=True,
    )
    created_time: datetime = AirweaveField(
        ..., description="When the user account was created.", is_created_at=True
    )
    updated_time: datetime = AirweaveField(
        ..., description="When the user account was last updated.", is_updated_at=True
    )
    email: str = AirweaveField(..., description="The user's email address", embeddable=True)
    avatar_url: Optional[str] = AirweaveField(
        None, description="URL to the user's avatar image", embeddable=False
    )
    description: Optional[str] = AirweaveField(
        None, description="A short description of the user", embeddable=True
    )
    timezone: Optional[str] = AirweaveField(
        None, description="The local timezone of the user", embeddable=False
    )
    active: Optional[bool] = AirweaveField(
        None, description="Whether the user account is active or disabled", embeddable=False
    )
    admin: Optional[bool] = AirweaveField(
        None, description="Whether the user is an organization administrator", embeddable=False
    )
    guest: Optional[bool] = AirweaveField(
        None, description="Whether the user is a guest with limited access", embeddable=False
    )
    last_seen: Optional[Any] = AirweaveField(
        None, description="The last time the user was seen online", embeddable=False
    )
    status_emoji: Optional[str] = AirweaveField(
        None, description="The emoji to represent the user's current status", embeddable=False
    )
    status_label: Optional[str] = AirweaveField(
        None, description="The label of the user's current status", embeddable=True
    )
    status_until_at: Optional[Any] = AirweaveField(
        None, description="Date at which the user's status should be cleared", embeddable=False
    )
    created_issue_count: Optional[int] = AirweaveField(
        None, description="Number of issues created by the user", embeddable=False
    )
    team_ids: Optional[List[str]] = AirweaveField(
        None, description="IDs of the teams this user belongs to", embeddable=False
    )
    team_names: Optional[List[str]] = AirweaveField(
        None, description="Names of the teams this user belongs to", embeddable=True
    )
    web_url_value: Optional[str] = AirweaveField(
        None, description="URL to view the user in Linear", embeddable=False, unhashable=True
    )

    @classmethod
    def from_api(cls, data: Dict[str, Any]) -> LinearUserEntity:
        """Construct from a Linear GraphQL ``users`` node."""
        user_id = data["id"]
        user_name = data.get("name", "")
        display_name = data.get("displayName", "")
        created = _parse_dt(data.get("createdAt")) or datetime.utcnow()
        updated = _parse_dt(data.get("updatedAt")) or created

        team_ids = [t["id"] for t in data.get("teams", {}).get("nodes", []) if t.get("id")]
        team_names = [t.get("name", "") for t in data.get("teams", {}).get("nodes", [])]
        display_label = display_name or user_name or data.get("email") or user_id

        return cls(
            entity_id=user_id,
            breadcrumbs=_team_breadcrumbs(team_ids, team_names),
            name=user_name or display_label,
            created_at=created,
            updated_at=updated,
            user_id=user_id,
            display_name=display_label,
            created_time=created,
            updated_time=updated,
            email=data.get("email"),
            avatar_url=data.get("avatarUrl"),
            description=data.get("description"),
            timezone=data.get("timezone"),
            active=data.get("active"),
            admin=data.get("admin"),
            guest=data.get("guest"),
            last_seen=data.get("lastSeen"),
            status_emoji=data.get("statusEmoji"),
            status_label=data.get("statusLabel"),
            status_until_at=data.get("statusUntilAt"),
            created_issue_count=data.get("createdIssueCount"),
            team_ids=team_ids or None,
            team_names=team_names or None,
            web_url_value=f"https://linear.app/u/{user_id}",
        )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Browser URL for the user."""
        return self.web_url_value or ""


class LinearIssueEntity(BaseEntity):
    """Schema for Linear issue entities."""

    issue_id: str = AirweaveField(
        ..., description="Unique Linear ID of the issue.", is_entity_id=True
    )
    identifier: str = AirweaveField(
        ..., description="The unique identifier of the issue (e.g., 'ENG-123').", embeddable=True
    )
    title: str = AirweaveField(
        ..., description="The title of the issue.", embeddable=True, is_name=True
    )
    created_time: datetime = AirweaveField(
        ..., description="When the issue was created.", is_created_at=True
    )
    updated_time: datetime = AirweaveField(
        ..., description="When the issue was last updated.", is_updated_at=True
    )
    description: Optional[str] = AirweaveField(
        None, description="The description/content of the issue", embeddable=True
    )
    priority: Optional[int] = AirweaveField(
        None, description="The priority level of the issue", embeddable=False
    )
    state: Optional[str] = AirweaveField(
        None, description="The current state/status name of the issue", embeddable=True
    )
    completed_at: Optional[Any] = AirweaveField(
        None, description="When the issue was completed, if applicable", embeddable=False
    )
    due_date: Optional[str] = AirweaveField(
        None, description="The due date for the issue, if set", embeddable=True
    )
    team_id: Optional[str] = AirweaveField(
        None, description="ID of the team this issue belongs to", embeddable=False
    )
    team_name: Optional[str] = AirweaveField(
        None, description="Name of the team this issue belongs to", embeddable=True
    )
    project_id: Optional[str] = AirweaveField(
        None, description="ID of the project this issue belongs to, if any", embeddable=False
    )
    project_name: Optional[str] = AirweaveField(
        None, description="Name of the project this issue belongs to, if any", embeddable=True
    )
    assignee: Optional[str] = AirweaveField(
        None, description="Name of the user assigned to this issue, if any", embeddable=True
    )
    web_url_value: Optional[str] = AirweaveField(
        None, description="URL to view the issue in Linear.", embeddable=False, unhashable=True
    )

    @classmethod
    def from_api(cls, data: Dict[str, Any]) -> LinearIssueEntity:
        """Construct from a Linear GraphQL ``issues`` node."""
        issue_id = data["id"]
        identifier = data.get("identifier", "")
        title = data.get("title", "") or identifier
        created = _parse_dt(data.get("createdAt")) or datetime.utcnow()
        updated = _parse_dt(data.get("updatedAt")) or created

        team = data.get("team") or {}
        team_id = team.get("id")
        team_name = team.get("name")

        project = data.get("project") or {}
        project_id = project.get("id")
        project_name = project.get("name")

        breadcrumbs: List[Breadcrumb] = []
        if team_id:
            breadcrumbs.append(
                Breadcrumb(
                    entity_id=team_id, name=team_name or "Team", entity_type="LinearTeamEntity"
                )
            )
        if project_id:
            breadcrumbs.append(
                Breadcrumb(
                    entity_id=project_id,
                    name=project_name or "Project",
                    entity_type="LinearProjectEntity",
                )
            )

        assignee_obj = data.get("assignee") or {}

        return cls(
            entity_id=issue_id,
            breadcrumbs=breadcrumbs,
            name=title,
            created_at=created,
            updated_at=updated,
            issue_id=issue_id,
            identifier=identifier,
            title=title,
            created_time=created,
            updated_time=updated,
            description=data.get("description"),
            priority=data.get("priority"),
            state=(data.get("state") or {}).get("name"),
            completed_at=_parse_dt(data.get("completedAt")),
            due_date=data.get("dueDate"),
            team_id=team_id,
            team_name=team_name,
            project_id=project_id,
            project_name=project_name,
            assignee=assignee_obj.get("name"),
            web_url_value=f"https://linear.app/issue/{identifier}",
        )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Browser URL for the issue."""
        return self.web_url_value or ""


class LinearCommentEntity(BaseEntity):
    """Schema for Linear comment entities."""

    comment_id: str = AirweaveField(..., description="Unique ID of the comment.", is_entity_id=True)
    body_preview: str = AirweaveField(
        ..., description="Preview of the comment body for display.", embeddable=True, is_name=True
    )
    created_time: datetime = AirweaveField(
        ..., description="When the comment was created.", is_created_at=True
    )
    updated_time: datetime = AirweaveField(
        ..., description="When the comment was last updated.", is_updated_at=True
    )
    issue_id: str = AirweaveField(
        ..., description="ID of the issue this comment belongs to", embeddable=False
    )
    issue_identifier: str = AirweaveField(
        ..., description="Identifier of the issue (e.g., 'ENG-123')", embeddable=True
    )
    body: str = AirweaveField(..., description="The content/body of the comment", embeddable=True)
    user_id: Optional[str] = AirweaveField(
        None, description="ID of the user who created the comment", embeddable=False
    )
    user_name: Optional[str] = AirweaveField(
        None, description="Name of the user who created the comment", embeddable=True
    )
    team_id: Optional[str] = AirweaveField(
        None, description="ID of the team this comment belongs to", embeddable=False
    )
    team_name: Optional[str] = AirweaveField(
        None, description="Name of the team this comment belongs to", embeddable=True
    )
    project_id: Optional[str] = AirweaveField(
        None, description="ID of the project this comment belongs to, if any", embeddable=False
    )
    project_name: Optional[str] = AirweaveField(
        None, description="Name of the project this comment belongs to, if any", embeddable=True
    )
    web_url_value: Optional[str] = AirweaveField(
        None, description="URL to view the comment in Linear", embeddable=False, unhashable=True
    )

    @classmethod
    def from_api(
        cls,
        data: Dict[str, Any],
        *,
        issue_id: str,
        issue_identifier: str,
        breadcrumbs: List[Breadcrumb],
        team_id: Optional[str] = None,
        team_name: Optional[str] = None,
        project_id: Optional[str] = None,
        project_name: Optional[str] = None,
    ) -> LinearCommentEntity:
        """Construct from a Linear GraphQL comment node with parent issue context."""
        comment_id = data["id"]
        body = data.get("body", "")
        preview = body[:50] + "..." if len(body) > 50 else body
        user = data.get("user") or {}
        created = _parse_dt(data.get("createdAt")) or datetime.utcnow()
        updated = _parse_dt(data.get("updatedAt")) or created

        return cls(
            entity_id=comment_id,
            breadcrumbs=list(breadcrumbs),
            name=preview,
            created_at=created,
            updated_at=updated,
            comment_id=comment_id,
            body_preview=preview,
            created_time=created,
            updated_time=updated,
            issue_id=issue_id,
            issue_identifier=issue_identifier,
            body=body,
            user_id=user.get("id"),
            user_name=user.get("name"),
            team_id=team_id,
            team_name=team_name,
            project_id=project_id,
            project_name=project_name,
            web_url_value=f"https://linear.app/issue/{issue_identifier}#comment-{comment_id}",
        )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Browser URL for the comment."""
        return self.web_url_value or ""


class LinearAttachmentEntity(FileEntity):
    """Schema for Linear attachment entities extracted from issue descriptions."""

    attachment_id: str = AirweaveField(
        ..., description="Unique identifier for the attachment.", is_entity_id=True
    )
    issue_id: str = AirweaveField(
        ..., description="ID of the issue this attachment belongs to", embeddable=False
    )
    issue_identifier: str = AirweaveField(
        ..., description="Identifier of the issue (e.g., 'ENG-123')", embeddable=True
    )
    title: str = AirweaveField(
        ..., description="Title of the attachment", embeddable=True, is_name=True
    )
    subtitle: Optional[str] = AirweaveField(
        None, description="Subtitle of the attachment", embeddable=True
    )
    source: Optional[Dict[str, Any]] = AirweaveField(
        None, description="Source information about the attachment", embeddable=False
    )
    web_url_value: Optional[str] = AirweaveField(
        None, description="Viewer URL for the attachment.", embeddable=False, unhashable=True
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Browser URL for the attachment (falls back to download URL)."""
        return self.web_url_value or self.url
