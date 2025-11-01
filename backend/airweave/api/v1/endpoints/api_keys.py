"""API endpoints for managing API keys."""

from uuid import UUID

from fastapi import Body, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.api import deps
from airweave.api.context import ApiContext
from airweave.api.router import TrailingSlashRouter
from airweave.core import credentials
from airweave.core.datetime_utils import utc_now_naive

router = TrailingSlashRouter()


@router.post("/", response_model=schemas.APIKey)
async def create_api_key(
    *,
    db: AsyncSession = Depends(deps.get_db),
    api_key_in: schemas.APIKeyCreate = Body(default_factory=lambda: schemas.APIKeyCreate()),
    ctx: ApiContext = Depends(deps.get_context),
) -> schemas.APIKey:
    """Create a new API key for the current user.

    Returns a temporary plain key for the user to store securely.
    This is not stored in the database.

    Args:
    ----
        db (AsyncSession): The database session.
        api_key_in (schemas.APIKeyCreate): The API key creation data.
        ctx (ApiContext): The current authentication context.

    Returns:
    -------
        schemas.APIKey: The created API key object, including the key.

    """
    api_key_obj = await crud.api_key.create(db=db, obj_in=api_key_in, ctx=ctx)

    # Audit log: API key creation (flows to Azure LAW)
    expiration_days = (api_key_obj.expiration_date - api_key_obj.created_at).days
    audit_logger = ctx.logger.with_context(event_type="api_key_created")
    audit_logger.info(
        f"API key created: {api_key_obj.id} by {api_key_obj.created_by_email} "
        f"for org {ctx.organization.id}, expires in {expiration_days} days "
        f"({api_key_obj.expiration_date.isoformat()})"
    )

    # Decrypt the key for the response
    decrypted_data = credentials.decrypt(api_key_obj.encrypted_key)
    decrypted_key = decrypted_data["key"]

    api_key_data = {
        "id": api_key_obj.id,
        "organization_id": ctx.organization.id,
        "created_at": api_key_obj.created_at,
        "modified_at": api_key_obj.modified_at,
        "last_used_date": None,  # New key has no last used date
        "expiration_date": api_key_obj.expiration_date,
        "created_by_email": api_key_obj.created_by_email,
        "modified_by_email": api_key_obj.modified_by_email,
        "decrypted_key": decrypted_key,
    }

    return schemas.APIKey(**api_key_data)


@router.get("/{id}", response_model=schemas.APIKey)
async def read_api_key(
    *,
    db: AsyncSession = Depends(deps.get_db),
    id: UUID,
    ctx: ApiContext = Depends(deps.get_context),
) -> schemas.APIKey:
    """Retrieve an API key by ID.

    Args:
    ----
        db (AsyncSession): The database session.
        id (UUID): The ID of the API key.
        ctx (ApiContext): The current authentication context.

    Returns:
    -------
        schemas.APIKey: The API key object with decrypted key.

    Raises:
    ------
        HTTPException: If the API key is not found.
    """
    api_key = await crud.api_key.get(db=db, id=id, ctx=ctx)
    # Decrypt the key for the response
    decrypted_data = credentials.decrypt(api_key.encrypted_key)
    decrypted_key = decrypted_data["key"]

    api_key_data = {
        "id": api_key.id,
        "organization_id": ctx.organization.id,
        "created_at": api_key.created_at,
        "modified_at": api_key.modified_at,
        "last_used_date": api_key.last_used_date if hasattr(api_key, "last_used_date") else None,
        "expiration_date": api_key.expiration_date,
        "created_by_email": api_key.created_by_email,
        "modified_by_email": api_key.modified_by_email,
        "decrypted_key": decrypted_key,
    }

    return schemas.APIKey(**api_key_data)


