"""White label endpoints."""

from uuid import UUID

from fastapi import Body, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.api import deps
from airweave.api.router import TrailingSlashRouter
from airweave.core import credentials
from airweave.core.exceptions import NotFoundException
from airweave.core.logging import logger
from airweave.core.shared_models import ConnectionStatus
from airweave.db.unit_of_work import UnitOfWork
from airweave.models.integration_credential import IntegrationType
from airweave.models.user import User
from airweave.platform.auth.schemas import AuthType
from airweave.platform.auth.services import oauth2_service

router = TrailingSlashRouter()


@router.get("/list", response_model=list[schemas.WhiteLabel])
async def list_white_labels(
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_user),
) -> list[schemas.WhiteLabel]:
    """List all white labels for the current user's organization.

    Args:
    -----
        db: The database session
        current_user: The current user

    Returns:
    --------
        list[schemas.WhiteLabel]: A list of white labels
    """
    white_labels = await crud.white_label.get_all_for_user(db, current_user=current_user)
    return white_labels


@router.post("/", response_model=schemas.WhiteLabel)
async def create_white_label(
    *,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_user),
    white_label_in: schemas.WhiteLabelCreate,
) -> schemas.WhiteLabel:
    """Create new white label integration.

    Args:
    -----
        db: The database session
        current_user: The current user
        white_label_in: The white label to create

    Returns:
    --------
        white_label (schemas.WhiteLabel): The created white label
    """
    white_label = await crud.white_label.create(
        db,
        obj_in=white_label_in,
        current_user=current_user,
    )
    return white_label


@router.get("/{white_label_id}", response_model=schemas.WhiteLabel)
async def get_white_label(
    white_label_id: UUID,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_user),
) -> schemas.WhiteLabel:
    """Get a specific white label integration.

    Args:
    -----
        db: The database session
        white_label_id: The ID of the white label to get
        current_user: The current user

    Returns:
    --------
        white_label (schemas.WhiteLabel): The white label
    """
    white_label = await crud.white_label.get(db, id=white_label_id, current_user=current_user)
    if not white_label:
        raise HTTPException(status_code=404, detail="White label integration not found")
    if white_label.organization_id != current_user.organization_id:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    return white_label


@router.put("/{white_label_id}", response_model=schemas.WhiteLabel)
async def update_white_label(
    *,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_user),
    white_label_id: UUID,
    white_label_in: schemas.WhiteLabelUpdate,
) -> schemas.WhiteLabel:
    """Update a white label integration.

    Args:
    -----
        db: The database session
        current_user: The current user
        white_label_id: The ID of the white label to update
        white_label_in: The white label to update

    Returns:
    --------
        white_label (schemas.WhiteLabel): The updated white label
    """
    # TODO: Check if update is valid (i.e. scopes, source id etc)
    white_label = await crud.white_label.get(db, id=white_label_id)
    if not white_label:
        raise HTTPException(status_code=404, detail="White label integration not found")
    if white_label.organization_id != current_user.organization_id:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    white_label = await crud.white_label.update(
        db,
        db_obj=white_label,
        obj_in=white_label_in,
        current_user=current_user,
    )
    return white_label


@router.delete("/{white_label_id}")
async def delete_white_label(
    white_label_id: UUID,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_user),
) -> schemas.WhiteLabel:
    """Delete a white label integration.

    Args:
    -----
        db: The database session
        current_user: The current user
        white_label_id: The ID of the white label to delete

    Returns:
    --------
        white_label (schemas.WhiteLabel): The deleted white label
    """
    white_label = await crud.white_label.get(db, id=white_label_id, current_user=current_user)
    if not white_label:
        raise HTTPException(status_code=404, detail="White label integration not found")
    if white_label.organization_id != current_user.organization_id:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    return await crud.white_label.remove(db, id=white_label_id)


