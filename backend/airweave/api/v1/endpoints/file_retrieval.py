"""API endpoints for file downloads from storage."""

from typing import List
from zipfile import ZipFile

from fastapi import Depends, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud
from airweave.api import deps
from airweave.api.context import ApiContext
from airweave.api.router import TrailingSlashRouter
from airweave.platform.storage import sync_file_manager

router = TrailingSlashRouter()


async def verify_picnic_health_access(
    ctx: ApiContext,
    db: AsyncSession,
) -> None:
    """Verify that the request is from Picnic Health organization.

    Raises:
        HTTPException: If not from Picnic Health
    """
    # Picnic Health organization ID
    PICNIC_HEALTH_ORG_ID = "9878d9b4-0fb9-4401-b2b3-15420da4eda3"

    # Check if the request is from Picnic Health organization by ID
    if str(ctx.organization.id) != PICNIC_HEALTH_ORG_ID:
        # Get the organization details for logging
        organization = await crud.organization.get(db=db, id=ctx.organization.id, ctx=ctx)

        ctx.logger.warning(
            f"File access denied for organization: "
            f"{organization.name if organization else 'Unknown'} "
            f"(ID: {ctx.organization.id})",
            extra={
                "organization_id": ctx.organization.id,
                "organization_name": organization.name if organization else None,
                "auth_method": ctx.auth_method,
                "expected_org_id": PICNIC_HEALTH_ORG_ID,
            },
        )
        raise HTTPException(
            status_code=403, detail="Access restricted to Picnic Health organization members"
        )


@router.get("/{entity_id}", response_class=FileResponse)
async def download_file(
    *,
    entity_id: str,
    ctx: ApiContext = Depends(deps.get_context),
    db: AsyncSession = Depends(deps.get_db),
) -> FileResponse:
    """Download a file by entity ID.

    Args:
        entity_id: The entity ID
        ctx: The current authentication context
        db: Database session

    Returns:
        FileResponse: The file content

    Raises:
        HTTPException: If file not found or invalid entity ID
    """
    # Verify Picnic Health access
    await verify_picnic_health_access(ctx, db)

    try:
        # Download to temp file
        content, file_path = await sync_file_manager.download_ctti_file(
            ctx.logger,
            entity_id,
            output_path=f"/tmp/{entity_id.replace(':', '_').replace('/', '_')}.md",
        )

        if content is None:
            raise HTTPException(
                status_code=404, detail=f"File not found for entity ID: {entity_id}"
            )

        # Extract ID suffix from entity_id for filename
        file_suffix = entity_id.split(":")[-1] if ":" in entity_id else entity_id

        return FileResponse(
            path=file_path,
            filename=f"{file_suffix}.md",
            media_type="text/markdown",
            headers={"Content-Disposition": f'attachment; filename="{file_suffix}.md"'},
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        ctx.logger.error(f"Error downloading file: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.get("/{entity_id}/content")
async def get_file_content(
    *,
    entity_id: str,
    ctx: ApiContext = Depends(deps.get_context),
    db: AsyncSession = Depends(deps.get_db),
) -> dict:
    """Get file content as JSON response.

    Args:
        entity_id: The entity ID
        ctx: The current authentication context
        db: Database session

    Returns:
        dict: JSON response with the file content

    Raises:
        HTTPException: If file not found or invalid entity ID
    """
    # Verify Picnic Health access
    await verify_picnic_health_access(ctx, db)

    try:
        content = await sync_file_manager.get_ctti_file_content(ctx.logger, entity_id)

        if content is None:
            raise HTTPException(
                status_code=404, detail=f"File not found for entity ID: {entity_id}"
            )

        # Extract ID suffix from entity_id
        id_suffix = entity_id.split(":")[-1] if ":" in entity_id else entity_id

        return {
            "entity_id": entity_id,
            "id": id_suffix,
            "content": content,
            "content_length": len(content),
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except HTTPException:
        raise
    except Exception as e:
        ctx.logger.error(f"Error getting file content: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.post("/batch-download", response_class=StreamingResponse)
async def download_files_batch(
    *,
    entity_ids: List[str],
    ctx: ApiContext = Depends(deps.get_context),
    db: AsyncSession = Depends(deps.get_db),
) -> StreamingResponse:
    """Download multiple files as a ZIP archive.

    Args:
        entity_ids: List of entity IDs to download
        ctx: The current authentication context
        db: Database session

    Returns:
        StreamingResponse: ZIP file containing all requested files

    Raises:
        HTTPException: If no valid files found
    """
    # Verify Picnic Health access
    await verify_picnic_health_access(ctx, db)

    if not entity_ids:
        raise HTTPException(status_code=400, detail="No entity IDs provided")

    if len(entity_ids) > 100:
        raise HTTPException(status_code=400, detail="Maximum 100 files can be downloaded at once")

    try:
        # Download all files
        results = await sync_file_manager.download_ctti_files_batch(
            ctx.logger, entity_ids, continue_on_error=True
        )

        # Filter successful downloads
        successful_downloads = {
            entity_id: content for entity_id, (content, _) in results.items() if content is not None
        }

        if not successful_downloads:
            raise HTTPException(
                status_code=404, detail="No valid files found for the provided entity IDs"
            )

        # Create ZIP file in memory
        import io

        zip_buffer = io.BytesIO()

        with ZipFile(zip_buffer, "w") as zip_file:
            for entity_id, content in successful_downloads.items():
                # Extract ID suffix for filename
                file_suffix = entity_id.split(":")[-1] if ":" in entity_id else entity_id
                zip_file.writestr(f"{file_suffix}.md", content)

        # Reset buffer position
        zip_buffer.seek(0)

        # Log summary
        ctx.logger.info(
            f"Batch download completed: {len(successful_downloads)}/{len(entity_ids)} files",
            extra={
                "requested": len(entity_ids),
                "successful": len(successful_downloads),
                "failed": len(entity_ids) - len(successful_downloads),
            },
        )

        return StreamingResponse(
            io.BytesIO(zip_buffer.read()),
            media_type="application/zip",
            headers={
                "Content-Disposition": (
                    f'attachment; filename="files_{len(successful_downloads)}.zip"'
                )
            },
        )

    except Exception as e:
        ctx.logger.error(f"Error in batch download: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.get("/", response_model=dict)
async def check_files_exist(
    *,
    entity_ids: List[str] = Query(..., description="List of entity IDs to check"),
    ctx: ApiContext = Depends(deps.get_context),
    db: AsyncSession = Depends(deps.get_db),
) -> dict:
    """Check which files exist in storage.

    Args:
        entity_ids: List of entity IDs to check
        ctx: The current authentication context
        db: Database session

    Returns:
        dict: Dictionary with entity_ids as keys and existence status as values
    """
    # Verify Picnic Health access
    await verify_picnic_health_access(ctx, db)

    if not entity_ids:
        raise HTTPException(status_code=400, detail="No entity IDs provided")

    if len(entity_ids) > 1000:
        raise HTTPException(
            status_code=400, detail="Maximum 1000 entity IDs can be checked at once"
        )

    results = {}

    for entity_id in entity_ids:
        try:
            exists = await sync_file_manager.check_ctti_file_exists(ctx.logger, entity_id)
            results[entity_id] = exists
        except Exception as e:
            ctx.logger.warning(f"Error checking file {entity_id}: {e}")
            results[entity_id] = False

    return {
        "results": results,
        "total": len(entity_ids),
        "found": sum(1 for exists in results.values() if exists),
        "not_found": sum(1 for exists in results.values() if not exists),
    }
