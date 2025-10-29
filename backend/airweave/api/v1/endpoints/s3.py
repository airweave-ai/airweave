"""S3 destination configuration endpoints."""

from uuid import UUID as PyUUID

from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud
from airweave.api import deps
from airweave.api.context import ApiContext
from airweave.api.rbac import require_org_role
from airweave.api.router import TrailingSlashRouter
from airweave.core.credentials import encrypt
from airweave.core.shared_models import ConnectionStatus, FeatureFlag
from airweave.models.connection import Connection
from airweave.models.integration_credential import IntegrationCredential
from airweave.platform.configs.auth import S3AuthConfig
from airweave.platform.destinations.s3 import S3Destination

router = TrailingSlashRouter()


class S3ConfigRequest(BaseModel):
    """Request to configure S3 destination."""

    aws_access_key_id: str = Field(..., description="AWS access key ID")
    aws_secret_access_key: str = Field(..., description="AWS secret access key")
    bucket_name: str = Field(..., description="S3 bucket name")
    bucket_prefix: str = Field(default="airweave-outbound/", description="Prefix for Airweave data")
    aws_region: str = Field(default="us-east-1", description="AWS region")
    endpoint_url: str | None = Field(default=None, description="Custom S3 endpoint")
    use_ssl: bool = Field(default=True, description="Use SSL/TLS")


class S3ConfigResponse(BaseModel):
    """Response after configuring S3 destination."""

    connection_id: str
    status: str
    message: str


@router.post("/configure", response_model=S3ConfigResponse)
async def configure_s3_destination(
    config: S3ConfigRequest,
    db: AsyncSession = Depends(deps.get_db),
    ctx: ApiContext = Depends(deps.get_context),
) -> S3ConfigResponse:
    """Configure S3 destination for organization.

    Requires S3_DESTINATION feature flag to be enabled for the organization.
    Creates or updates the S3 connection with provided credentials.
    """
    # Check feature flag
    if not ctx.has_feature(FeatureFlag.S3_DESTINATION):
        raise HTTPException(
            status_code=403,
            detail="S3_DESTINATION feature not enabled for this organization. "
            "Contact support to enable this feature.",
        )

    # Validate credentials by testing connection
    try:
        # Build full auth config (contains everything for S3)
        auth_config = S3AuthConfig(**config.model_dump())

        # Test connection using new create() pattern
        _ = await S3Destination.create(
            credentials=auth_config,
            config=None,  # Everything is in credentials
            collection_id=PyUUID("00000000-0000-0000-0000-000000000000"),  # Dummy for test
            organization_id=ctx.organization.id,
            logger=ctx.logger,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"S3 connection test failed: {str(e)}") from e

    # Check if S3 connection already exists
    from sqlalchemy import and_, select

    stmt = select(Connection).where(
        and_(
            Connection.organization_id == ctx.organization.id,
            Connection.short_name == "s3",
            Connection.integration_type == "DESTINATION",
        )
    )
    result = await db.execute(stmt)
    existing_connection = result.scalar_one_or_none()

    if existing_connection:
        # Update existing connection credentials (contains everything)
        if existing_connection.integration_credential_id:
            cred = await crud.integration_credential.get(
                db, existing_connection.integration_credential_id
            )
            if cred:
                # Update encrypted credentials (contains auth + config)
                cred.encrypted_data = encrypt(auth_config.model_dump())
                await db.commit()
                await db.refresh(cred)

        return S3ConfigResponse(
            connection_id=str(existing_connection.id),
            status="updated",
            message="S3 connection updated successfully",
        )

    # Create new S3 connection
    encrypted_creds = encrypt(auth_config.model_dump())  # Contains everything
    credential = IntegrationCredential(
        organization_id=ctx.organization.id,
        name="S3 Event Stream Credentials",
        integration_short_name="s3",
        description="S3-compatible storage for event streaming",
        integration_type="DESTINATION",
        authentication_method="direct",
        encrypted_credentials=encrypted_creds,
        auth_config_class="S3AuthConfig",
        created_by_email=ctx.user.email if ctx.user else None,
        modified_by_email=ctx.user.email if ctx.user else None,
    )
    db.add(credential)
    await db.flush()

    # Create connection
    connection = Connection(
        organization_id=ctx.organization.id,
        name="S3 Event Stream",
        readable_id=f"s3-event-stream-{ctx.organization.id}",
        short_name="s3",
        integration_type="DESTINATION",
        status=ConnectionStatus.ACTIVE,
        integration_credential_id=credential.id,
        created_by_email=ctx.user.email if ctx.user else None,
        modified_by_email=ctx.user.email if ctx.user else None,
    )
    db.add(connection)
    await db.commit()
    await db.refresh(connection)

    ctx.logger.info(
        f"S3 destination configured for organization {ctx.organization.id}: "
        f"bucket={config.bucket_name}"
    )

    return S3ConfigResponse(
        connection_id=str(connection.id),
        status="created",
        message="S3 connection created successfully. All future syncs will include S3.",
    )


