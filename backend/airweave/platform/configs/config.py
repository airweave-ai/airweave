"""Configuration classes for platform components."""

from typing import Optional

from pydantic import Field, field_validator

from airweave.platform.configs._base import BaseConfig, RequiredTemplateConfig


class SourceConfig(BaseConfig):
    """Source config schema."""

    pass


class AirtableConfig(SourceConfig):
    """Airtable configuration schema."""

    pass


class AsanaConfig(SourceConfig):
    """Asana configuration schema."""

    pass


class ApolloConfig(SourceConfig):
    """Apollo configuration schema."""

    pass


class AttioConfig(SourceConfig):
    """Attio configuration schema."""

    pass


class BitbucketConfig(SourceConfig):
    """Bitbucket configuration schema."""

    branch: str = Field(
        default="",
        title="Branch name",
        description=(
            "Specific branch to sync (e.g., 'main', 'develop'). If empty, uses the default branch."
        ),
    )
    file_extensions: list[str] = Field(
        default=[],
        title="File Extensions",
        description=(
            "List of file extensions to include (e.g., '.py', '.js', '.md'). "
            "If empty, includes all text files."
        ),
    )

    @field_validator("file_extensions", mode="before")
    @classmethod
    def parse_file_extensions(cls, value):
        """Convert string input to list if needed."""
        if isinstance(value, str):
            if not value.strip():
                return []
            # Split by commas and strip whitespace
            return [ext.strip() for ext in value.split(",") if ext.strip()]
        return value


class BoxConfig(SourceConfig):
    """Box configuration schema."""

    folder_id: str = Field(
        default="0",
        title="Folder ID",
        description=(
            "Specific Box folder ID to sync. Default is '0' (root folder, syncs all files). "
            "To sync a specific folder, enter its folder ID. "
            "You can find folder IDs in the Box URL when viewing a folder."
        ),
    )


class ClickUpConfig(SourceConfig):
    """ClickUp configuration schema."""

    pass


class CodaConfig(SourceConfig):
    """Coda configuration schema."""

    doc_id: Optional[str] = Field(
        default=None,
        title="Doc ID",
        description="Sync only this doc (leave empty to sync all docs the token can access).",
    )
    folder_id: Optional[str] = Field(
        default=None,
        title="Folder ID",
        description="Limit docs to this folder (optional).",
    )


class ConfluenceConfig(SourceConfig):
    """Confluence configuration schema."""

    pass


class DropboxConfig(SourceConfig):
    """Dropbox configuration schema."""


class FirefliesConfig(SourceConfig):
    """Fireflies configuration schema.

    Syncs meeting transcripts (mine: true) from the Fireflies GraphQL API.
    No additional config required for basic sync.
    """


class Document360Config(SourceConfig):
    """Document360 configuration schema."""

    base_url: Optional[str] = Field(
        default=None,
        title="API Base URL",
        description=(
            "Document360 API base URL (e.g. https://apihub.document360.io or "
            "https://apihub.us.document360.io for US). Leave empty to use default."
        ),
    )
    lang_code: str = Field(
        default="en",
        title="Language Code",
        description="Language code for article content (e.g. 'en', 'es'). Default: en.",
    )


class ElasticsearchConfig(SourceConfig):
    """Elasticsearch configuration schema."""

    pass


class GitHubConfig(SourceConfig):
    """Github configuration schema."""

    repo_name: str = Field(
        title="Repository Name",
        description="Repository to sync in owner/repo format (e.g., 'airweave-ai/airweave')",
        min_length=3,
        pattern=r"^[a-zA-Z0-9_-]+/[a-zA-Z0-9_.-]+$",
    )
    branch: str = Field(
        default="",
        title="Branch name",
        description=(
            "Specific branch to sync (e.g., 'main', 'development'). "
            "If empty, uses the default branch."
        ),
    )

    @field_validator("repo_name")
    @classmethod
    def validate_repo_name(cls, v: str) -> str:
        """Validate repository name is in owner/repo format."""
        if not v or not v.strip():
            raise ValueError("Repository name is required")
        v = v.strip()
        if "/" not in v:
            raise ValueError(
                "Repository must be in 'owner/repo' format (e.g., 'airweave-ai/airweave')"
            )
        parts = v.split("/")
        if len(parts) != 2:
            raise ValueError(
                "Repository must be in 'owner/repo' format (e.g., 'airweave-ai/airweave')"
            )
        owner, repo = parts
        if not owner or not repo:
            raise ValueError("Both owner and repository name must be non-empty")
        return v


