"""Chat service for handling AI interactions with support for multiple providers."""

import logging
import os
from typing import AsyncGenerator, Optional
from uuid import UUID

import httpx
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionChunk
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.core.config import settings
from airweave.core.search_service import search_service
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
        """Initialize the chat service with appropriate LLM client."""
        self.provider = os.getenv("LLM_PROVIDER", "openai").lower()
        self.client = self._initialize_client()

    def _initialize_client(self):
        if self.provider == "openai":
            if not settings.OPENAI_API_KEY:
                logger.warning("OPENAI_API_KEY is not set in environment variables")
                return None
            return AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        elif self.provider == "groq":
            if not settings.GROQ_API_KEY:
                logger.warning("GROQ_API_KEY is not set in environment variables")
                return None
            return settings.GROQ_API_KEY
        elif self.provider == "ollama":
            return settings.OLLAMA_BASE_URL or "http://localhost:11434"
        else:
            logger.warning(f"Unsupported LLM provider: {self.provider}")
            return None

    async def generate_streaming_response(
        self,
        db: AsyncSession,
        chat_id: UUID,
        user: schemas.User,
    ) -> AsyncGenerator[ChatCompletionChunk, None]:
        """Generate a streaming response from the AI and yield content chunks."""
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
                    db=db,
                    chat=chat,
                    query=last_user_message.content,
                    user=user,
                )

            messages = self._prepare_messages_with_context(chat.messages, context)
            model = chat.model_name or self.DEFAULT_MODEL
            model_settings = {**self.DEFAULT_MODEL_SETTINGS, "stream": True}

            if self.provider == "openai" and isinstance(self.client, AsyncOpenAI):
                stream = await self.client.chat.completions.create(
                    model=model, messages=messages, **model_settings
                )
                full_content = ""
                async for chunk in stream:
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

            elif self.provider == "groq" and self.client:
                headers = {
                    "Authorization": f"Bearer {self.client}",
                    "Content-Type": "application/json",
                }
                async with httpx.AsyncClient(timeout=60) as client:
                    response = await client.post(
                        "https://api.groq.com/openai/v1/chat/completions",
                        headers=headers,
                        json={"model": model, "messages": messages, **model_settings},
                    )
                    data = response.json()
                    content = data["choices"][0]["message"]["content"]
                    yield ChatCompletionChunk(
                        choices=[
                            type("obj", (), {"delta": type("msg", (), {"content": content})()})
                        ]
                    )

            elif self.provider == "ollama" and self.client:
                async with httpx.AsyncClient(timeout=60) as client:
                    response = await client.post(
                        f"{self.client}/api/chat",
                        json={"model": model, "messages": messages},
                    )
                    data = response.json()
                    content = data.get("message", {}).get("content", "")
                    yield ChatCompletionChunk(
                        choices=[
                            type("obj", (), {"delta": type("msg", (), {"content": content})()})
                        ]
                    )

        except Exception as e:
            logger.error(f"Error generating streaming response: {str(e)}")
            error_message = schemas.ChatMessageCreate(
                content=(
    "Sorry, I encountered an error while generating a response. "
    "Please try again."
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
        """Generate a complete AI response and save it to the database.

        Args:
        db: Async SQLAlchemy session.
        chat_id: UUID of the chat.
        user: Authenticated user.

        Returns:
        The saved ChatMessage instance.
        """
        try:
            chat = await crud.chat.get_with_messages(db=db, id=chat_id, current_user=user)
            if not chat:
                logger.error(f"Chat {chat_id} not found")
                return None

            messages = self._prepare_messages(chat.messages)
            model = chat.model_name or self.DEFAULT_MODEL
            model_settings = {**self.DEFAULT_MODEL_SETTINGS, **chat.model_settings}

            if self.provider == "openai" and isinstance(self.client, AsyncOpenAI):
                response = await self.client.chat.completions.create(
                    model=model, messages=messages, **model_settings
                )
                if not response.choices:
                    return None
                content = response.choices[0].message.content

            elif self.provider == "groq" and self.client:
                headers = {
                    "Authorization": f"Bearer {self.client}",
                    "Content-Type": "application/json",
                }
                async with httpx.AsyncClient(timeout=60) as client:
                    response = await client.post(
                        "https://api.groq.com/openai/v1/chat/completions",
                        headers=headers,
                        json={"model": model, "messages": messages, **model_settings},
                    )
                    content = response.json()["choices"][0]["message"]["content"]

            elif self.provider == "ollama" and self.client:
                async with httpx.AsyncClient(timeout=60) as client:
                    response = await client.post(
                        f"{self.client}/api/chat",
                        json={"model": model, "messages": messages},
                    )
                    content = response.json().get("message", {}).get("content", "")

            else:
                logger.error("Unsupported provider or missing client")
                return None

            message_create = schemas.ChatMessageCreate(content=content, role=ChatRole.ASSISTANT)
            return await crud.chat.add_message(
                db=db, chat_id=chat_id, obj_in=message_create, current_user=user
            )

        except Exception as e:
            logger.error(f"Error generating AI response: {str(e)}")
            error_message = schemas.ChatMessageCreate(
                content=("Sorry, I encountered an error while generating a response."
                " Please try again."),
                role=ChatRole.ASSISTANT,
            )
            return await crud.chat.add_message(
                db=db, chat_id=chat_id, obj_in=error_message, current_user=user
            )

    def _prepare_messages(self, messages: list[ChatMessage]) -> list[dict]:
        formatted_messages = []
        has_system_message = any(msg.role == ChatRole.SYSTEM for msg in messages)
        if not has_system_message:
            formatted_messages.append(
                {
                    "role": "system",
                    "content": "You are a helpful AI assistant. Provide clear, accurate, and"
                    " concise responses while being friendly and professional.",
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
        if not chat.sync_id:
            return ""
        try:
            search_results = await search_service.search(
                db=db, query=query, sync_id=chat.sync_id, current_user=user
            )
            return "\n\n".join(str(result) for result in search_results) if search_results else ""
        except Exception as e:
            logger.error(f"Error getting search context: {str(e)}")
            raise e

    def _prepare_messages_with_context(
        self,
        messages: list[ChatMessage],
        context: str = "",
    ) -> list[dict]:
        formatted_messages = []
        has_system_message = any(msg.role == ChatRole.SYSTEM for msg in messages)
        if not has_system_message:
            system_content = (
                self.CONTEXT_PROMPT.format(context=context)
                if context
                else (
                    "You are a helpful AI assistant. Always format your responses in proper "
                    "markdown, including tables, code blocks with language tags, and proper headers"
                    " Provide clear, accurate, and concise responses while being friendly and "
                    "professional."
                )
            )
            formatted_messages.append({"role": "system", "content": system_content})
        formatted_messages.extend(
            [{"role": message.role, "content": message.content} for message in messages]
        )
        return formatted_messages


# Create a singleton instance
chat_service = ChatService()
