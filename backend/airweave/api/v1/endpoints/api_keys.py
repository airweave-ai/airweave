"""API endpoints for managing API keys."""

from typing import cast
from uuid import UUID

from fastapi import Body, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.api import deps
from airweave.api.context import ApiContext
from airweave.api.inject import Inject
from airweave.api.router import TrailingSlashRouter
from airweave.core import credentials
from airweave.core.datetime_utils import utc_now_naive
from airweave.core.protocols.cache import ContextCache
from airweave.db.unit_of_work import UnitOfWork
from airweave.domains.organizations import logic

router = TrailingSlashRouter()


@router.post("/", response_model=schemas.APIKey)
async def create_api_key(
    *,
    db: AsyncSession = Depends(deps.get_db),
    api_key_in: schemas.APIKeyCreate = Body(default_factory=lambda: schemas.APIKeyCreate()),
    ctx: ApiContext = deps.require_org_role(logic.can_manage_api_keys, block_api_key_auth=True),
) -> schemas.APIKey:
    """Create a new API key for the current user.

    Returns a temporary plain key for the user to store securely.
    This is the only time the full key is visible.

    Args:
    ----
        db (AsyncSession): The database session.
        api_key_in (schemas.APIKeyCreate): The API key creation data.
        ctx (ApiContext): The current authentication context.

    Returns:
    -------
        schemas.APIKey: The created API key object, including the
            decrypted key (visible only on creation).

    """
    api_key_obj = await crud.api_key.create(db=db, obj_in=api_key_in, ctx=ctx)

    expiration_days = (api_key_obj.expiration_date - api_key_obj.created_at).days
    audit_logger = ctx.logger.with_context(event_type="api_key_created")
    audit_logger.info(
        f"API key created: {api_key_obj.id} by {api_key_obj.created_by_email} "
        f"for org {ctx.organization.id}, expires in {expiration_days} days "
        f"({api_key_obj.expiration_date.isoformat()})"
    )

    decrypted_data = credentials.decrypt(api_key_obj.encrypted_key)
    decrypted_key = decrypted_data["key"]

    result = schemas.APIKey.model_validate(api_key_obj, from_attributes=True)
    result.decrypted_key = decrypted_key
    return result


@router.get("/{id}", response_model=schemas.APIKey)
async def read_api_key(
    *,
    db: AsyncSession = Depends(deps.get_db),
    id: UUID,
    ctx: ApiContext = deps.require_org_role(logic.can_manage_api_keys, block_api_key_auth=True),
) -> schemas.APIKey:
    """Retrieve an API key by ID.

    The decrypted key is NOT returned — only the key_prefix is visible.

    Args:
    ----
        db (AsyncSession): The database session.
        id (UUID): The ID of the API key.
        ctx (ApiContext): The current authentication context.

    Returns:
    -------
        schemas.APIKey: The API key object (without decrypted key).

    Raises:
    ------
        NotFoundException: If the API key is not found.

    """
    api_key = await crud.api_key.get(db=db, id=id, ctx=ctx)
    result = schemas.APIKey.model_validate(api_key, from_attributes=True)
    result.decrypted_key = None
    return result


@router.get("/", response_model=list[schemas.APIKey])
async def read_api_keys(
    *,
    db: AsyncSession = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    ctx: ApiContext = deps.require_org_role(logic.can_manage_api_keys, block_api_key_auth=True),
) -> list[schemas.APIKey]:
    """Retrieve all API keys for the current user.

    Decrypted keys are NOT returned — only the key_prefix is visible.

    Args:
    ----
        db (AsyncSession): The database session.
        skip (int): Number of records to skip for pagination.
        limit (int): Maximum number of records to return.
        ctx (ApiContext): The current authentication context.

    Returns:
    -------
        list[schemas.APIKey]: A list of API keys (without decrypted
            keys).

    """
    api_keys = await crud.api_key.get_multi(db=db, skip=skip, limit=limit, ctx=ctx)
    # Audit log: API keys listed (flows to Azure LAW)
    audit_logger = ctx.logger.with_context(event_type="api_keys_listed")
    audit_logger.info(
        f"API keys listed ({len(api_keys)} keys) by {ctx.tracking_email} "
        f"for org {ctx.organization.id}"
    )

    result = []
    for api_key in api_keys:
        schema = schemas.APIKey.model_validate(api_key, from_attributes=True)
        schema.decrypted_key = None
        result.append(schema)

    return result


