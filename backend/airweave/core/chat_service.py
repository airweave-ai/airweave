"""Chat service for handling AI interactions."""

import logging
from typing import AsyncGenerator, Optional
from uuid import UUID

from openai.types.chat import ChatCompletionChunk
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.core.config import settings
from airweave.core.llm_providers import get_llm_client
from airweave.models.chat import ChatMessage, ChatRole

logger = logging.getLogger(__name__)


class ChatService:
    """Service for handling chat interactions with AI."""

    DEFAULT_MODEL = "gpt-4o"
    DEFAULT_MODEL_SETTINGS = {
        "temperature": 0.7,
        "max_tokens": 1000,
        "top_p": 1,
        "frequency_penalty": 0,
        "presence_penalty": 0,
    }

    CONTEXT_PROMPT = """You are an AI assistant with access to a knowledge base.
    Use the following relevant context to help answer the user's question.
    Always format your responses in proper markdown, including:
    - Using proper headers (# ## ###)
    - Formatting code blocks with ```language
    - Using tables with | header | header |
    - Using bullet points and numbered lists
    - Using **bold** and *italic* where appropriate

    Here's the context:
    {context}

    Remember to:
    1. Be helpful, clear, and accurate
    2. Maintain a professional tone
    3. Format ALL responses in proper markdown
    4. Use tables when presenting structured data
    5. Use code blocks with proper language tags"""

    def __init__(self):
        """Initialize the chat service with OpenAI client."""
        self.client = get_llm_client()
        if settings.LLM_PROVIDER.lower() == "ollama":
            self.DEFAULT_MODEL = "llama3:latest"  # or "llama3:latest"
        else:
            self.DEFAULT_MODEL = "gpt-4o"

    async def _stream_chat_response(
        self,
        model: str,
        messages: list[dict],
        model_settings: dict,
    ) -> AsyncGenerator[ChatCompletionChunk, None]:
        """Stream chat response from the LLM client."""
        if settings.LLM_PROVIDER.lower() == "ollama":
            async for chunk in self.client.create_completion(
                model=model, messages=messages, **model_settings
            ):
                yield chunk
        else:
            stream = await self.client.create_completion(
                model=model, messages=messages, **model_settings
            )
            async for chunk in stream:
                yield chunk

    async def generate_streaming_response(
        self,
        db: AsyncSession,
        chat_id: UUID,
        user: schemas.User,
    ) -> AsyncGenerator[ChatCompletionChunk, None]:
        """Generate a streaming AI response."""
        try:
            chat = await crud.chat.get_with_messages(db=db, id=chat_id, current_user=user)
            if not chat:
                logger.error(f"Chat {chat_id} not found")
                return

            last_user_message = next(
                (msg for msg in reversed(chat.messages) if msg.role == ChatRole.USER), None
            )
            context = ""
            if last_user_message:
                context = await self._get_relevant_context(
                    db=db, chat=chat, query=last_user_message.content, user=user
                )

            messages = self._prepare_messages_with_context(chat.messages, context)
            model = chat.model_name or self.DEFAULT_MODEL
            model_settings = {**self.DEFAULT_MODEL_SETTINGS, "stream": True}

            full_content = ""
            async for chunk in self._stream_chat_response(model, messages, model_settings):
                if chunk.choices[0].delta.content:
                    full_content += chunk.choices[0].delta.content
                yield chunk

            if full_content:
                message_create = schemas.ChatMessageCreate(
                    content=full_content, role=ChatRole.ASSISTANT
                )
                await crud.chat.add_message(
                    db=db, chat_id=chat_id, obj_in=message_create, current_user=user
                )

        except Exception as e:
            logger.error(f"Error generating streaming response: {str(e)}")
            error_message = schemas.ChatMessageCreate(
                content=(
                    "Sorry, I encountered an error while generating a response. Please try again."
                ),
                role=ChatRole.ASSISTANT,
            )
            await crud.chat.add_message(
                db=db, chat_id=chat_id, obj_in=error_message, current_user=user
            )
            raise

    async def generate_and_save_response(
        self,
        db: AsyncSession,
        chat_id: UUID,
        user: schemas.User,
    ) -> Optional[ChatMessage]:
        """Generate a non-streaming AI response and save it."""
        try:
            chat = await crud.chat.get_with_messages(db=db, id=chat_id, current_user=user)
            if not chat:
                logger.error(f"Chat {chat_id} not found")
                return None

            messages = self._prepare_messages(chat.messages)
            model = chat.model_name or self.DEFAULT_MODEL
            model_settings = {
                **self.DEFAULT_MODEL_SETTINGS,
                **chat.model_settings,
            }

            response = await self.client.chat.completions.create(
                model=model, messages=messages, **model_settings
            )

            if not response.choices:
                logger.error("No response generated from OpenAI")
                return None

            message_create = schemas.ChatMessageCreate(
                content=response.choices[0].message.content,
                role=ChatRole.ASSISTANT,
            )

            return await crud.chat.add_message(
                db=db, chat_id=chat_id, obj_in=message_create, current_user=user
            )

        except Exception as e:
            logger.error(f"Error generating AI response: {str(e)}")
            error_message = schemas.ChatMessageCreate(
                content=(
                    "Sorry, I encountered an error while generating a response. Please try again."
                ),
                role=ChatRole.ASSISTANT,
            )
            return await crud.chat.add_message(
                db=db, chat_id=chat_id, obj_in=error_message, current_user=user
            )

    def _prepare_messages(self, messages: list[ChatMessage]) -> list[dict]:
        """Prepare messages for OpenAI API format."""
        formatted_messages = []
        has_system_message = any(msg.role == ChatRole.SYSTEM for msg in messages)

        if not has_system_message:
            formatted_messages.append(
                {
                    "role": "system",
                    "content": (
                        "You are a helpful AI assistant. Provide clear, accurate, "
                        "and concise responses while being friendly and professional."
                    ),
                }
            )

        formatted_messages.extend(
            [{"role": message.role, "content": message.content} for message in messages]
        )

        return formatted_messages

    async def _get_relevant_context(
        self,
        db: AsyncSession,
        chat: schemas.Chat,
        query: str,
        user: schemas.User,
    ) -> str:
        """Get relevant context from vector store if sync_id is present."""
        if not chat.sync_id:
            return ""

        try:
            # Lazy import to avoid circular dependency
            from airweave.core.search_service import search_service

            search_results = await search_service.search(
                db=db,
                query=query,
                readable_id=chat.sync_id,
                current_user=user,
            )

            if not search_results:
                return ""

            return "\n\n".join(str(result) for result in search_results)

        except Exception as e:
            logger.error(f"Error getting search context: {str(e)}")
            raise e

    def _prepare_messages_with_context(
        self,
        messages: list[ChatMessage],
        context: str = "",
    ) -> list[dict]:
        """Prepare messages for OpenAI API format with optional context."""
        formatted_messages = []
        has_system_message = any(msg.role == ChatRole.SYSTEM for msg in messages)

        # Add system message with context if available
        if not has_system_message:
            system_content = (
                self.CONTEXT_PROMPT.format(context=context)
                if context
                else (
                    "You are a helpful AI assistant. "
                    "Always format your responses in proper markdown, "
                    "including tables, code blocks with language tags, and proper headers. "
                    "Provide clear, accurate, and concise responses while being friendly"
                    " and professional."
                )
            )
            formatted_messages.append(
                {
                    "role": "system",
                    "content": system_content,
                }
            )

        # Add chat history
        formatted_messages.extend(
            [{"role": message.role, "content": message.content} for message in messages]
        )

        return formatted_messages


# Create a singleton instance
chat_service = ChatService()