@router.get("/", response_model=list[schemas.APIKey])
async def read_api_keys(
    *,
    db: AsyncSession = Depends(deps.get_db),
    skip: int = Query(0, ge=0, description="Number of API keys to skip for pagination"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of API keys to return"),
    ctx: ApiContext = Depends(deps.get_context),
) -> list[schemas.APIKey]:
    """Retrieve all API keys for the current user.

    Args:
    ----
        db (AsyncSession): The database session.
        skip (int): Number of records to skip for pagination.
        limit (int): Maximum number of records to return.
        ctx (ApiContext): The current authentication context.

    Returns:
    -------
        List[schemas.APIKey]: A list of API keys with decrypted keys.
    """
    api_keys = await crud.api_key.get_multi(db=db, skip=skip, limit=limit, ctx=ctx)

    result = []
    for api_key in api_keys:
        # Decrypt each key
        decrypted_data = credentials.decrypt(api_key.encrypted_key)
        decrypted_key = decrypted_data["key"]

        api_key_data = {
            "id": api_key.id,
            "organization_id": ctx.organization.id,
            "created_at": api_key.created_at,
            "modified_at": api_key.modified_at,
            "last_used_date": (
                api_key.last_used_date if hasattr(api_key, "last_used_date") else None
            ),
            "expiration_date": api_key.expiration_date,
            "created_by_email": api_key.created_by_email,
            "modified_by_email": api_key.modified_by_email,
            "decrypted_key": decrypted_key,
        }
        result.append(schemas.APIKey(**api_key_data))

    return result


@router.post("/{id}/rotate", response_model=schemas.APIKey)
async def rotate_api_key(
    *,
    db: AsyncSession = Depends(deps.get_db),
    id: UUID,
    ctx: ApiContext = Depends(deps.get_context),
) -> schemas.APIKey:
    """Rotate an API key by creating a new one.

    This endpoint creates a new API key with a fresh 90-day expiration.
    The old key remains active until its original expiration date.
    Users can manage multiple keys or delete the old one manually if desired.

    Args:
    ----
        db (AsyncSession): The database session.
        id (UUID): The ID of the API key to rotate.
        ctx (ApiContext): The current authentication context.

    Returns:
    -------
        schemas.APIKey: The newly created API key with decrypted key value.

    Raises:
    ------
        HTTPException: If the API key is not found or user doesn't have access.

    """
    # Verify old key exists and user has access
    old_key = await crud.api_key.get(db=db, id=id, ctx=ctx)
    old_key_schema = schemas.APIKey.model_validate(old_key, from_attributes=True)

    # Create new key with default 90-day expiration
    new_key_obj = await crud.api_key.create(
        db=db,
        obj_in=schemas.APIKeyCreate(),  # Uses default 90 days
        ctx=ctx,
    )

    # Decrypt the new key for the response
    decrypted_data = credentials.decrypt(new_key_obj.encrypted_key)
    decrypted_key = decrypted_data["key"]

    new_key_schema = schemas.APIKey.model_validate(new_key_obj, from_attributes=True)
    new_key_schema.decrypted_key = decrypted_key

    # Audit log: API key rotation (flows to Azure LAW)
    audit_logger = ctx.logger.with_context(event_type="api_key_rotated")
    audit_logger.info(
        f"API key rotated: old={old_key_schema.id}, new={new_key_schema.id} "
        f"by {new_key_schema.created_by_email} for org {ctx.organization.id}, "
        f"new key expires {new_key_schema.expiration_date.isoformat()}"
    )

    return new_key_schema


@router.delete("/", response_model=schemas.APIKey)
async def delete_api_key(
    *,
    db: AsyncSession = Depends(deps.get_db),
    id: UUID,
    ctx: ApiContext = Depends(deps.get_context),
) -> schemas.APIKey:
    """Delete an API key.

    Args:
    ----
        db (AsyncSession): The database session.
        id (UUID): The ID of the API key.
        ctx (ApiContext): The current authentication context.

    Returns:
    -------
        schemas.APIKey: The revoked API key object.

    Raises:
    ------
        HTTPException: If the API key is not found.

    """
    api_key = await crud.api_key.get(db=db, id=id, ctx=ctx)

    # Decrypt the key for the response
    decrypted_data = credentials.decrypt(api_key.encrypted_key)
    decrypted_key = decrypted_data["key"]

    # Create a copy of the data before deletion
    api_key_data = {
        "id": api_key.id,
        "organization_id": ctx.organization.id,
        "created_at": api_key.created_at,
        "modified_at": api_key.modified_at,
        "last_used_date": api_key.last_used_date if hasattr(api_key, "last_used_date") else None,
        "expiration_date": api_key.expiration_date,
        "created_by_email": api_key.created_by_email,
        "modified_by_email": api_key.modified_by_email,
        "decrypted_key": decrypted_key,
    }

    # Audit log: API key deletion (flows to Azure LAW)
    was_expired = api_key.expiration_date < utc_now_naive()
    audit_logger = ctx.logger.with_context(event_type="api_key_deleted")
    audit_logger.info(
        f"API key deleted: {api_key.id} by {ctx.tracking_email} for org {ctx.organization.id} "
        f"(was_expired={was_expired})"
    )

    # Now delete the API key
    await crud.api_key.remove(db=db, id=id, ctx=ctx)

    return schemas.APIKey(**api_key_data)