@router.post("/{id}/rotate", response_model=schemas.APIKey)
async def rotate_api_key(
    *,
    db: AsyncSession = Depends(deps.get_db),
    id: UUID,
    ctx: ApiContext = deps.require_org_role(logic.can_manage_api_keys, block_api_key_auth=True),
    cache: ContextCache = Inject(ContextCache),
) -> schemas.APIKey:
    """Rotate an API key: create a new one and immediately revoke the old one.

    The new key inherits the original lifetime of the old key (i.e.
    the duration from ``created_at`` to ``expiration_date``), clamped
    to [1, 180] days.

    Args:
    ----
        db (AsyncSession): The database session.
        id (UUID): The ID of the API key to rotate.
        ctx (ApiContext): The current authentication context.
        cache (ContextCache): The cache for invalidating the old key.

    Returns:
    -------
        schemas.APIKey: The newly created API key with decrypted key.

    Raises:
    ------
        NotFoundException: If the API key is not found.

    """
    old_key = await crud.api_key.get(db=db, id=id, ctx=ctx)

    # Capture attributes before create() expires the ORM instance
    old_key_id = cast(UUID, old_key.id)
    old_key_encrypted = old_key.encrypted_key
    old_key_description = old_key.description
    original_days = (old_key.expiration_date - old_key.created_at).days

    new_key_create = schemas.APIKeyCreate(
        expiration_days=max(1, min(original_days, 180)),
        description=old_key_description,
    )

    async with UnitOfWork(db) as uow:
        new_key_obj = await crud.api_key.create(
            db=db,
            obj_in=new_key_create,
            ctx=ctx,
            uow=uow,
        )
        await crud.api_key.revoke(
            db=db,
            api_key_id=old_key_id,
            uow=uow,
        )

    # UoW commit expires ORM instances — refresh before access
    await db.refresh(new_key_obj)

    # Invalidate old key's cache entry
    try:
        old_decrypted = credentials.decrypt(old_key_encrypted)
        old_plaintext = old_decrypted["key"]
        await cache.invalidate_api_key(old_plaintext)
    except Exception:
        pass  # Let TTL expire it

    decrypted_data = credentials.decrypt(new_key_obj.encrypted_key)
    decrypted_key = decrypted_data["key"]

    new_key_schema = schemas.APIKey.model_validate(new_key_obj, from_attributes=True)
    new_key_schema.decrypted_key = decrypted_key

    audit_logger = ctx.logger.with_context(event_type="api_key_rotated")
    audit_logger.info(
        f"API key rotated: old={old_key_id}, new={new_key_obj.id} "
        f"by {new_key_schema.created_by_email} for org {ctx.organization.id}, "
        f"new key expires {new_key_schema.expiration_date.isoformat()}"
    )

    return new_key_schema


@router.post("/{id}/revoke", response_model=schemas.APIKey)
async def revoke_api_key(
    *,
    db: AsyncSession = Depends(deps.get_db),
    id: UUID,
    ctx: ApiContext = deps.require_org_role(logic.can_manage_api_keys, block_api_key_auth=True),
    cache: ContextCache = Inject(ContextCache),
) -> schemas.APIKey:
    """Explicitly revoke an API key without creating a replacement.

    Use this for suspected compromise. The key is immediately invalid.

    Args:
    ----
        db (AsyncSession): The database session.
        id (UUID): The ID of the API key to revoke.
        ctx (ApiContext): The current authentication context.
        cache (ContextCache): The cache for invalidating the key.

    Returns:
    -------
        schemas.APIKey: The revoked API key object.

    Raises:
    ------
        NotFoundException: If the API key is not found.
        ConflictException: If the key is already revoked or expired.

    """
    api_key = await crud.api_key.get(db=db, id=id, ctx=ctx)

    # Capture before revoke() commits and expires the ORM instance
    api_key_id = cast(UUID, api_key.id)
    api_key_encrypted = api_key.encrypted_key

    revoked = await crud.api_key.revoke(db=db, api_key_id=api_key_id)

    # Invalidate cache
    try:
        decrypted_data = credentials.decrypt(api_key_encrypted)
        plaintext_key = decrypted_data["key"]
        await cache.invalidate_api_key(plaintext_key)
    except Exception:
        pass  # Best-effort; cache TTL will expire the entry

    audit_logger = ctx.logger.with_context(event_type="api_key_revoked")
    audit_logger.info(
        f"API key revoked: {api_key_id} by {ctx.tracking_email} for org {ctx.organization.id}"
    )

    result = schemas.APIKey.model_validate(revoked, from_attributes=True)
    result.decrypted_key = None
    return result


