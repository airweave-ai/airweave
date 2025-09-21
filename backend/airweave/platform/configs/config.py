"""Configuration classes for platform components."""

from typing import Any, Optional

from pydantic import Field, field_validator, validator

from airweave.platform.configs._base import BaseConfig


class SourceConfig(BaseConfig):
    """Source config schema."""

    pass


class AsanaConfig(SourceConfig):
    """Asana configuration schema."""

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
            "If empty, includes all text files. Use '.*' to include all files."
        ),
    )

    @validator("file_extensions", pre=True)
    def parse_file_extensions(cls, value):
        """Convert string input to list if needed."""
        if isinstance(value, str):
            if not value.strip():
                return []
            # Split by commas and strip whitespace
            return [ext.strip() for ext in value.split(",") if ext.strip()]
        return value


class ClickUpConfig(SourceConfig):
    """ClickUp configuration schema."""

    pass


class ConfluenceConfig(SourceConfig):
    """Confluence configuration schema."""

    pass


class DropboxConfig(SourceConfig):
    """Dropbox configuration schema."""

    pass


class ElasticsearchConfig(SourceConfig):
    """Elasticsearch configuration schema."""

    pass


class GitHubConfig(SourceConfig):
    """Github configuration schema."""

    branch: str = Field(
        default="",
        title="Branch name",
        description=(
            "Specific branch to sync (e.g., 'main', 'development'). "
            "If empty, uses the default branch."
        ),
    )


class GmailConfig(SourceConfig):
    """Gmail configuration schema."""

    pass


class GoogleCalendarConfig(SourceConfig):
    """Google Calendar configuration schema."""

    pass


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

    @validator("include_patterns", pre=True)
    def _parse_include_patterns(cls, value):
        if isinstance(value, str):
            return [p.strip() for p in value.split(",") if p.strip()]
        return value


class HubspotConfig(SourceConfig):
    """Hubspot configuration schema."""

    pass


class IntercomConfig(SourceConfig):
    """Intercom configuration schema."""

    pass


class JiraConfig(SourceConfig):
    """Jira configuration schema."""

    pass


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

    @validator("limit", pre=True)
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

    @validator("skip", pre=True)
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


class PostgreSQLConfig(SourceConfig):
    """Postgres configuration schema."""

    pass


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


class TodoistConfig(SourceConfig):
    """Todoist configuration schema."""

    pass


# ----------------- Trello (new) -----------------


class TrelloConfig(SourceConfig):
    """Trello source behavior flags."""

    board_ids: list[str] = Field(
        default=[],
        title="Board IDs",
        description="If empty, sync all boards visible to the user; otherwise only these boards.",
    )
    include_archived: bool = Field(
        default=False, title="Include archived", description="Include closed boards/lists/cards."
    )
    include_attachments: bool = Field(
        default=True, title="Attachments", description="Download & index card attachments."
    )
    include_comments: bool = Field(
        default=True, title="Comments", description="Index card comments (commentCard actions)."
    )
    include_checklists: bool = Field(
        default=True, title="Checklists", description="Index card checklists."
    )
    attachment_max_bytes: Optional[int] = Field(
        default=None,
        title="Attachment size cap (bytes)",
        description="Skip downloads larger than this.",
    )

    @validator("board_ids", pre=True)
    def _parse_board_ids(cls, v):
        """Accept comma-separated string or list; blanks → empty list."""
        if isinstance(v, str):
            return [x.strip() for x in v.split(",") if x.strip()]
        return v

    # ---- helpers to coerce UI strings & blanks ----
    @staticmethod
    def _parse_bool(value: Any, default: bool) -> bool:
        """Coerce '', None, and common string/int forms into booleans."""
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        if isinstance(value, str):
            s = value.strip().lower()
            if s == "":  # blank => default
                return default
            if s in {"1", "true", "t", "yes", "y", "on"}:
                return True
            if s in {"0", "false", "f", "no", "n", "off"}:
                return False
        raise ValueError("Invalid boolean")

    @field_validator("include_archived", mode="before")
    @classmethod
    def _v_include_archived(cls, v):
        return cls._parse_bool(v, default=False)

    @field_validator("include_attachments", mode="before")
    @classmethod
    def _v_include_attachments(cls, v):
        return cls._parse_bool(v, default=True)

    @field_validator("include_comments", mode="before")
    @classmethod
    def _v_include_comments(cls, v):
        return cls._parse_bool(v, default=True)

    @field_validator("include_checklists", mode="before")
    @classmethod
    def _v_include_checklists(cls, v):
        return cls._parse_bool(v, default=True)

    @field_validator("attachment_max_bytes", mode="before")
    @classmethod
    def _v_attachment_max_bytes(cls, v):
        """Accept None, '', numeric strings (with _ or ,), or ints."""
        if v is None:
            return None
        if isinstance(v, (int, float)):
            return int(v)
        if isinstance(v, str):
            s = v.strip().replace(",", "").replace("_", "")
            if s == "":
                return None
            try:
                return int(s)
            except ValueError:
                raise ValueError("Must be an integer (bytes)") from None
        return v