class GitLabConfig(SourceConfig):
    """GitLab configuration schema."""

    project_id: str = Field(
        default="",
        title="Project ID",
        description=(
            "Specific project ID to sync (e.g., '12345'). If empty, syncs all accessible projects."
        ),
    )
    branch: str = Field(
        default="",
        title="Branch name",
        description=(
            "Specific branch to sync (e.g., 'main', 'master'). If empty, uses the default branch."
        ),
    )


class GmailConfig(SourceConfig):
    """Gmail configuration schema."""

    after_date: Optional[str] = Field(
        None,
        title="After Date",
        description="Sync emails after this date (format: YYYY/MM/DD or YYYY-MM-DD).",
    )

    included_labels: list[str] = Field(
        default=["inbox", "sent"],
        title="Included Labels",
        description=(
            "Labels to include (e.g., 'inbox', 'sent', 'important'). Defaults to inbox and sent."
        ),
    )

    excluded_labels: list[str] = Field(
        default=[
            "spam",
            "trash",
        ],
        title="Excluded Labels",
        description=(
            "Labels to exclude (e.g., 'spam', 'trash', 'promotions', 'social'). "
            "Defaults to spam and trash."
        ),
    )

    excluded_categories: list[str] = Field(
        default=["promotions", "social"],
        title="Excluded Categories",
        description=(
            "Gmail categories to exclude (e.g., 'promotions', 'social', 'updates', 'forums')."
        ),
    )

    gmail_query: Optional[str] = Field(
        None,
        title="Custom Gmail Query",
        description=(
            "Advanced. Custom Gmail query string (overrides all other filters if provided)."
        ),
    )

    @field_validator("included_labels", "excluded_labels", "excluded_categories", mode="before")
    @classmethod
    def parse_list_fields(cls, value):
        """Convert comma-separated string to list if needed."""
        if isinstance(value, str):
            if not value.strip():
                return []
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator("after_date")
    @classmethod
    def validate_date_format(cls, value):
        """Validate date format and convert to YYYY/MM/DD."""
        if not value:
            return value
        # Accept both YYYY/MM/DD and YYYY-MM-DD formats
        return value.replace("-", "/")


class GoogleCalendarConfig(SourceConfig):
    """Google Calendar configuration schema."""

    pass


class GoogleDocsConfig(SourceConfig):
    """Google Docs configuration schema."""

    include_trashed: bool = Field(
        default=False,
        title="Include Trashed Documents",
        description="Include documents that have been moved to trash. Defaults to False.",
    )

    include_shared: bool = Field(
        default=True,
        title="Include Shared Documents",
        description="Include documents shared with you by others. Defaults to True.",
    )


class GoogleDriveConfig(SourceConfig):
    """Google Drive configuration schema."""

    include_patterns: list[str] = Field(
        default=[],
        title="Include Patterns",
        description=(
            "List of file/folder paths to include in synchronization. "
            "Examples: 'my_folder/*', 'my_folder/my_file.pdf'. "
            "Separate multiple patterns with commas. If empty, all files are included."
        ),
    )

    @field_validator("include_patterns", mode="before")
    @classmethod
    def _parse_include_patterns(cls, value):
        if isinstance(value, str):
            return [p.strip() for p in value.split(",") if p.strip()]
        return value


class GoogleSlidesConfig(SourceConfig):
    """Google Slides configuration schema."""

    include_trashed: bool = Field(
        default=False,
        title="Include Trashed Presentations",
        description="Include presentations that have been moved to trash. Defaults to False.",
    )

    include_shared: bool = Field(
        default=True,
        title="Include Shared Presentations",
        description="Include presentations shared with you by others. Defaults to True.",
    )


class HubspotConfig(SourceConfig):
    """Hubspot configuration schema."""

    pass


class SliteConfig(SourceConfig):
    """Slite configuration schema."""

    include_archived: bool = Field(
        default=False,
        title="Include archived notes",
        description="If enabled, archived notes will be synced. Default: only active notes.",
    )


class IntercomConfig(SourceConfig):
    """Intercom configuration schema."""

    pass


class JiraConfig(SourceConfig):
    """Jira configuration schema."""

    project_keys: list[str] = Field(
        ...,
        title="Project Keys",
        description=(
            "List of Jira project keys to sync (e.g., 'PROJ', 'DEV', 'MARKET'). "
            "Only the specified projects will be synced. Hit enter to add new project. "
            " You can find project keys in your Jira project settings."
        ),
        min_length=1,
    )

    # Zephyr Scale integration (requires ZEPHYR_SCALE feature flag)
    # This field is dynamically shown/hidden based on organization feature flags
    zephyr_scale_api_token: Optional[str] = Field(
        default=None,
        title="Zephyr Scale API Token",
        description=(
            "API token for Zephyr Scale test management integration. "
            "Leave empty if not using Zephyr Scale."
        ),
        json_schema_extra={"feature_flag": "zephyr_scale", "is_secret": True},
    )


