# flake8: noqa: F401
"""Schemas for the application."""

from airweave.platform.auth.schemas import OAuth2AuthUrl, OAuth2TokenResponse

from .admin import OrganizationMetrics
from .api_key import APIKey, APIKeyCreate, APIKeyInDBBase, APIKeyUpdate
from .auth_provider import (
    AuthProvider,
    AuthProviderConnection,
    AuthProviderConnectionCreate,
    AuthProviderConnectionUpdate,
    AuthProviderCreate,
    AuthProviderUpdate,
)
from .billing_period import (
    BillingPeriod,
    BillingPeriodCreate,
    BillingPeriodStatus,
    BillingPeriodUpdate,
    BillingPeriodWithUsage,
    BillingTransition,
)
from .collection import (
    Collection,
    CollectionCreate,
    CollectionRecord,
    CollectionUpdate,
)
from .connection import Connection, ConnectionCreate, ConnectionInDBBase, ConnectionUpdate
from .destination import (
    Destination,
    DestinationCreate,
    DestinationInDBBase,
    DestinationUpdate,
    DestinationWithAuthenticationFields,
)
from .embedding_model import (
    EmbeddingModel,
    EmbeddingModelCreate,
    EmbeddingModelInDBBase,
    EmbeddingModelUpdate,
    EmbeddingModelWithAuthenticationFields,
)
from .entity import Entity, EntityCount, EntityCreate, EntityInDBBase, EntityUpdate
from .entity_count import EntityCount as EntityCountSchema
from .entity_count import EntityCountCreate, EntityCountUpdate, EntityCountWithDefinition
from .entity_definition import (
    EntityDefinition,
    EntityDefinitionCreate,
    EntityDefinitionUpdate,
    EntityType,
)
from .errors import (
    ConflictErrorResponse,
    NotFoundErrorResponse,
    RateLimitErrorResponse,
    ValidationErrorDetail,
    ValidationErrorResponse,
)
from .integration_credential import (
    IntegrationCredential,
    IntegrationCredentialCreate,
    IntegrationCredentialCreateEncrypted,
    IntegrationCredentialInDB,
    IntegrationCredentialRawCreate,
    IntegrationCredentialUpdate,
)
from .invitation import (
    InvitationBase,
    InvitationCreate,
    InvitationResponse,
    MemberResponse,
)
from .organization import (
    Organization,
    OrganizationBase,
    OrganizationCreate,
    OrganizationInDBBase,
    OrganizationUpdate,
    OrganizationWithRole,
)
from .organization_billing import (
    BillingPlan,
    BillingStatus,
    CancelSubscriptionRequest,
    CheckoutSessionRequest,
    CheckoutSessionResponse,
    CustomerPortalRequest,
    CustomerPortalResponse,
    MessageResponse,
    OrganizationBilling,
    OrganizationBillingCreate,
    OrganizationBillingUpdate,
    PaymentStatus,
    PlanLimits,
    SubscriptionInfo,
    UpdatePlanRequest,
)
from .search import SearchRequest, SearchResponse
from .search_query import (
    SearchQueryAnalytics,
    SearchQueryCreate,
    SearchQueryInsights,
    SearchQueryResponse,
    SearchQueryUpdate,
)
from .source import (
    Source,
    SourceCreate,
    SourceInDBBase,
    SourceUpdate,
)
from .source_connection import (
    AuthenticationDetails,
    AuthenticationMethod,
    EntitySummary,
    EntityTypeStats,
    ScheduleDetails,
    SourceConnection,
    SourceConnectionCreate,
    SourceConnectionJob,
    SourceConnectionListItem,
    SourceConnectionSimple,
    SourceConnectionUpdate,
    SyncDetails,
    SyncJobDetails,
)
from .source_rate_limit import (
    SourceRateLimit,
    SourceRateLimitCreate,
    SourceRateLimitResponse,
    SourceRateLimitUpdate,
    SourceRateLimitUpdateRequest,
)
from .sync import (
    MinuteLevelScheduleConfig,
    ScheduleResponse,
    Sync,
    SyncBase,
    SyncCreate,
    SyncInDBBase,
    SyncUpdate,
    SyncWithoutConnections,
    SyncWithSourceConnection,
)
from .sync_cursor import (
    SyncCursor,
    SyncCursorBase,
    SyncCursorCreate,
    SyncCursorUpdate,
)
from .sync_job import (
    SyncJob,
    SyncJobCreate,
    SyncJobInDBBase,
    SyncJobUpdate,
)
from .transformer import Transformer, TransformerCreate, TransformerUpdate
from .usage import (
    SingleActionCheckResponse,
    Usage,
    UsageCreate,
    UsageInDBBase,
    UsageLimit,
    UsageUpdate,
)
from .user import (
    User,
    UserCreate,
    UserInDB,
    UserInDBBase,
    UserOrganization,
    UserUpdate,
    UserWithOrganizations,
)
from .webhooks import (
    # Request schemas
    CreateSubscriptionRequest,
    # Response schemas
    DeliveryAttempt,
    PatchSubscriptionRequest,
    RecoverMessagesRequest,
    RecoveryTask,
    WebhookMessage,
    WebhookMessageWithAttempts,
    WebhookSubscription,
)

# Rebuild models to resolve forward references
# This is necessary because OrganizationBilling references BillingPeriod as a string
OrganizationBilling.model_rebuild()
Organization.model_rebuild()
OrganizationWithRole.model_rebuild()
UserOrganization.model_rebuild()
User.model_rebuild()
