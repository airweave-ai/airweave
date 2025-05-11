"""API endpoints for performing searches."""

from enum import Enum
from uuid import UUID

from fastapi import Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import schemas
from airweave.api import deps
from airweave.api.router import TrailingSlashRouter
from airweave.core.chat_service import chat_service
from airweave.core.search_service import search_service

router = TrailingSlashRouter()


class ResponseType(str, Enum):
    """Response type for search results."""

    RAW = "raw"
    COMPLETION = "completion"


@router.get("/")
async def search(
    *,
    db: AsyncSession = Depends(deps.get_db),
    sync_id: UUID = Query(..., description="The ID of the sync to search within"),
    query: str = Query(..., description="Search query text"),
    response_type: ResponseType = Query(
        ResponseType.RAW, description="Type of response: raw search results or AI completion"
    ),
    user: schemas.User = Depends(deps.get_user),
) -> dict:
    """Search for documents within a specific sync.

    Args:
    -----
        db: The database session
        sync_id: The ID of the sync to search within
        query: The search query text
        response_type: Type of response (raw results or AI completion)
        user: The current user

    Returns:
    --------
        dict: A dictionary containing search results or AI completion
    """
    results = await search_service.search(
        db=db,
        query=query,
        sync_id=sync_id,
        current_user=user,
    )

    if response_type == ResponseType.RAW:
        return {"results": results, "response_type": "raw"}

    # For completion, use chat service to summarize and answer
    if not results:
        return {
            "results": [],
            "completion": "No results found for your query.",
            "response_type": "completion",
        }

    # Extract vector data from each result's payload
    vector_data = []
    for result in results:
        if isinstance(result, dict) and "payload" in result:
            if "vector" in result["payload"]:
                vector_data.append(str(result["payload"]["vector"]))
                # Remove vector from payload to avoid sending large data back
                result["payload"].pop("vector", None)

            # Also remove download URLs from payload
            if "download_url" in result["payload"]:
                result["payload"].pop("download_url", None)

    # Prepare messages for completion
    messages = [
        {"role": "system", "content": chat_service.CONTEXT_PROMPT.format(context=str(results))},
        {"role": "user", "content": query},
    ]

    # Generate completion
    model = chat_service.DEFAULT_MODEL
    model_settings = chat_service.DEFAULT_MODEL_SETTINGS.copy()

    # Remove streaming setting if present
    if "stream" in model_settings:
        model_settings.pop("stream")

    try:
        response = await chat_service.client.chat.completions.create(
            model=model, messages=messages, **model_settings
        )

        completion = (
            response.choices[0].message.content
            if response.choices
            else "Unable to generate completion."
        )
    except Exception as e:
        completion = f"Error generating completion: {str(e)}"

    return {
        "completion": completion,
        "results": results,
        "response_type": "completion",
    }
