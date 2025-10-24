"""Mock helpers for testing entity pipeline."""

import logging
from unittest.mock import AsyncMock, Mock
from uuid import UUID

# Import entity types for entity_map
from airweave.platform.entities.asana import (
    AsanaCommentEntity,
    AsanaFileEntity,
    AsanaProjectEntity,
    AsanaSectionEntity,
    AsanaTaskEntity,
    AsanaWorkspaceEntity,
)
from airweave.platform.entities.github import (
    GitHubCodeFileEntity,
    GitHubDirectoryEntity,
    GitHubRepositoryEntity,
)
from airweave.platform.entities.gmail import GmailMessageEntity, GmailThreadEntity
from airweave.platform.entities.google_calendar import (
    GoogleCalendarCalendarEntity,
    GoogleCalendarEventEntity,
    GoogleCalendarListEntity,
)
from airweave.platform.entities.google_drive import GoogleDriveDriveEntity, GoogleDriveFileEntity
from airweave.platform.entities.notion import (
    NotionDatabaseEntity,
    NotionFileEntity,
    NotionPageEntity,
    NotionPropertyEntity,
)
from airweave.platform.entities.stripe import (
    StripeBalanceEntity,
    StripeBalanceTransactionEntity,
    StripeChargeEntity,
    StripeCustomerEntity,
    StripeEventEntity,
    StripeInvoiceEntity,
    StripePaymentIntentEntity,
    StripePaymentMethodEntity,
    StripePayoutEntity,
    StripeRefundEntity,
    StripeSubscriptionEntity,
)
from airweave.platform.entities.teams import (
    TeamsChannelEntity,
    TeamsChatEntity,
    TeamsMessageEntity,
    TeamsTeamEntity,
    TeamsUserEntity,
)


def create_mock_sync_context(source_name: str = "asana"):
    """Create a mock sync context with real logger for visible output.

    Args:
        source_name: Short name of the source (default: "asana")
    """
    ctx = Mock()

    ctx.source = Mock()
    ctx.source._short_name = source_name

    ctx.destinations = [Mock()]

    ctx.embedding_model = Mock()

    ctx.keyword_indexing_model = Mock()

    ctx.transformers = {}

    ctx.sync = Mock()
    ctx.sync.id = UUID("12345678-1234-5678-1234-567812345678")

    ctx.sync_job = Mock()
    ctx.sync_job.id = UUID("87654321-4321-8765-4321-876543218765")

    ctx.progress = AsyncMock()

    ctx.entity_state_tracker = Mock()

    ctx.cursor = Mock()

    ctx.collection = Mock()
    ctx.collection.id = UUID("11111111-2222-3333-4444-555555555555")

    ctx.connection = Mock()

    # Entity map with mock UUIDs for entity types
    ctx.entity_map = {
        # Asana
        AsanaWorkspaceEntity: UUID("aaaaaaaa-0000-0000-0000-000000000001"),
        AsanaProjectEntity: UUID("aaaaaaaa-0000-0000-0000-000000000002"),
        AsanaSectionEntity: UUID("aaaaaaaa-0000-0000-0000-000000000003"),
        AsanaTaskEntity: UUID("aaaaaaaa-0000-0000-0000-000000000004"),
        AsanaCommentEntity: UUID("aaaaaaaa-0000-0000-0000-000000000005"),
        AsanaFileEntity: UUID("aaaaaaaa-0000-0000-0000-000000000006"),
        # Google Calendar
        GoogleCalendarListEntity: UUID("bbbbbbbb-0000-0000-0000-000000000001"),
        GoogleCalendarCalendarEntity: UUID("bbbbbbbb-0000-0000-0000-000000000002"),
        GoogleCalendarEventEntity: UUID("bbbbbbbb-0000-0000-0000-000000000003"),
        # Google Drive
        GoogleDriveDriveEntity: UUID("cccccccc-0000-0000-0000-000000000001"),
        GoogleDriveFileEntity: UUID("cccccccc-0000-0000-0000-000000000002"),
        # GitHub
        GitHubRepositoryEntity: UUID("dddddddd-0000-0000-0000-000000000001"),
        GitHubDirectoryEntity: UUID("dddddddd-0000-0000-0000-000000000002"),
        GitHubCodeFileEntity: UUID("dddddddd-0000-0000-0000-000000000003"),
        # Gmail
        GmailThreadEntity: UUID("eeeeeeee-0000-0000-0000-000000000001"),
        GmailMessageEntity: UUID("eeeeeeee-0000-0000-0000-000000000002"),
        # Notion
        NotionDatabaseEntity: UUID("ffffffff-0000-0000-0000-000000000001"),
        NotionPageEntity: UUID("ffffffff-0000-0000-0000-000000000002"),
        NotionPropertyEntity: UUID("ffffffff-0000-0000-0000-000000000003"),
        NotionFileEntity: UUID("ffffffff-0000-0000-0000-000000000004"),
        # Stripe
        StripeBalanceEntity: UUID("11111111-0000-0000-0000-000000000001"),
        StripeBalanceTransactionEntity: UUID("11111111-0000-0000-0000-000000000002"),
        StripeChargeEntity: UUID("11111111-0000-0000-0000-000000000003"),
        StripeCustomerEntity: UUID("11111111-0000-0000-0000-000000000004"),
        StripeEventEntity: UUID("11111111-0000-0000-0000-000000000005"),
        StripeInvoiceEntity: UUID("11111111-0000-0000-0000-000000000006"),
        StripePaymentIntentEntity: UUID("11111111-0000-0000-0000-000000000007"),
        StripePaymentMethodEntity: UUID("11111111-0000-0000-0000-000000000008"),
        StripePayoutEntity: UUID("11111111-0000-0000-0000-000000000009"),
        StripeRefundEntity: UUID("11111111-0000-0000-0000-00000000000a"),
        StripeSubscriptionEntity: UUID("11111111-0000-0000-0000-00000000000b"),
        # Teams
        TeamsUserEntity: UUID("22222222-0000-0000-0000-000000000001"),
        TeamsTeamEntity: UUID("22222222-0000-0000-0000-000000000002"),
        TeamsChannelEntity: UUID("22222222-0000-0000-0000-000000000003"),
        TeamsChatEntity: UUID("22222222-0000-0000-0000-000000000004"),
        TeamsMessageEntity: UUID("22222222-0000-0000-0000-000000000005"),
    }

    ctx.ctx = Mock()

    ctx.guard_rail = Mock()

    # Use REAL logger instead of Mock so we can see log output
    # Using root logger to ensure all logs are captured, including from async tasks
    logger = logging.getLogger("test_entity_pipeline")
    logger.setLevel(logging.DEBUG)
    logger.propagate = True  # Ensure logs propagate to root logger (pytest captures this)

    # Clear any existing handlers to avoid duplicates
    logger.handlers.clear()

    # Add handler that writes to stdout (pytest captures this with -s flag)
    handler = logging.StreamHandler()
    handler.setLevel(logging.DEBUG)  # Capture all levels including WARNING
    formatter = logging.Formatter("%(levelname)s - %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    ctx.logger = logger

    ctx.force_full_sync = False

    ctx.has_keyword_index = False

    ctx.should_batch = True

    ctx.batch_size = 64

    ctx.max_batch_latency_ms = 200

    ctx.max_queue_size = 100

    return ctx