@router.post("/test", response_model=dict)
async def test_s3_connection(
    config: S3ConfigRequest,
    ctx: ApiContext = Depends(deps.get_context),
) -> dict:
    """Test S3 connection without saving credentials.

    Validates credentials by attempting to connect to the bucket.
    """
    # Check feature flag
    if not ctx.has_feature(FeatureFlag.S3_DESTINATION):
        raise HTTPException(
            status_code=403,
            detail="S3_DESTINATION feature not enabled for this organization",
        )

    try:
        # Build full auth config (contains everything for S3)
        auth_config = S3AuthConfig(**config.model_dump())

        # Test connection using new create() pattern
        _ = await S3Destination.create(
            credentials=auth_config,
            config=None,  # Everything is in credentials
            collection_id=PyUUID("00000000-0000-0000-0000-000000000000"),  # Dummy for test
            organization_id=ctx.organization.id,
            logger=ctx.logger,
        )

        return {
            "status": "success",
            "message": f"Successfully connected to S3 bucket: {config.bucket_name}",
            "bucket_name": config.bucket_name,
            "endpoint": config.endpoint_url or "AWS S3",
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Connection test failed: {str(e)}") from e


@router.delete("/configure")
async def delete_s3_configuration(
    db: AsyncSession = Depends(deps.get_db),
    ctx: ApiContext = Depends(deps.get_context),
) -> dict:
    """Remove S3 configuration for organization.

    This operation requires admin or owner role within the organization.

    Deletes the S3 connection. Future syncs will only use Qdrant.

    Raises:
    -------
        HTTPException: If user lacks admin privileges (403) or S3 connection not found (404).
    """
    # Validate user has admin role
    require_org_role(ctx, min_role="admin")

    from sqlalchemy import and_, select

    # Find S3 connection
    stmt = select(Connection).where(
        and_(
            Connection.organization_id == ctx.organization.id,
            Connection.short_name == "s3",
            Connection.integration_type == "DESTINATION",
        )
    )
    result = await db.execute(stmt)
    connection = result.scalar_one_or_none()

    if not connection:
        raise HTTPException(status_code=404, detail="S3 connection not found")

    # Delete credentials if they exist
    if connection.integration_credential_id:
        cred = await crud.integration_credential.get(db, connection.integration_credential_id)
        if cred:
            await db.delete(cred)

    # Delete connection
    await db.delete(connection)
    await db.commit()

    ctx.logger.info(f"S3 destination removed for organization {ctx.organization.id}")

    return {"status": "success", "message": "S3 configuration removed"}


@router.get("/s3/status")
async def get_s3_status(
    db: AsyncSession = Depends(deps.get_db),
    ctx: ApiContext = Depends(deps.get_context),
) -> dict:
    """Get S3 configuration status for organization."""
    from sqlalchemy import and_, select

    # Check feature flag
    has_feature = ctx.has_feature(FeatureFlag.S3_DESTINATION)

    if not has_feature:
        return {
            "feature_enabled": False,
            "configured": False,
            "message": "S3_DESTINATION feature not enabled",
        }

    # Find S3 connection
    stmt = select(Connection).where(
        and_(
            Connection.organization_id == ctx.organization.id,
            Connection.short_name == "s3",
            Connection.integration_type == "DESTINATION",
        )
    )
    result = await db.execute(stmt)
    connection = result.scalar_one_or_none()

    if not connection:
        return {
            "feature_enabled": True,
            "configured": False,
            "message": "S3 connection not configured. Use POST /s3/configure to set up.",
        }

    # Load bucket name (don't expose credentials)
    bucket_name = None
    if connection.integration_credential_id:
        cred = await crud.integration_credential.get(db, connection.integration_credential_id)
        if cred:
            from airweave.core.credentials import decrypt

            try:
                decrypted = decrypt(cred.encrypted_data)
                bucket_name = decrypted.get("bucket_name")
            except Exception:
                pass

    return {
        "feature_enabled": True,
        "configured": True,
        "connection_id": str(connection.id),
        "bucket_name": bucket_name,
        "status": connection.status,
        "created_at": connection.created_at.isoformat() if connection.created_at else None,
    }