class DiscordConfig(SourceConfig):
    """Discord source configuration (Bot token)."""

    # Scope selection
    guild_ids: list[str] = Field(
        default=[],
        title="Guild IDs",
        description="Snowflake IDs of guilds to sync. The bot must be a member.",
    )
    channel_ids: list[str] = Field(
        default=[],
        title="Channel IDs (optional)",
        description=(
            "Restrict to these channels/threads. Empty = discover text/announcement + "
            "active threads."
        ),
    )

    # Crawl toggles
    include_threads: bool = Field(
        default=True,
        title="Include active threads",
        description="Fetch active threads for each guild and index their messages.",
    )
    include_attachments_metadata: bool = Field(
        default=True,
        title="Include attachment metadata",
        description="Index attachment metadata (filename, size, URL). Files are not downloaded.",
    )
    include_bot_authors: bool = Field(
        default=True,
        title="Include bot-authored messages",
        description="If false, messages by bots are skipped.",
    )
    message_types: list[int] = Field(
        default=[],
        title="Message types allowlist",
        description="Allowlist of Discord Message.type integers (empty = all).",
    )

    # Pagination / limits
    page_size: int = Field(
        default=100, title="Page size", description="Messages per request (1–100)."
    )
    max_messages_per_channel: Optional[int] = Field(
        default=None,
        title="Max messages per channel (full sync)",
        description="Cap when walking full history (blank = no cap).",
    )
    after_message_id: Optional[str] = Field(
        default=None,
        title="Start after message ID",
        description=(
            "On first run, only fetch messages strictly after this ID. "
            "Subsequent runs are incremental."
        ),
    )

    @validator("guild_ids", "channel_ids", "message_types", pre=True)
    def _csv_to_list(cls, v):
        if isinstance(v, str):
            items = [x.strip() for x in v.split(",") if x.strip()]
            try:
                return [int(x) for x in items] if all(x.isdigit() for x in items) else items
            except Exception:
                return items
        return v

    @validator("include_threads", "include_attachments_metadata", "include_bot_authors", pre=True)
    def _coerce_bool(cls, v):
        if v is None or isinstance(v, bool):
            return v
        if isinstance(v, (int, float)):
            return bool(v)
        if isinstance(v, str):
            s = v.strip().lower()
            if s in {"", "default"}:  # leave UI default
                return v
            if s in {"1", "true", "t", "yes", "y", "on"}:
                return True
            if s in {"0", "false", "f", "no", "n", "off"}:
                return False
        raise ValueError("Invalid boolean")

    @validator("page_size", "max_messages_per_channel", pre=True)
    def _coerce_int(cls, v):
        if v is None or isinstance(v, (int, float)):
            return None if v is None else int(v)
        if isinstance(v, str):
            s = v.strip().replace(",", "").replace("_", "")
            return int(s) if s != "" else None
        return v


