"""Response builder for source connections.

Assembles the rich SourceConnection and SourceConnectionListItem
response schemas from multiple data sources.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional
from uuid import UUID

from croniter import croniter
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import schemas
from airweave.api.context import ApiContext
from airweave.core.config import settings as core_settings
from airweave.core.shared_models import SourceConnectionErrorCategory, SyncJobStatus, SyncStatus
from airweave.domains.connections.protocols import ConnectionRepositoryProtocol
from airweave.domains.credentials.protocols import IntegrationCredentialRepositoryProtocol
from airweave.domains.entities.protocols import EntityCountRepositoryProtocol
from airweave.domains.source_connections.protocols import (
    ResponseBuilderProtocol,
    SourceConnectionRepositoryProtocol,
)
from airweave.domains.source_connections.types import SourceConnectionStats
from airweave.domains.sources.protocols import SourceRegistryProtocol
from airweave.domains.syncs.jobs.protocols import SyncJobRepositoryProtocol
from airweave.models.source_connection import SourceConnection
from airweave.models.sync import Sync
from airweave.models.sync_job import SyncJob
from airweave.schemas.source_connection import (
    AuthenticationDetails,
    AuthenticationMethod,
    SourceConnectionJob,
    SourceConnectionListItem,
    compute_status,
    determine_auth_method,
)
from airweave.schemas.source_connection import (
    SourceConnection as SourceConnectionSchema,
)

if TYPE_CHECKING:
    from airweave.domains.auth_provider.protocols import AuthProviderRegistryProtocol


@dataclass(frozen=True, slots=True)
class _ProviderInfo:
    """Resolved auth provider info for credential error UI."""

    settings_url: Optional[str] = None
    short_name: Optional[str] = None


_EMPTY_PROVIDER_INFO = _ProviderInfo()

# Generic user-safe messages per error category (raw exception details stay in SyncJobDetails.error)
_GENERIC_ERROR_MESSAGES: dict[SourceConnectionErrorCategory, str] = {
    SourceConnectionErrorCategory.OAUTH_CREDENTIALS_EXPIRED: (
        "Your OAuth authorization has expired or been revoked."
    ),
    SourceConnectionErrorCategory.API_KEY_INVALID: (
        "The API key for this connection is no longer valid."
    ),
    SourceConnectionErrorCategory.AUTH_PROVIDER_ACCOUNT_GONE: (
        "The connected account on the auth provider has been deleted or deactivated."
    ),
    SourceConnectionErrorCategory.AUTH_PROVIDER_CREDENTIALS_INVALID: (
        "The credentials on the auth provider need to be refreshed or re-configured."
    ),
}


class ResponseBuilder(ResponseBuilderProtocol):
    """Builds API response schemas for source connections."""

    def __init__(
        self,
        sc_repo: SourceConnectionRepositoryProtocol,
        connection_repo: ConnectionRepositoryProtocol,
        credential_repo: IntegrationCredentialRepositoryProtocol,
        source_registry: SourceRegistryProtocol,
        entity_count_repo: EntityCountRepositoryProtocol,
        sync_job_repo: SyncJobRepositoryProtocol,
        auth_provider_registry: Optional["AuthProviderRegistryProtocol"] = None,
    ) -> None:
        """Initialize with all dependencies."""
        self._sc_repo = sc_repo
        self._connection_repo = connection_repo
        self._credential_repo = credential_repo
        self._source_registry = source_registry
        self._entity_count_repo = entity_count_repo
        self._sync_job_repo = sync_job_repo
        self._auth_provider_registry = auth_provider_registry

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def build_response(
        self,
        db: AsyncSession,
        source_conn: SourceConnection,
        ctx: ApiContext,
        *,
        auth_url_override: Optional[str] = None,
        auth_url_expiry_override: Optional[datetime] = None,
        claim_token: Optional[str] = None,
    ) -> SourceConnectionSchema:
        """Build complete SourceConnection response from an ORM object."""
        sync_details = await self._build_sync_details(db, source_conn, ctx)
        sync_status = await self._fetch_sync_status(db, source_conn)

        last_job_status = None
        last_job_error_category = None
        if sync_details and sync_details.last_job:
            last_job_status = sync_details.last_job.status
            last_job_error_category = sync_details.last_job.error_category

        auth = await self._build_auth_details(
            db,
            source_conn,
            ctx,
            auth_url_override=auth_url_override,
            auth_url_expiry_override=auth_url_expiry_override,
            claim_token=claim_token,
            has_credential_error=last_job_error_category is not None,
        )
        schedule = await self._build_schedule_details(db, source_conn, ctx)
        entities = await self._build_entity_summary(db, source_conn, ctx)
        federated_search = self._get_federated_search(source_conn)

        provider_info = _EMPTY_PROVIDER_INFO
        if last_job_error_category and self._auth_provider_registry:
            provider_info = await self._resolve_provider_info(db, source_conn, ctx)

        return SourceConnectionSchema(
            id=source_conn.id,
            organization_id=source_conn.organization_id,
            name=source_conn.name,
            description=source_conn.description,
            short_name=source_conn.short_name,
            readable_collection_id=source_conn.readable_collection_id,
            status=compute_status(
                source_conn, last_job_status, last_job_error_category, sync_status=sync_status
            ),
            created_at=source_conn.created_at,
            modified_at=source_conn.modified_at,
            auth=auth,
            config=source_conn.config_fields,
            schedule=schedule,
            sync=sync_details,
            sync_id=source_conn.sync_id,
            entities=entities,
            error_category=last_job_error_category,
            error_message=_GENERIC_ERROR_MESSAGES.get(last_job_error_category, None)
            if last_job_error_category
            else None,
            provider_settings_url=provider_info.settings_url,
            provider_short_name=provider_info.short_name,
            federated_search=federated_search,
        )

    def build_list_item(self, stats: SourceConnectionStats) -> SourceConnectionListItem:
        """Build a SourceConnectionListItem from a typed stats object."""
        last_job_status = stats.last_job.status if stats.last_job else None
        last_job_error_category = stats.last_job.error_category if stats.last_job else None

        return SourceConnectionListItem(
            id=stats.id,
            name=stats.name,
            short_name=stats.short_name,
            readable_collection_id=stats.readable_collection_id,
            created_at=stats.created_at,
            modified_at=stats.modified_at,
            is_authenticated=stats.is_authenticated,
            authentication_method=stats.authentication_method,
            entity_count=stats.entity_count,
            is_active=stats.is_active,
            last_job_status=last_job_status,
            last_job_error_category=last_job_error_category,
            federated_search=stats.federated_search,
            sync_status=stats.sync_status,
        )

    def map_sync_job(self, job: SyncJob, source_connection_id: UUID) -> SourceConnectionJob:
        """Convert a sync job ORM object to a SourceConnectionJob schema."""
        return SourceConnectionJob(
            id=job.id,
            source_connection_id=source_connection_id,
            status=job.status,
            started_at=job.started_at,
            completed_at=job.completed_at,
            duration_seconds=(
                (job.completed_at - job.started_at).total_seconds()
                if job.completed_at and job.started_at
                else None
            ),
            entities_inserted=job.entities_inserted,
            entities_updated=job.entities_updated,
            entities_deleted=job.entities_deleted,
            entities_failed=job.entities_skipped,
            error=job.error,
            error_category=job.error_category,
        )

    # ------------------------------------------------------------------
    # Private helpers — auth
    # ------------------------------------------------------------------

    async def _build_auth_details(
        self,
        db: AsyncSession,
        source_conn: SourceConnection,
        ctx: ApiContext,
        *,
        auth_url_override: Optional[str] = None,
        auth_url_expiry_override: Optional[datetime] = None,
        claim_token: Optional[str] = None,
        has_credential_error: bool = False,
    ) -> AuthenticationDetails:
        """Build authentication details section."""
        actual_auth_method = await self._resolve_auth_method(db, source_conn, ctx)

        authenticated_at = source_conn.created_at if source_conn.is_authenticated else None

        provider_id: Optional[str] = None
        provider_readable_id: Optional[str] = None
        if source_conn.readable_auth_provider_id:
            provider_id = source_conn.readable_auth_provider_id
            provider_readable_id = source_conn.readable_auth_provider_id

        auth_url: Optional[str] = None
        auth_url_expires: Optional[datetime] = None
        redirect_url: Optional[str] = None

        if auth_url_override:
            # [code blue] wire auth_url overrides from service layer during BYOC flows
            auth_url = auth_url_override
            auth_url_expires = auth_url_expiry_override
        elif source_conn.connection_init_session_id:
            resolved_auth_url, auth_url_expires, redirect_url = await self._resolve_oauth_pending(
                db, source_conn, ctx
            )
            # Only expose auth_url when the connection needs (re-)authentication
            # or when a fresh claim_token signals an active OAuth initiation
            if not source_conn.is_authenticated or has_credential_error or claim_token:
                auth_url = resolved_auth_url

        return AuthenticationDetails(
            method=actual_auth_method,
            authenticated=source_conn.is_authenticated,
            authenticated_at=authenticated_at,
            provider_id=provider_id,
            provider_readable_id=provider_readable_id,
            auth_url=auth_url,
            auth_url_expires=auth_url_expires,
            redirect_url=redirect_url,
            claim_token=claim_token,
        )

    async def _resolve_auth_method(
        self, db: AsyncSession, source_conn: SourceConnection, ctx: ApiContext
    ) -> AuthenticationMethod:
        """Resolve the auth method from auth provider, credential, or fallback."""
        if source_conn.readable_auth_provider_id:
            return AuthenticationMethod.AUTH_PROVIDER

        if source_conn.connection_id:
            connection = await self._connection_repo.get(db, source_conn.connection_id, ctx)
            if connection and connection.integration_credential_id:
                credential = await self._credential_repo.get(
                    db, connection.integration_credential_id, ctx
                )
                if credential:
                    method_map = {
                        "oauth_token": AuthenticationMethod.OAUTH_TOKEN,
                        "oauth_browser": AuthenticationMethod.OAUTH_BROWSER,
                        "oauth_byoc": AuthenticationMethod.OAUTH_BYOC,
                        "direct": AuthenticationMethod.DIRECT,
                        "auth_provider": AuthenticationMethod.AUTH_PROVIDER,
                    }
                    resolved = method_map.get(credential.authentication_method)
                    if resolved:
                        return resolved

        return determine_auth_method(source_conn)

    async def _resolve_oauth_pending(
        self,
        db: AsyncSession,
        source_conn: SourceConnection,
        ctx: ApiContext,
    ) -> tuple[Optional[str], Optional[datetime], Optional[str]]:
        """Resolve OAuth pending auth_url, expiry, and redirect_url from init session.

        Returns (auth_url, auth_url_expires, redirect_url).
        """
        init_session = await self._sc_repo.get_init_session_with_redirect(
            db, source_conn.connection_init_session_id, ctx
        )

        auth_url: Optional[str] = None
        auth_url_expires: Optional[datetime] = None
        redirect_url: Optional[str] = None

        if init_session:
            if init_session.overrides:
                redirect_url = init_session.overrides.get("redirect_url")

            if init_session.redirect_session:
                auth_url = (
                    f"{core_settings.api_url}/source-connections/authorize/"
                    f"{init_session.redirect_session.code}"
                )
                auth_url_expires = init_session.redirect_session.expires_at
        elif (
            hasattr(source_conn, "authentication_url")
            and source_conn.authentication_url
            and not source_conn.is_authenticated
        ):
            # Backward-compatible fallback for temporary auth URL attributes.
            auth_url = source_conn.authentication_url
            auth_url_expires = source_conn.authentication_url_expiry

        return auth_url, auth_url_expires, redirect_url

    # ------------------------------------------------------------------
    # Private helpers — schedule, sync, entities, federated search
    # ------------------------------------------------------------------

    async def _build_schedule_details(
        self, db: AsyncSession, source_conn: SourceConnection, ctx: ApiContext
    ) -> Optional[schemas.ScheduleDetails]:
        """Build schedule details section."""
        if not source_conn.sync_id:
            return None
        try:
            schedule_info = await self._sc_repo.get_schedule_info(db, source_connection=source_conn)
            if schedule_info:
                cron_expression = schedule_info.get("cron_expression")
                next_run_at = None
                if cron_expression:
                    base = datetime.now(timezone.utc)
                    cron = croniter(cron_expression, base)
                    next_run_at = cron.get_next(datetime)
                return schemas.ScheduleDetails(
                    cron=cron_expression,
                    next_run=next_run_at,
                    continuous=schedule_info.get("is_continuous", False),
                    cursor_field=schedule_info.get("cursor_field"),
                    cursor_value=schedule_info.get("cursor_value"),
                )
        except Exception as e:
            ctx.logger.warning(f"Failed to get schedule info: {e}")
        return None

    async def _build_sync_details(
        self, db: AsyncSession, source_conn: SourceConnection, ctx: ApiContext
    ) -> Optional[schemas.SyncDetails]:
        """Build sync/job details section."""
        if not source_conn.sync_id:
            return None
        try:
            job = await self._sync_job_repo.get_latest_by_sync_id(db, sync_id=source_conn.sync_id)
            if job:
                duration_seconds = None
                if job.completed_at and job.started_at:
                    duration_seconds = (job.completed_at - job.started_at).total_seconds()

                last_job = schemas.SyncJobDetails(
                    id=job.id,
                    status=job.status,
                    started_at=job.started_at,
                    completed_at=job.completed_at,
                    duration_seconds=duration_seconds,
                    entities_inserted=job.entities_inserted or 0,
                    entities_updated=job.entities_updated or 0,
                    entities_deleted=job.entities_deleted or 0,
                    entities_failed=job.entities_skipped or 0,
                    error=job.error,
                    error_category=job.error_category,
                )

                return schemas.SyncDetails(
                    total_runs=1,
                    successful_runs=1 if job.status == SyncJobStatus.COMPLETED else 0,
                    failed_runs=1 if job.status == SyncJobStatus.FAILED else 0,
                    last_job=last_job,
                )

        except Exception as e:
            ctx.logger.warning(f"Failed to get sync details: {e}")
        return None

    async def _build_entity_summary(
        self, db: AsyncSession, source_conn: SourceConnection, ctx: ApiContext
    ) -> Optional[schemas.EntitySummary]:
        """Build entity summary section."""
        if not source_conn.sync_id:
            return None
        try:
            entity_counts = await self._entity_count_repo.get_counts_per_sync_and_type(
                db, source_conn.sync_id
            )

            if entity_counts:
                total_entities = sum(count_data.count for count_data in entity_counts)
                by_type = {}
                for count_data in entity_counts:
                    by_type[count_data.entity_definition_name] = schemas.EntityTypeStats(
                        count=count_data.count,
                        last_updated=count_data.modified_at,
                    )

                return schemas.EntitySummary(
                    total_entities=total_entities,
                    by_type=by_type,
                )
        except Exception as e:
            ctx.logger.warning(f"Failed to get entity summary: {e}")
        return None

    async def _resolve_provider_info(
        self,
        db: Optional[AsyncSession],
        source_conn: SourceConnection,
        ctx: ApiContext,
    ) -> _ProviderInfo:
        """Resolve auth provider settings URL and short_name for credential error UI.

        The source connection stores a readable_auth_provider_id (e.g. "my-composio")
        which is the Connection.readable_id, not the auth provider short_name.
        We look up the Connection to get its short_name for the registry.
        """
        if not self._auth_provider_registry or not source_conn.readable_auth_provider_id:
            return _EMPTY_PROVIDER_INFO
        try:
            if db:
                connection = await self._connection_repo.get_by_readable_id(
                    db, source_conn.readable_auth_provider_id, ctx
                )
                if connection:
                    url = self._auth_provider_registry.get_settings_url(connection.short_name)
                    return _ProviderInfo(settings_url=url, short_name=connection.short_name)
            return _EMPTY_PROVIDER_INFO
        except Exception:
            return _EMPTY_PROVIDER_INFO

    async def _fetch_sync_status(
        self, db: Optional[AsyncSession], source_conn: SourceConnection
    ) -> Optional[SyncStatus]:
        """Fetch Sync.status for the detail view."""
        if not db or not source_conn.sync_id:
            return None
        try:
            from sqlalchemy import select as sa_select

            row = (
                await db.execute(sa_select(Sync.status).where(Sync.id == source_conn.sync_id))
            ).first()
            return SyncStatus(row.status) if row else None
        except Exception:
            return None

    def _get_federated_search(self, source_conn: SourceConnection) -> bool:
        """Get federated_search flag from the source registry."""
        try:
            entry = self._source_registry.get(source_conn.short_name)
            return entry.federated_search
        except KeyError:
            return False