class LinearConfig(SourceConfig):
    """Linear configuration schema."""

    pass


class MondayConfig(SourceConfig):
    """Monday configuration schema."""

    pass


class MySQLConfig(SourceConfig):
    """MySQL configuration schema."""

    pass


class NotionConfig(SourceConfig):
    """Notion configuration schema."""

    pass


class OneDriveConfig(SourceConfig):
    """OneDrive configuration schema."""

    pass


class OracleConfig(SourceConfig):
    """Oracle configuration schema."""

    pass


class OutlookCalendarConfig(SourceConfig):
    """Outlook Calendar configuration schema."""

    pass


class OutlookMailConfig(SourceConfig):
    """Outlook Mail configuration schema."""

    after_date: Optional[str] = Field(
        None,
        title="After Date",
        description="Sync emails after this date (format: YYYY/MM/DD or YYYY-MM-DD).",
    )

    included_folders: list[str] = Field(
        default=["inbox", "sentitems"],
        title="Included Folders",
        description=(
            "Well-known folder names to include (e.g., 'inbox', 'sentitems', 'drafts'). "
            "Defaults to inbox and sent items."
        ),
    )

    excluded_folders: list[str] = Field(
        default=["junkemail", "deleteditems"],
        title="Excluded Folders",
        description=(
            "Well-known folder names to exclude (e.g., 'junkemail', 'deleteditems'). "
            "Defaults to junk email and deleted items."
        ),
    )

    @field_validator("included_folders", "excluded_folders", mode="before")
    @classmethod
    def parse_list_fields(cls, value):
        """Convert comma-separated string to list if needed."""
        if isinstance(value, str):
            if not value.strip():
                return []
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator("after_date")
    @classmethod
    def validate_date_format(cls, value):
        """Validate date format and convert to YYYY/MM/DD."""
        if not value:
            return value
        # Accept both YYYY/MM/DD and YYYY-MM-DD formats
        return value.replace("-", "/")


class OneNoteConfig(SourceConfig):
    """Microsoft OneNote configuration schema."""

    pass


class WordConfig(SourceConfig):
    """Microsoft Word configuration schema."""

    pass


class CTTIConfig(SourceConfig):
    """CTTI AACT configuration schema."""

    limit: int = Field(
        default=10000,
        title="Study Limit",
        description="Maximum number of clinical trial studies to fetch from AACT database",
    )

    skip: int = Field(
        default=0,
        title="Skip Studies",
        description=(
            "Number of clinical trial studies to skip (for pagination). "
            "Use with limit to fetch different batches."
        ),
    )

    @field_validator("limit", mode="before")
    @classmethod
    def parse_limit(cls, value):
        """Convert string input to integer if needed."""
        if isinstance(value, str):
            if not value.strip():
                return 10000
            try:
                return int(value.strip())
            except ValueError as e:
                raise ValueError("Limit must be a valid integer") from e
        return value

    @field_validator("skip", mode="before")
    @classmethod
    def parse_skip(cls, value):
        """Convert string input to integer if needed."""
        if isinstance(value, str):
            if not value.strip():
                return 0
            try:
                skip_val = int(value.strip())
                if skip_val < 0:
                    raise ValueError("Skip must be non-negative")
                return skip_val
            except ValueError as e:
                if "non-negative" in str(e):
                    raise e
                raise ValueError("Skip must be a valid integer") from e
        if isinstance(value, (int, float)):
            if value < 0:
                raise ValueError("Skip must be non-negative")
            return int(value)
        return value


class SharePointConfig(SourceConfig):
    """SharePoint configuration schema."""

    pass


class SharePoint2019V2Config(SourceConfig):
    """SharePoint 2019 On-Premise configuration schema.

    Requires both SharePoint site URL and Active Directory server configuration.
    AD is needed to resolve SIDs to sAMAccountNames for access control.
    """

    site_url: str = RequiredTemplateConfig(
        title="SharePoint Site URL",
        description=(
            "Full URL of the SharePoint site to sync "
            "(e.g., 'https://sharepoint.contoso.com/sites/Marketing')"
        ),
        json_schema_extra={"required_for_auth": True},
    )

    # Active Directory config (required for SID resolution)
    ad_server: str = Field(
        title="Active Directory Server",
        description=(
            "LDAP server hostname or IP address for Active Directory queries "
            "(e.g., 'dc.contoso.local' or 'ldaps://dc.contoso.local:636')"
        ),
    )

    ad_search_base: str = Field(
        title="AD Search Base DN",
        description=(
            "LDAP search base Distinguished Name for Active Directory queries "
            "(e.g., 'DC=contoso,DC=local')"
        ),
    )


