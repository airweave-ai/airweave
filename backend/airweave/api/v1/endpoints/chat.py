"""Chat endpoints."""

from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.api.deps import get_db, get_user
from airweave.api.router import TrailingSlashRouter
from airweave.core.chat_service import chat_service
from airweave.core.config import settings
from airweave.core.logging import logger

router = TrailingSlashRouter()


# Add this function to support token in query params for SSE
async def get_user_from_token_param(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> schemas.User:
    """Get user from token query parameter for SSE endpoints.

    Args:
        request: The request object.
        db: The database session.

    Returns:
        The authenticated user.

    Raises:
        HTTPException: If authentication fails.
    """
    if settings.AUTH_ENABLED:
        token = request.query_params.get("token")
        if not token:
            logger.warning("SSE connection attempt without token")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing authentication token"
            )

        # Use the same auth logic from get_user but with the token from query param
        from airweave.api.deps import get_user_from_token

        user = await get_user_from_token(token, db)
        if not user:
            logger.warning(f"SSE connection with invalid token: {token[:10]}...")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication token"
            )

        logger.info(f"SSE connection authenticated for user: {user.id}")
        return user
    else:
        return await get_user(db=db)


@router.get("/openai_key_set", response_model=bool)
async def openai_key_set(
    *,
    db: AsyncSession = Depends(get_db),
    user: schemas.User = Depends(get_user),
) -> bool:
    """Check if the OpenAI API key is set for the current user.

    Args:
    ----
        db: The database session.
        user: The current user.

    Returns:
    -------
        bool: True if the OpenAI API key is set, False otherwise.
    """
    return settings.OPENAI_API_KEY is not None


@router.post("/", response_model=schemas.Chat)
async def create_chat(
    *,
    db: AsyncSession = Depends(get_db),
    chat_in: schemas.ChatCreate,
    user: schemas.User = Depends(get_user),
) -> schemas.Chat:
    """Create a new chat.

    Args:
    ----
        db: The database session.
        chat_in: The chat creation data.
        user: The current user.

    Returns:
    -------
        schemas.Chat: The created chat.
    """
    chat = await crud.chat.create(db=db, obj_in=chat_in, current_user=user)
    return chat


@router.get("/", response_model=list[schemas.Chat])
async def list_chats(
    *,
    db: AsyncSession = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    user: schemas.User = Depends(get_user),
) -> list[schemas.Chat]:
    """List all chats for the current user.

    Args:
    ----
        db: The database session.
        skip: The number of chats to skip.
        limit: The number of chats to return.
        user: The current user.

    Returns:
    -------
        list[schemas.Chat]: The list of chats.
    """
    chats = await crud.chat.get_active_chats(db=db, current_user=user, skip=skip, limit=limit)
    return chats


@router.get("/{chat_id}", response_model=schemas.Chat)
async def get_chat(
    *,
    db: AsyncSession = Depends(get_db),
    chat_id: UUID,
    user: schemas.User = Depends(get_user),
) -> schemas.Chat:
    """Get a specific chat by ID.

    Args:
    ----
        db: The database session.
        chat_id: The ID of the chat to get.
        user: The current user.

    Returns:
    -------
        schemas.Chat: The chat.
    """
    chat = await crud.chat.get_with_messages(db=db, id=chat_id, current_user=user)
    if not chat:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")
    return chat


@router.put("/{chat_id}", response_model=schemas.Chat)
async def update_chat(
    *,
    db: AsyncSession = Depends(get_db),
    chat_id: UUID,
    chat_in: schemas.ChatUpdate,
    user: schemas.User = Depends(get_user),
) -> schemas.Chat:
    """Update a chat.

    Args:
    ----
        db: The database session.
        chat_id: The ID of the chat to update.
        chat_in: The chat update data.
        user: The current user.

    Returns:
    -------
        schemas.Chat: The updated chat.
    """
    chat = await crud.chat.get(db=db, id=chat_id, current_user=user)
    if not chat:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")

    chat = await crud.chat.update(db=db, db_obj=chat, obj_in=chat_in, current_user=user)
    return chat


@router.delete("/{chat_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_chat(
    *,
    db: AsyncSession = Depends(get_db),
    chat_id: UUID,
    user: schemas.User = Depends(get_user),
) -> None:
    """Archive a chat.

    Args:
    ----
        db: The database session.
        chat_id: The ID of the chat to archive.
        user: The current user.
    """
    chat = await crud.chat.get(db=db, id=chat_id, current_user=user)
    if not chat:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")

    await crud.chat.remove(db=db, id=chat_id, current_user=user)


@router.post("/{chat_id}/message")
async def send_message(
    *,
    db: AsyncSession = Depends(get_db),
    chat_id: UUID,
    message: schemas.ChatMessageCreate,
    user: schemas.User = Depends(get_user),
) -> schemas.ChatMessage:
    """Send a message to a chat.

    Args:
    -----
        db: The database session.
        chat_id: The ID of the chat to send the message to.
        message: The message to send.
        user: The current user.

    Returns:
    -------
        schemas.ChatMessage: The sent message.
    """
    return await crud.chat.add_message(db=db, chat_id=chat_id, obj_in=message, current_user=user)


@router.get("/{chat_id}/stream", response_class=StreamingResponse)
async def stream_chat_response(
    *,
    request: Request,
    db: AsyncSession = Depends(get_db),
    chat_id: UUID,
    user: schemas.User = Depends(get_user_from_token_param),
) -> StreamingResponse:
    """Stream an AI response for a chat message.

    Args:
    -----
        request: The request object.
        db: The database session.
        chat_id: The ID of the chat to stream the response for.
        user: The current user.

    Returns:
    -------
        StreamingResponse: The streaming response.
    """

    async def event_generator():
        try:
            async for entity in chat_service.generate_streaming_response(
                db=db, chat_id=chat_id, user=user
            ):
                if entity.choices[0].delta.content is not None:
                    content = entity.choices[0].delta.content
                    # Properly encode newlines for SSE
                    content = content.replace("\n", "\\n")
                    yield f"data: {content}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            logger.error(f"Error in stream: {str(e)}")
            yield "data: [ERROR]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
    )


# @router.get("/{chat_id}/stream", response_class=StreamingResponse)
# async def stream_chat_response(
#     *,
#     db: AsyncSession = Depends(get_db),
#     user: schemas.User = Depends(get_user),
# ) -> StreamingResponse:
#     """Stream a test response with predefined text."""
#     TEST_TEXT = """
#     You still have 2 uncompleted tasks related to the Python programming language.
#     The first is titled "Refactor Pydantic models" and the second is titled "Make use of
#     structured outputs instead of free-form text". Would you like me to give you a detailed
#     explanation of the tasks?
#     """

#     async def test_event_generator():
#         await asyncio.sleep(2)
#         try:
#             # Split text into words and stream each word
#             for word in TEST_TEXT.split():
#                 yield f"data: {word} \n\n"
#                 await asyncio.sleep(0.1)  # Add small delay between words
#             yield "data: [DONE]\n\n"
#         except Exception as e:
#             logger.error(f"Error in test stream: {str(e)}")
#             yield "data: [ERROR]\n\n"

#     return StreamingResponse(
#         test_event_generator(),
#         media_type="text/event-stream",
#     )
