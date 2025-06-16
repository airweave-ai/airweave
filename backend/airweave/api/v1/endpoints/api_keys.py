"""API endpoints for managing API keys."""

from uuid import UUID
import logging

from fastapi import Body, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.api import deps
from airweave.api.router import TrailingSlashRouter
from airweave.core import credentials

router = TrailingSlashRouter()


@router.post("/", response_model=schemas.APIKey)
async def create_api_key(
    *,
    db: AsyncSession = Depends(deps.get_db),
    api_key_in: schemas.APIKeyCreate = Body({}),  # Default to empty dict if not provided
    user: schemas.User = Depends(deps.get_user),
) -> schemas.APIKey:
    """Create a new API key for the current user.

    Returns a temporary plain key for the user to store securely.
    This is not stored in the database.

    Args:
    ----
        db (AsyncSession): The database session.
        api_key_in (schemas.APIKeyCreate): The API key creation data.
        user (schemas.User): The current user.

    Returns:
    -------
        schemas.APIKey: The created API key object, including the key.

    """
    api_key_obj = await crud.api_key.create_with_user(db=db, obj_in=api_key_in, current_user=user)

    # Decrypt the key for the response
    decrypted_data = credentials.decrypt(api_key_obj.encrypted_key)
    decrypted_key = decrypted_data["key"]

    api_key_data = {
        "id": api_key_obj.id,
        "organization": user.organization_id,  # Use the user's organization_id
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
    user: schemas.User = Depends(deps.get_user),
) -> schemas.APIKey:
    """Retrieve an API key by ID.

    Args:
    ----
        db (AsyncSession): The database session.
        id (UUID): The ID of the API key.
        user (schemas.User): The current user.

    Returns:
    -------
        schemas.APIKey: The API key object with decrypted key.

    Raises:
    ------
        HTTPException: If the API key is not found.
    """
    api_key = await crud.api_key.get(db=db, id=id, current_user=user)
    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")

    # Decrypt the key for the response
    decrypted_data = credentials.decrypt(api_key.encrypted_key)
    decrypted_key = decrypted_data["key"]

    api_key_data = {
        "id": api_key.id,
        "organization": user.organization_id,
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
    skip: int = 0,
    limit: int = 100,
    user: schemas.User = Depends(deps.get_user),
) -> list[schemas.APIKey]:
    """Retrieve all API keys for the current user.

    Args:
    ----
        db (AsyncSession): The database session.
        skip (int): Number of records to skip for pagination.
        limit (int): Maximum number of records to return.
        user (schemas.User): The current user.

    Returns:
    -------
        List[schemas.APIKey]: A list of API keys with decrypted keys.
    """
    api_keys = await crud.api_key.get_all_for_user(db=db, skip=skip, limit=limit, current_user=user)
    
    result = []
    invalid_keys = []  # New: Track invalid keys
    for api_key in api_keys:
        try:
            decrypted_data = credentials.decrypt(api_key.encrypted_key)
            decrypted_key = decrypted_data["key"]
        except Exception as e:
            invalid_keys.append(api_key.id)  # New: Record invalid key ID
            logging.warning(f"Failed to decrypt API key {api_key.id}: {e}")
            continue  # Skip this key but continue processing others

        api_key_data = {
            "id": api_key.id,
            "organization": user.organization_id,
            "created_at": api_key.created_at,
            "modified_at": api_key.modified_at,
            "last_used_date": api_key.last_used_date
            if hasattr(api_key, "last_used_date")
            else None,
            "expiration_date": api_key.expiration_date,
            "created_by_email": api_key.created_by_email,
            "modified_by_email": api_key.modified_by_email,
            "decrypted_key": decrypted_key,
        }
        result.append(schemas.APIKey(**api_key_data))

    # New: Log summary of invalid keys
    if invalid_keys:
        logging.warning(f"Skipped {len(invalid_keys)} invalid API keys: {', '.join(str(id) for id in invalid_keys)}")

    return result  # Will return empty list if all keys are invalid


@router.delete("/", response_model=schemas.APIKey)
async def delete_api_key(
    *,
    db: AsyncSession = Depends(deps.get_db),
    id: UUID,
    user: schemas.User = Depends(deps.get_user),
) -> schemas.APIKey:
    """Delete an API key.

    Args:
    ----
        db (AsyncSession): The database session.
        id (UUID): The ID of the API key.
        user (schemas.User): The current user.

    Returns:
    -------
        schemas.APIKey: The revoked API key object.

    Raises:
    ------
        HTTPException: If the API key is not found.

    """
    api_key = await crud.api_key.get(db=db, id=id, current_user=user)
    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")

    # Decrypt the key for the response
    decrypted_data = credentials.decrypt(api_key.encrypted_key)
    decrypted_key = decrypted_data["key"]

    # Create a copy of the data before deletion
    api_key_data = {
        "id": api_key.id,
        "organization": user.organization_id,
        "created_at": api_key.created_at,
        "modified_at": api_key.modified_at,
        "last_used_date": api_key.last_used_date if hasattr(api_key, "last_used_date") else None,
        "expiration_date": api_key.expiration_date,
        "created_by_email": api_key.created_by_email,
        "modified_by_email": api_key.modified_by_email,
        "decrypted_key": decrypted_key,
    }

    # Now delete the API key
    await crud.api_key.remove(db=db, id=id, current_user=user)

    return schemas.APIKey(**api_key_data)