class MicrosoftTeamsConfig(SourceConfig):
    """Teams (Graph) delegated config: reads the signed-in user's accessible data."""

    # What to sync
    include_channels: bool = Field(
        default=True,
        title="Include Teams channel messages",
        description="From the user's joined teams and channels they can see.",
    )
    include_chats: bool = Field(
        default=True,
        title="Include user chats (DMs, group, meeting)",
        description="Reads chat messages for chats the user participates in.",
    )

    # Narrowing
    team_ids: list[str] = Field(
        default=[],
        title="Team IDs (optional)",
        description="Restrict to these team (group) IDs; empty = all /me/joinedTeams.",
    )
    channel_ids: list[str] = Field(
        default=[],
        title="Channel IDs (optional)",
        description="Restrict to these channel IDs; empty = all channels in each selected team.",
    )
    chat_ids: list[str] = Field(
        default=[],
        title="Chat IDs (optional)",
        description="Restrict to these chat IDs; empty = all /me/chats.",
    )

    # Message options
    include_replies: bool = Field(
        default=True,
        title="Include channel replies",
        description=("Uses $expand=replies (Graph returns up to ~1000 replies per message page)."),
    )
    include_attachments_metadata: bool = Field(
        default=True,
        title="Include attachment metadata",
        description=(
            "Index attachment metadata (name, type, contentUrl/hostedContent IDs). "
            "Files are not downloaded."
        ),
    )

    # Paging / incremental
    page_size: int = Field(
        default=50,
        title="Page size ($top)",
        description="Graph caps most message list endpoints at 50.",
    )
    max_messages_per_conversation: Optional[int] = Field(
        default=None,
        title="Max per conversation (full sync)",
        description="Cap when walking history (blank = no cap).",
    )

    @validator("team_ids", "channel_ids", "chat_ids", pre=True)
    def _csv_to_list(cls, v):
        if isinstance(v, str):
            return [x.strip() for x in v.split(",") if x.strip()]
        return v

    @validator(
        "include_channels",
        "include_chats",
        "include_replies",
        "include_attachments_metadata",
        pre=True,
    )
    def _coerce_bool(cls, v):
        if v is None or isinstance(v, bool):
            return v
        if isinstance(v, (int, float)):
            return bool(v)
        if isinstance(v, str):
            s = v.strip().lower()
            if s in {"1", "true", "t", "yes", "y", "on"}:
                return True
            if s in {"0", "false", "f", "no", "n", "off"}:
                return False
        raise ValueError("Invalid boolean")

    @validator("page_size", "max_messages_per_conversation", pre=True)
    def _coerce_int(cls, v):
        if v is None:
            return None
        if isinstance(v, (int, float)):
            return int(v)
        if isinstance(v, str):
            s = v.strip().replace(",", "").replace("_", "")
            return int(s) if s != "" else None
        return v


class AirtableConfig(SourceConfig):
    """Airtable source behavior flags (used with OAuth 2.0)."""

    base_ids: list[str] = Field(
        default=[],
        title="Base IDs",
        description="Base IDs to sync (e.g., 'appXXXXXXXX'). If empty, "
        "list bases via Meta API and sync all.",
    )
    table_ids: list[str] = Field(
        default=[],
        title="Table IDs",
        description="Restrict to these table IDs (e.g., "
        "'tblXXXXXXXX'). If empty, include all tables.",
    )
    table_names: list[str] = Field(
        default=[],
        title="Table Names",
        description="Restrict to tables with these names (per base). If empty, include all tables.",
    )
    view: Optional[str] = Field(
        default=None,
        title="View",
        description="Optional view name/ID to filter records for each table.",
    )
    fields: list[str] = Field(
        default=[],
        title="Fields",
        description="Optional subset of field names to fetch for each table. Empty = all fields.",
    )
    filter_by_formula: Optional[str] = Field(
        default=None,
        title="Filter by formula",
        description="Airtable filterByFormula applied to all tables (advanced).",
    )
    page_size: Optional[int] = Field(
        default=100, title="Page size", description="Records per page (max 100)."
    )
    max_records: Optional[int] = Field(
        default=None,
        title="Max records",
        description="Global cap across each table; blank for no cap.",
    )
    include_attachments: bool = Field(
        default=True,
        title="Attachments",
        description="Download & index files from attachment fields.",
    )
    attachment_max_bytes: Optional[int] = Field(
        default=None,
        title="Attachment size cap (bytes)",
        description="Skip attachment downloads larger than this.",
    )

    @validator("base_ids", "table_ids", "table_names", "fields", pre=True)
    def _parse_csv(cls, v):
        if isinstance(v, str):
            return [x.strip() for x in v.split(",") if x.strip()]
        return v

    # blank-string-friendly coercion
    @staticmethod
    def _parse_bool(value: Any, default: bool) -> bool:
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        if isinstance(value, str):
            s = value.strip().lower()
            if s == "":
                return default
            if s in {"1", "true", "t", "yes", "y", "on"}:
                return True
            if s in {"0", "false", "f", "no", "n", "off"}:
                return False
        raise ValueError("Invalid boolean")

    @field_validator("include_attachments", mode="before")
    @classmethod
    def _v_include_attachments(cls, v):
        return cls._parse_bool(v, default=True)

    @field_validator("page_size", "max_records", "attachment_max_bytes", mode="before")
    @classmethod
    def _v_ints(cls, v):
        if v is None:
            return v
        if isinstance(v, (int, float)):
            return int(v)
        if isinstance(v, str):
            s = v.strip().replace(",", "").replace("_", "")
            if s == "":
                return None
            return int(s)
        return v


# ----------------- AUTH PROVIDER CONFIGS -----------------


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
    environment: str = Field(
        default="production",
        title="Environment",
        description="Pipedream environment (production or development)",
    )
    external_user_id: Optional[str] = Field(
        default=None,
        title="External User ID",
        description="External user ID associated with the account",
    )
