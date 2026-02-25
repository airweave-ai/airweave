"""Domain service for auth provider connections."""

from typing import Optional

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import schemas
from airweave.api.context import ApiContext
from airweave.core import credentials
from airweave.core.datetime_utils import utc_now_naive
from airweave.core.shared_models import ConnectionStatus, IntegrationType
from airweave.db.unit_of_work import UnitOfWork
from airweave.domains.auth_provider.protocols import (
    AuthProviderRegistryProtocol,
    AuthProviderServiceProtocol,
)
from airweave.domains.auth_provider.types import AuthProviderRegistryEntry
from airweave.domains.connections.protocols import ConnectionRepositoryProtocol
from airweave.domains.credentials.protocols import IntegrationCredentialRepositoryProtocol
from airweave.models.connection import Connection
from airweave.platform.auth.settings import AuthenticationMethod


class AuthProviderService(AuthProviderServiceProtocol):
    """Service for auth provider connection operations."""

    def __init__(
        self,
        auth_provider_registry: AuthProviderRegistryProtocol,
        connection_repo: ConnectionRepositoryProtocol,
        credential_repo: IntegrationCredentialRepositoryProtocol,
    ) -> None:
        """Initialize service dependencies."""
        self._registry = auth_provider_registry
        self._connection_repo = connection_repo
        self._credential_repo = credential_repo

    async def list_connections(
        self, db: AsyncSession, *, ctx: ApiContext, skip: int = 0, limit: int = 100
    ) -> list[schemas.AuthProviderConnection]:
        """List auth provider connections for the current organization."""
        connections = await self._connection_repo.get_by_integration_type(
            db, integration_type=IntegrationType.AUTH_PROVIDER, ctx=ctx
        )
        result: list[schemas.AuthProviderConnection] = []

        for connection in connections[skip : skip + limit]:
            result.append(await self._to_schema(db, connection, ctx))
        return result

    async def get_connection(
        self, db: AsyncSession, *, readable_id: str, ctx: ApiContext
    ) -> schemas.AuthProviderConnection:
        """Get an auth provider connection."""
        connection = await self._get_auth_provider_connection(db, readable_id=readable_id, ctx=ctx)
        return await self._to_schema(db, connection, ctx)

    async def create_connection(
        self,
        db: AsyncSession,
        *,
        obj_in: schemas.AuthProviderConnectionCreate,
        ctx: ApiContext,
    ) -> schemas.AuthProviderConnection:
        """Create an auth provider connection."""
        entry = self._get_registry_entry(obj_in.short_name)
        validated_auth_fields = self._validate_auth_fields(entry, obj_in.auth_fields)
        await self._validate_credentials(
            entry=entry,
            validated_auth_fields=validated_auth_fields,
            validated_provider_config={},
            ctx=ctx,
        )

        async with UnitOfWork(db) as uow:
            integration_credential = await self._credential_repo.create(
                uow.session,
                obj_in=schemas.IntegrationCredentialCreateEncrypted(
                    name=f"{obj_in.name} Credentials",
                    integration_short_name=obj_in.short_name,
                    description=f"Credentials for {obj_in.name}",
                    integration_type=IntegrationType.AUTH_PROVIDER,
                    authentication_method=AuthenticationMethod.DIRECT,
                    encrypted_credentials=credentials.encrypt(validated_auth_fields),
                    auth_config_class=entry.auth_config_ref.__name__,
                ),
                ctx=ctx,
                uow=uow,
            )
            await uow.session.flush()

            connection = await self._connection_repo.create(
                uow.session,
                obj_in=schemas.ConnectionCreate(
                    name=obj_in.name,
                    readable_id=obj_in.readable_id,
                    description=f"Auth provider connection for {obj_in.name}",
                    integration_type=IntegrationType.AUTH_PROVIDER,
                    status=ConnectionStatus.ACTIVE,
                    integration_credential_id=integration_credential.id,
                    short_name=obj_in.short_name,
                ),
                ctx=ctx,
                uow=uow,
            )
            await uow.session.flush()

            return await self._to_schema(uow.session, connection, ctx)

    async def update_connection(
        self,
        db: AsyncSession,
        *,
        readable_id: str,
        obj_in: schemas.AuthProviderConnectionUpdate,
        ctx: ApiContext,
    ) -> schemas.AuthProviderConnection:
        """Update an auth provider connection."""
        async with UnitOfWork(db) as uow:
            connection = await self._get_auth_provider_connection(
                uow.session, readable_id=readable_id, ctx=ctx
            )
            auth_fields_updated = obj_in.auth_fields is not None

            if auth_fields_updated:
                await self._update_auth_credentials(
                    uow=uow,
                    connection=connection,
                    auth_fields=obj_in.auth_fields,
                    ctx=ctx,
                )

            updates: dict[str, str] = {}
            if obj_in.name is not None:
                updates["name"] = obj_in.name
            if obj_in.description is not None:
                updates["description"] = obj_in.description

            if updates:
                await self._connection_repo.update(
                    uow.session,
                    db_obj=connection,
                    obj_in=schemas.ConnectionUpdate(**updates),
                    ctx=ctx,
                    uow=uow,
                )

            if auth_fields_updated:
                connection.modified_at = utc_now_naive()
                if ctx.has_user_context:
                    connection.modified_by_email = ctx.tracking_email
                uow.session.add(connection)

            if updates or auth_fields_updated:
                await uow.session.flush()
                await uow.session.refresh(connection)

            return await self._to_schema(uow.session, connection, ctx)

    async def delete_connection(
        self, db: AsyncSession, *, readable_id: str, ctx: ApiContext
    ) -> schemas.AuthProviderConnection:
        """Delete an auth provider connection."""
        connection = await self._get_auth_provider_connection(db, readable_id=readable_id, ctx=ctx)
        response = await self._to_schema(db, connection, ctx, include_masked_client_id=False)
        await self._connection_repo.remove(db, id=connection.id, ctx=ctx)
        return response

    def _get_registry_entry(self, short_name: str) -> AuthProviderRegistryEntry:
        """Get auth provider registry entry or raise HTTP 404."""
        try:
            return self._registry.get(short_name)
        except KeyError as exc:
            raise HTTPException(
                status_code=404,
                detail=f"Auth provider '{short_name}' not found",
            ) from exc

    def _validate_auth_fields(
        self, entry: AuthProviderRegistryEntry, auth_fields: Optional[dict[str, object]]
    ) -> dict[str, object]:
        """Validate auth fields against provider auth config."""
        if auth_fields is None:
            raise HTTPException(
                status_code=422,
                detail=f"Auth provider {entry.name} requires auth fields.",
            )

        auth_fields_dict = (
            auth_fields.model_dump() if hasattr(auth_fields, "model_dump") else auth_fields
        )

        try:
            auth_config = entry.auth_config_ref(**auth_fields_dict)
            return auth_config.model_dump()
        except ValidationError as exc:
            error_messages: list[str] = []
            for error in exc.errors():
                field = ".".join(str(loc) for loc in error.get("loc", []))
                msg = error.get("msg", "")
                error_messages.append(f"Field '{field}': {msg}")
            error_detail = (
                f"Invalid configuration for {entry.auth_config_ref.__name__}:\n"
                + "\n".join(error_messages)
            )
            raise HTTPException(
                status_code=422,
                detail=f"Invalid auth fields: {error_detail}",
            ) from exc
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f"Invalid auth fields: {exc}") from exc

    async def _validate_credentials(
        self,
        *,
        entry: AuthProviderRegistryEntry,
        validated_auth_fields: dict[str, object],
        validated_provider_config: dict[str, object],
        ctx: ApiContext,
    ) -> None:
        """Validate auth provider credentials by creating a temporary provider instance."""
        try:
            auth_provider_instance = await entry.provider_class_ref.create(
                credentials=validated_auth_fields,
                config=validated_provider_config,
            )
            auth_provider_instance.set_logger(ctx.logger)
            await auth_provider_instance.validate()
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(
                status_code=422,
                detail=f"Failed to validate {entry.short_name} connection: {exc}",
            ) from exc

    async def _update_auth_credentials(
        self,
        *,
        uow: UnitOfWork,
        connection,
        auth_fields: dict[str, object],
        ctx: ApiContext,
    ) -> None:
        """Validate and update encrypted auth fields for a connection."""
        entry = self._get_registry_entry(connection.short_name)
        validated_auth_fields = self._validate_auth_fields(entry, auth_fields)

        if not connection.integration_credential_id:
            raise HTTPException(status_code=500, detail="Connection missing integration credential")

        integration_credential = await self._credential_repo.get(
            uow.session, id=connection.integration_credential_id, ctx=ctx
        )
        if not integration_credential:
            raise HTTPException(status_code=404, detail="Integration credential not found")

        await self._credential_repo.update(
            uow.session,
            db_obj=integration_credential,
            obj_in=schemas.IntegrationCredentialUpdate(
                encrypted_credentials=credentials.encrypt(validated_auth_fields)
            ),
            ctx=ctx,
            uow=uow,
        )
        await uow.session.flush()

    async def _get_masked_client_id(
        self,
        db: AsyncSession,
        *,
        connection: Connection,
        ctx: ApiContext,
    ) -> Optional[str]:
        """Get masked client ID from decrypted auth credentials."""
        try:
            if not connection.integration_credential_id:
                return None

            credential = await self._credential_repo.get(
                db, id=connection.integration_credential_id, ctx=ctx
            )
            if not credential:
                return None

            decrypted = credentials.decrypt(credential.encrypted_credentials)
            client_id = decrypted.get("client_id")
            if not client_id:
                return None

            if len(client_id) <= 15:
                return f"{client_id[:4]}..."
            return f"{client_id[:7]}...{client_id[-4:]}"
        except Exception:
            return None

    async def _get_auth_provider_connection(
        self,
        db: AsyncSession,
        *,
        readable_id: str,
        ctx: ApiContext,
    ) -> Connection:
        """Get validated auth provider connection by readable ID."""
        connection = await self._connection_repo.get_by_readable_id(
            db, readable_id=readable_id, ctx=ctx
        )
        if not connection:
            raise HTTPException(
                status_code=404,
                detail=f"Auth provider connection not found: {readable_id}",
            )
        if connection.integration_type != IntegrationType.AUTH_PROVIDER:
            raise HTTPException(
                status_code=400,
                detail=f"Connection {readable_id} is not an auth provider connection",
            )
        return connection

    async def _to_schema(
        self,
        db: AsyncSession,
        connection: Connection,
        ctx: ApiContext,
        *,
        include_masked_client_id: bool = True,
    ) -> schemas.AuthProviderConnection:
        """Map ORM connection to response schema."""
        masked_client_id = None
        if include_masked_client_id:
            masked_client_id = await self._get_masked_client_id(db, connection=connection, ctx=ctx)

        return schemas.AuthProviderConnection(
            id=connection.id,
            name=connection.name,
            readable_id=connection.readable_id,
            short_name=connection.short_name,
            description=connection.description,
            created_by_email=connection.created_by_email,
            modified_by_email=connection.modified_by_email,
            created_at=connection.created_at,
            modified_at=connection.modified_at,
            masked_client_id=masked_client_id,
        )