@router.delete("/", response_model=schemas.APIKey)
async def delete_api_key(
    *,
    db: AsyncSession = Depends(deps.get_db),
    id: UUID,
    ctx: ApiContext = deps.require_org_role(logic.can_manage_api_keys, block_api_key_auth=True),
    cache: ContextCache = Inject(ContextCache),
) -> schemas.APIKey:
    """Delete an API key.

    Args:
    ----
        db (AsyncSession): The database session.
        id (UUID): The ID of the API key.
        ctx (ApiContext): The current authentication context.
        cache (ContextCache): The cache for invalidating the key.

    Returns:
    -------
        schemas.APIKey: The deleted API key object.

    Raises:
    ------
        NotFoundException: If the API key is not found.

    """
    api_key = await crud.api_key.get(db=db, id=id, ctx=ctx)

    # Build response before deletion
    result = schemas.APIKey.model_validate(api_key, from_attributes=True)
    result.decrypted_key = None

    # Decrypt internally for cache invalidation (never exposed to client)
    plaintext_key = None
    try:
        decrypted_data = credentials.decrypt(api_key.encrypted_key)
        plaintext_key = decrypted_data["key"]
    except Exception:
        pass  # Decryption may fail for corrupted keys; proceed with deletion

    was_expired = api_key.expiration_date < utc_now_naive()
    audit_logger = ctx.logger.with_context(event_type="api_key_deleted")
    audit_logger.info(
        f"API key deleted: {api_key.id} by {ctx.tracking_email} for org {ctx.organization.id} "
        f"(was_expired={was_expired})"
    )

    if plaintext_key:
        await cache.invalidate_api_key(plaintext_key)
    await crud.api_key.remove(db=db, id=id, ctx=ctx)

    return result


@router.get("/{id}/usage", response_model=list[schemas.APIKeyUsageLogEntry])
async def read_api_key_usage(
    *,
    db: AsyncSession = Depends(deps.get_db),
    id: UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    ctx: ApiContext = deps.require_org_role(logic.can_manage_api_keys, block_api_key_auth=True),
) -> list[schemas.APIKeyUsageLogEntry]:
    """Get paginated usage log for an API key.

    Args:
    ----
        db (AsyncSession): The database session.
        id (UUID): The ID of the API key.
        skip (int): Number of records to skip for pagination.
        limit (int): Maximum number of records to return (1–200).
        ctx (ApiContext): The current authentication context.

    Returns:
    -------
        list[schemas.APIKeyUsageLogEntry]: Paginated usage log entries,
            most recent first.

    """
    await crud.api_key.get(db=db, id=id, ctx=ctx)

    log_entries = await crud.api_key.get_usage_log(db, api_key_id=id, skip=skip, limit=limit)
    return [
        schemas.APIKeyUsageLogEntry.model_validate(entry, from_attributes=True)
        for entry in log_entries
    ]


@router.get("/{id}/usage/stats", response_model=schemas.APIKeyUsageStats)
async def read_api_key_usage_stats(
    *,
    db: AsyncSession = Depends(deps.get_db),
    id: UUID,
    ctx: ApiContext = deps.require_org_role(logic.can_manage_api_keys, block_api_key_auth=True),
) -> schemas.APIKeyUsageStats:
    """Get aggregated usage statistics for an API key.

    Args:
    ----
        db (AsyncSession): The database session.
        id (UUID): The ID of the API key.
        ctx (ApiContext): The current authentication context.

    Returns:
    -------
        schemas.APIKeyUsageStats: Aggregate usage statistics including
            total requests, unique IPs, and unique endpoints.

    """
    await crud.api_key.get(db=db, id=id, ctx=ctx)

    return await crud.api_key.get_usage_stats(db, api_key_id=id)