class ShopifyConfig(SourceConfig):
    """Shopify configuration schema."""

    shop_domain: str = Field(
        title="Shop Domain",
        description="Your Shopify store domain (e.g., 'my-store.myshopify.com')",
        min_length=3,
    )


class SlackConfig(SourceConfig):
    """Slack configuration schema."""

    pass


class SQLServerConfig(SourceConfig):
    """SQL Server configuration schema."""

    pass


class SQliteConfig(SourceConfig):
    """SQlite configuration schema."""

    pass


class StripeConfig(SourceConfig):
    """Stripe configuration schema."""

    pass


class SalesforceConfig(SourceConfig):
    """Salesforce configuration schema.

    Note: instance_url is automatically extracted from the OAuth response
    or from the auth provider's credential blob, so users don't need to
    provide it manually.
    """

    instance_url: Optional[str] = Field(
        default=None,
        title="Salesforce Instance URL",
        description="Your Salesforce instance domain (auto-populated from OAuth response)",
        json_schema_extra={
            "exclude_from_ui": True,
            "auth_provider_field": "instance_url",
        },
    )

    @field_validator("instance_url", mode="before")
    @classmethod
    def strip_https_prefix(cls, value):
        """Remove https:// or http:// prefix if present."""
        if isinstance(value, str):
            if value.startswith("https://"):
                return value.replace("https://", "", 1)
            elif value.startswith("http://"):
                return value.replace("http://", "", 1)
        return value


class TodoistConfig(SourceConfig):
    """Todoist configuration schema."""

    pass


class TimedConfig(SourceConfig):
    """Timed source configuration schema for testing sync lifecycle.

    Controls the generation of N entities spread evenly over a configurable
    duration. Designed for precise timing control in cancellation and
    state transition tests.
    """

    entity_count: int = Field(
        default=100,
        title="Entity Count",
        description="Total number of entities to generate",
        ge=1,
        le=10000,
    )
    duration_seconds: float = Field(
        default=10.0,
        title="Duration (seconds)",
        description="Total time to spread entity generation over, in seconds",
        ge=0.1,
        le=600,
    )
    seed: int = Field(
        default=42,
        title="Random Seed",
        description="Random seed for reproducible content generation",
    )


class StubConfig(SourceConfig):
    """Stub source configuration schema for testing.

    Configures the generation of deterministic test entities with various
    content sizes and types. Uses weighted distribution for entity type selection.
    """

    entity_count: int = Field(
        default=10,
        title="Entity Count",
        description="Total number of entities to generate",
        ge=1,
        le=100000,
    )
    seed: int = Field(
        default=42,
        title="Random Seed",
        description="Random seed for reproducible content generation",
    )
    generation_delay_ms: int = Field(
        default=0,
        title="Generation Delay (ms)",
        description="Delay between entity generations in milliseconds (0 for no delay)",
        ge=0,
        le=10000,
    )

    # Distribution weights (will be normalized to sum to 100)
    small_entity_weight: int = Field(
        default=30,
        title="Small Entity Weight",
        description="Weight for small entities (~100-200 chars, like comments)",
        ge=0,
        le=100,
    )
    medium_entity_weight: int = Field(
        default=30,
        title="Medium Entity Weight",
        description="Weight for medium entities (~500-1000 chars, like tasks)",
        ge=0,
        le=100,
    )
    large_entity_weight: int = Field(
        default=10,
        title="Large Entity Weight",
        description="Weight for large entities (~3000-5000 chars, like articles)",
        ge=0,
        le=100,
    )
    small_file_weight: int = Field(
        default=15,
        title="Small File Weight",
        description="Weight for small file entities (~1-5 KB)",
        ge=0,
        le=100,
    )
    large_file_weight: int = Field(
        default=5,
        title="Large File Weight",
        description="Weight for large file entities (~50-100 KB)",
        ge=0,
        le=100,
    )
    code_file_weight: int = Field(
        default=10,
        title="Code File Weight",
        description="Weight for code file entities (~2-10 KB)",
        ge=0,
        le=100,
    )
    inject_special_tokens: bool = Field(
        default=False,
        title="Inject Special Tokens",
        description=(
            "If true, injects special tokenizer tokens (like <|endoftext|>) into generated "
            "content. Used for testing chunker/embedder handling of edge cases."
        ),
    )

    custom_content_prefix: Optional[str] = Field(
        default=None,
        title="Custom Content Prefix",
        description=(
            "Optional string to prepend to all generated content. Useful for testing "
            "specific strings like special tokens or edge case characters."
        ),
    )

    fail_after: int = Field(
        default=-1,
        title="Fail After",
        description="Number of entities to generate before failing the sync",
        ge=0,
        le=100000,
    )

    @field_validator(
        "small_entity_weight",
        "medium_entity_weight",
        "large_entity_weight",
        "small_file_weight",
        "large_file_weight",
        "code_file_weight",
        mode="before",
    )
    @classmethod
    def parse_weight(cls, value):
        """Convert string input to integer if needed."""
        if isinstance(value, str):
            if not value.strip():
                return 0
            try:
                return int(value.strip())
            except ValueError as e:
                raise ValueError("Weight must be a valid integer") from e
        return value


