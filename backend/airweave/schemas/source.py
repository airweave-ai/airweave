"""Source schema.

Sources represent the available data connector types that Airweave can use to sync data
from external systems. Each source defines the authentication and configuration requirements
for connecting to a specific type of data source.
"""

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from airweave.platform.configs._base import Fields


class Source(BaseModel):
    """Complete source representation with authentication and configuration schemas.

    Served from the in-memory SourceRegistry — no database row needed.
    """

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
            "extraction."
        ),
    )
    federated_search: bool = Field(
        False,
        description=("Whether this source uses federated search instead of traditional syncing."),
    )
    supports_temporal_relevance: bool = Field(
        True,
        description=(
            "Whether this source's entities have timestamps that enable recency-based ranking."
        ),
    )
    supports_access_control: bool = Field(
        False,
        description=("Whether this source supports document-level access control."),
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
    supports_browse_tree: bool = Field(
        False,
        description=(
            "Whether this source supports lazy-loaded browse tree for selective node syncing."
        ),
    )
    auth_fields: Optional[Fields] = Field(
        None,
        description=(
            "Schema definition for authentication fields required to connect to this source."
        ),
    )
    config_fields: Fields = Field(
        ...,
        description=(
            "Schema definition for configuration fields required to customize this source."
        ),
    )
    supported_auth_providers: Optional[List[str]] = Field(
        default=None,
        description=("List of auth provider short names that support this source."),
    )

    model_config = ConfigDict(from_attributes=True)