@router.get("/{white_label_id}/oauth2/auth_url", response_model=str)
async def get_white_label_oauth2_auth_url(
    *,
    db: AsyncSession = Depends(deps.get_db),
    white_label_id: UUID,
    user: User = Depends(deps.get_user),
) -> str:
    """Generate the OAuth2 authorization URL by delegating to oauth2_service.

    Args:
    -----
        db: The database session
        white_label_id: The ID of the white label to get the auth URL for
        user: The current user

    Returns:
    --------
        str: The OAuth2 authorization URL
    """
    white_label = await crud.white_label.get(db, id=white_label_id)
    if not white_label:
        raise HTTPException(status_code=404, detail="White label integration not found")
    if white_label.organization_id != user.organization_id:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    return oauth2_service.generate_auth_url_for_whitelabel(white_label)


@router.post("/{white_label_id}/oauth2/code", response_model=schemas.Connection)
async def exchange_white_label_oauth2_code(
    *,
    white_label_id: UUID,
    code: str = Body(...),
    db: AsyncSession = Depends(deps.get_db),
    user: User = Depends(deps.get_user),
) -> schemas.Connection:
    """Exchange OAuth2 code for tokens and create connection.

    Args:
    -----
        white_label_id: The ID of the white label to exchange the code for
        code: The OAuth2 code
        db: The database session
        user: The current user

    Returns:
    --------
        connection (schemas.Connection): The created connection
    """
    white_label = await crud.white_label.get(db, id=white_label_id)
    if not white_label:
        raise HTTPException(status_code=404, detail="White label integration not found")
    if white_label.organization_id != user.organization_id:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    try:
        token_response = await oauth2_service.exchange_code_for_whitelabel(
            db, code, white_label, user
        )
    except Exception as e:
        logger.error(f"Failed to exchange OAuth2 code for WhiteLabel {white_label.id}: {e}")
        raise HTTPException(status_code=400, detail="Failed to exchange OAuth2 code.") from e

    decrypted_credentials = {
        "access_token": token_response.access_token,
        "refresh_token": token_response.refresh_token,
    }
    encrypted_credentials = credentials.encrypt(decrypted_credentials)

    async with UnitOfWork(db) as uow:
        source = await crud.source.get_by_short_name(uow.session, short_name=white_label.source_id)
        if not source:
            raise NotFoundException(
                f"No Source found matching white_label.source_id='{white_label.source_id}'"
            )

        integration_cred_in = schemas.IntegrationCredentialCreateEncrypted(
            name=f"WhiteLabel {white_label.name} - {user.email}",
            description=f"Credentials for WhiteLabel {white_label.name}",
            integration_short_name=source.short_name,
            integration_type=IntegrationType.SOURCE,
            auth_type=AuthType.oauth2,
            encrypted_credentials=encrypted_credentials,
            auth_config_class=None,
        )
        integration_cred = await crud.integration_credential.create(
            uow.session, obj_in=integration_cred_in, current_user=user, uow=uow
        )
        await uow.session.flush()

        connection_in = schemas.ConnectionCreate(
            name=f"WhiteLabel Connection - {white_label.name}",
            integration_type=IntegrationType.SOURCE,
            status=ConnectionStatus.ACTIVE,
            integration_credential_id=integration_cred.id,
            short_name=source.short_name,
        )
        connection = await crud.connection.create(
            uow.session, obj_in=connection_in, current_user=user, uow=uow
        )

        await uow.commit()
        await uow.session.refresh(connection)

    return connection


@router.get("/{white_label_id}/syncs", response_model=list[schemas.Sync])
async def list_white_label_syncs(
    white_label_id: UUID,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_user),
) -> list[schemas.Sync]:
    """List all syncs for a specific white label.

    Args:
    -----
        white_label_id: The ID of the white label to list syncs for
        db: The database session
        current_user: The current user

    Returns:
    --------
        list[schemas.Sync]: A list of syncs
    """
    result = await crud.sync.get_all_for_white_label(db, white_label_id, current_user)
    return [schemas.Sync.model_validate(sync) for sync in result]