class FileStubConfig(SourceConfig):
    """File stub source configuration for testing file converters.

    Generates one of each file type: born-digital PDF, scanned PDF, PPTX, DOCX.
    """

    seed: int = Field(
        default=42,
        title="Random Seed",
        description="Random seed for reproducible content generation",
    )
    custom_content_prefix: Optional[str] = Field(
        default=None,
        title="Custom Content Prefix",
        description=(
            "Optional string to embed in all generated files. "
            "Useful as a tracking token for search assertions."
        ),
    )


class TrelloConfig(SourceConfig):
    """Trello configuration schema."""

    pass


class TeamsConfig(SourceConfig):
    """Microsoft Teams configuration schema."""

    pass


class ZendeskConfig(SourceConfig):
    """Zendesk configuration schema."""

    subdomain: str = RequiredTemplateConfig(
        title="Zendesk Subdomain",
        description="Your Zendesk subdomain only (e.g., 'mycompany' NOT 'mycompany.zendesk.com')",
        json_schema_extra={"required_for_auth": True},
    )
    exclude_closed_tickets: Optional[bool] = Field(
        default=False,
        title="Exclude Closed Tickets",
        description="Skip closed tickets during sync (recommended for faster syncing)",
    )


class FreshdeskConfig(SourceConfig):
    """Freshdesk configuration schema."""

    domain: str = RequiredTemplateConfig(
        title="Freshdesk Domain",
        description=("Your Freshdesk domain only (e.g., 'mycompany' for mycompany.freshdesk.com)"),
        json_schema_extra={"required_for_auth": True},
    )


class ServiceNowConfig(SourceConfig):
    """ServiceNow configuration schema."""

    pass


# AUTH PROVIDER CONFIGURATION CLASSES
# These are for configuring auth provider behavior


class AuthProviderConfig(BaseConfig):
    """Base auth provider configuration schema."""

    pass


class ComposioConfig(AuthProviderConfig):
    """Composio Auth Provider configuration schema."""

    auth_config_id: str = Field(
        title="Auth Config ID",
        description="Auth Config ID for the Composio connection",
    )
    account_id: str = Field(
        title="Account ID",
        description="Account ID for the Composio connection",
    )


class PipedreamConfig(AuthProviderConfig):
    """Pipedream Auth Provider configuration schema."""

    project_id: str = Field(
        title="Project ID",
        description="Pipedream project ID (e.g., proj_JPsD74a)",
    )
    account_id: str = Field(
        title="Account ID",
        description="Pipedream account ID (e.g., apn_gyha5Ky)",
    )
    external_user_id: str = Field(
        title="External User ID",
        description="External user ID associated with the account",
    )
    environment: str = Field(
        default="production",
        title="Environment",
        description="Pipedream environment (production or development)",
    )


class SnapshotConfig(BaseConfig):
    """Configuration for SnapshotSource.

    Specifies the path to raw data captured during a previous sync.
    Supports both local filesystem paths and Azure blob URLs.
    """

    path: str = Field(
        title="Raw Data Path",
        description=(
            "Path to the raw data directory containing manifest.json, entities/, and files/. "
            "Can be a local filesystem path (e.g., '/path/to/raw/sync-id') or "
            "Azure blob URL (e.g., 'https://account.blob.core.windows.net/container/raw/sync-id')"
        ),
        min_length=1,
    )

    restore_files: bool = Field(
        default=True,
        title="Restore Files",
        description="Whether to restore file attachments from the files/ directory",
    )

    @field_validator("path")
    @classmethod
    def validate_path(cls, v: str) -> str:
        """Validate and normalize path."""
        if not v or not v.strip():
            raise ValueError("Path is required")
        return v.strip().rstrip("/")
