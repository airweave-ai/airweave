"""Source schema.

Sources represent the available data connector types that Airweave can use to sync data
from external systems. Each source defines the authentication and configuration requirements
for connecting to a specific type of data source.
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from airweave.platform.configs._base import Fields


class SourceBase(BaseModel):
    """Base schema for Source with common fields."""

    name: str = Field(
        ...,
        description=(
            "Human-readable name of the data source connector (e.g., 'GitHub', 'Stripe', "
            "'PostgreSQL')."
        ),
    )
    description: Optional[str] = Field(
        None,
        description=(
            "Detailed description explaining what data this source can extract and its "
            "typical use cases."
        ),
    )
    auth_methods: Optional[List[str]] = Field(
        None,
        description="List of supported authentication methods (e.g., 'direct', 'oauth_browser').",
    )
    oauth_type: Optional[str] = Field(
        None,
        description="OAuth token type for OAuth sources (e.g., 'access_only', 'with_refresh').",
    )
    requires_byoc: bool = Field(
        False,
        description="Whether this OAuth source requires users to bring their own client.",
    )
    auth_config_class: Optional[str] = Field(
        None,
        description=(
            "Python class name that defines the authentication configuration fields "
            "required for this source (only for DIRECT auth)."
        ),
    )
    config_class: Optional[str] = Field(
        None,
        description=(
            "Python class name that defines the source-specific configuration options "
            "and parameters."
        ),
    )
    short_name: str = Field(
        ...,
        description=(
            "Technical identifier used internally to reference this source type. Must be unique "
            "across all sources."
        ),
    )
    class_name: str = Field(
        ...,
        description=(
            "Python class name of the source implementation that handles data extraction logic."
        ),
    )
    output_entity_definitions: List[str] = Field(
        default_factory=list,
        description=(
            "List of entity definition short names that this source can produce "
            "(e.g., ['asana_task_entity', 'asana_project_entity'])."
        ),
    )
    labels: Optional[List[str]] = Field(
        None,
        description=(
            "Categorization tags to help users discover and filter sources by domain or use case."
        ),
    )
    supports_continuous: bool = Field(
        False,
        description=(
            "Whether this source supports cursor-based continuous syncing for incremental data "
            "extraction. Sources with this capability can track their sync position and resume "
            "from where they left off."
        ),
    )
    federated_search: bool = Field(
        False,
        description=(
            "Whether this source uses federated search instead of traditional syncing. "
            "Federated search sources query data in real-time during searches rather than "
            "syncing and indexing all data beforehand."
        ),
    )
    supports_temporal_relevance: bool = Field(
        True,
        description=(
            "Whether this source's entities have timestamps that enable recency-based ranking. "
            "Sources without file-level timestamps (e.g., code repositories) cannot use temporal "
            "relevance for search result weighting."
        ),
    )
    supports_access_control: bool = Field(
        False,
        description=(
            "Whether this source supports document-level access control. "
            "Sources with this capability extract ACL information from the source "
            "and apply it during search to filter results based on user permissions."
        ),
    )
    rate_limit_level: Optional[str] = Field(
        None,
        description=(
            "Rate limiting level for this source: 'org' (organization-wide), "
            "'connection' (per-connection/per-user), or None (no rate limiting)."
        ),
    )
    feature_flag: Optional[str] = Field(
        None,
        description=(
            "Feature flag required to access this source. "
            "If set, only organizations with this feature enabled can see/use this source."
        ),
    )

    model_config = ConfigDict(from_attributes=True)


class SourceCreate(SourceBase):
    """Schema for creating a Source object."""

    pass


class SourceUpdate(SourceBase):
    """Schema for updating a Source object."""

    pass


class SourceInDBBase(SourceBase):
    """Base schema for Source stored in database with system fields."""

    output_entity_definition_ids: Optional[List[str]] = Field(
        None,
        description="Legacy DB column — maps to output_entity_definitions.",
    )
    id: UUID = Field(
        ...,
        description=(
            "Unique system identifier for this source type. Generated automatically when the "
            "source is registered."
        ),
    )
    created_at: datetime = Field(
        ...,
        description=(
            "Timestamp when this source type was registered in the system (ISO 8601 format)."
        ),
    )
    modified_at: datetime = Field(
        ...,
        description="Timestamp when this source type was last updated (ISO 8601 format).",
    )

    model_config = ConfigDict(from_attributes=True)


class Source(SourceBase):
    """Complete source representation with authentication and configuration schemas.

    Served from the in-memory SourceRegistry — no database row needed.
    """

    auth_fields: Optional[Fields] = Field(
        None,
        description=(
            "Schema definition for authentication fields required to connect to this source. "
            "Only present for sources using DIRECT authentication. OAuth sources handle "
            "authentication through browser flows."
        ),
    )
    config_fields: Fields = Field(
        ...,
        description=(
            "Schema definition for configuration fields required to customize this source. "
            "Describes field types, validation rules, and user interface hints."
        ),
    )
    supported_auth_providers: Optional[List[str]] = Field(
        default=None,
        description=(
            "List of auth provider short names that support this source "
            "(e.g., ['composio', 'pipedream']). Computed dynamically for API responses. "
            "This field is not stored in the database."
        ),
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "id": "550e8400-e29b-41d4-a716-446655440000",
                    "name": "GitHub",
                    "description": (
                        "Connect to GitHub repositories for code, issues, pull requests, "
                        "and documentation"
                    ),
                    "auth_methods": ["direct"],
                    "oauth_type": None,
                    "auth_config_class": "GitHubAuthConfig",
                    "config_class": "GitHubConfig",
                    "short_name": "github",
                    "class_name": "GitHubSource",
                    "output_entity_definitions": [
                        "git_hub_repository_entity",
                        "git_hub_code_file_entity",
                    ],
                    "organization_id": None,
                    "labels": ["code"],
                    "created_at": "2024-01-01T00:00:00Z",
                    "modified_at": "2024-01-01T00:00:00Z",
                    "supported_auth_providers": [],
                    "auth_fields": {
                        "fields": [
                            {
                                "name": "personal_access_token",
                                "title": "Personal Access Token",
                                "description": (
                                    "Personal Access Token with repository read permissions. "
                                    "Generate one at https://github.com/settings/tokens"
                                ),
                                "type": "string",
                                "secret": True,
                            },
                        ]
                    },
                    "config_fields": {
                        "fields": [
                            {
                                "name": "repo_name",
                                "title": "Repository Name",
                                "description": (
                                    "Full repository name in format 'owner/repo' "
                                    "(e.g., 'airweave-ai/airweave')"
                                ),
                                "type": "string",
                            },
                            {
                                "name": "branch",
                                "title": "Branch name",
                                "description": (
                                    "Specific branch to sync (e.g., 'main', 'development'). "
                                    "If empty, uses the default branch."
                                ),
                                "type": "string",
                            },
                        ]
                    },
                },
                {
                    "id": "660e8400-e29b-41d4-a716-446655440001",
                    "name": "Gmail",
                    "description": "Connect to Gmail for email threads, messages, and attachments",
                    "auth_methods": ["oauth_browser", "oauth_token", "oauth_byoc"],
                    "oauth_type": "with_refresh",
                    "auth_config_class": None,
                    "config_class": "GmailConfig",
                    "short_name": "gmail",
                    "class_name": "GmailSource",
                    "output_entity_definitions": [
                        "gmail_thread_entity",
                        "gmail_message_entity",
                    ],
                    "organization_id": None,
                    "labels": ["Communication", "Email"],
                    "created_at": "2024-01-01T00:00:00Z",
                    "modified_at": "2024-01-01T00:00:00Z",
                    "supported_auth_providers": ["pipedream", "composio"],
                    "auth_fields": None,  # OAuth sources don't have auth_fields
                    "config_fields": {
                        "fields": [
                            {
                                "name": "sync_attachments",
                                "title": "Sync Attachments",
                                "description": "Whether to sync email attachments",
                                "type": "boolean",
                                "default": True,
                            },
                        ]
                    },
                },
            ]
        }
    }
