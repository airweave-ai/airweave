"""Chat service for handling AI interactions."""

import logging
from enum import Enum
from typing import AsyncGenerator, Dict, List, Optional, Union
from uuid import UUID

import anthropic
from anthropic.types import MessageParam, MessageStreamEvent
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionChunk
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.core.config import settings
from airweave.core.search_service import search_service
from airweave.models.chat import ChatMessage, ChatRole

logger = logging.getLogger(__name__)


class ModelProvider(str, Enum):
    """Model provider enum."""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"


class ChatService:
    """Service for handling chat interactions with AI."""

    DEFAULT_MODEL = "claude-3-7-sonnet-20250219"
    DEFAULT_MODEL_SETTINGS = {
        "temperature": 0.7,
        "max_tokens": 1000,
        "top_p": 1,
        "frequency_penalty": 0,
        "presence_penalty": 0,
    }

    # Mapping of model names to providers
    MODEL_PROVIDERS = {
        # OpenAI models
        "gpt-4o": ModelProvider.OPENAI,
        "gpt-4": ModelProvider.OPENAI,
        "gpt-3.5-turbo": ModelProvider.OPENAI,
        # Anthropic models
        "claude-3-7-sonnet-20250219": ModelProvider.ANTHROPIC,
        "claude-3-5-sonnet-20241022": ModelProvider.ANTHROPIC,
        "claude-3-opus-20240229": ModelProvider.ANTHROPIC,
        "claude-3-sonnet-20240229": ModelProvider.ANTHROPIC,
        "claude-3-haiku-20240307": ModelProvider.ANTHROPIC,
    }

    # Default provider-specific settings
    PROVIDER_DEFAULT_SETTINGS = {
        ModelProvider.OPENAI: DEFAULT_MODEL_SETTINGS,
        ModelProvider.ANTHROPIC: {
            "temperature": 0.7,
            "max_tokens": 1000,
            "top_p": 1,
        },
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
        """Initialize the chat service with OpenAI and Anthropic clients."""
        # Initialize OpenAI client
        if not settings.OPENAI_API_KEY:
            logger.warning("OPENAI_API_KEY is not set in environment variables")
            self.openai_client = None
        else:
            self.openai_client = AsyncOpenAI(
                api_key=settings.OPENAI_API_KEY,
            )

        # Initialize Anthropic client
        if not settings.ANTHROPIC_API_KEY:
            logger.warning("ANTHROPIC_API_KEY is not set in environment variables")
            self.anthropic_client = None
        else:
            try:
                # Create client without proxies to avoid HTTPX compatibility issues
                self.anthropic_client = anthropic.AsyncAnthropic(
                    api_key=settings.ANTHROPIC_API_KEY,
                    # Use explicit version to avoid compatibility issues
                    base_url="https://api.anthropic.com/v1",
                    default_headers={"anthropic-version": "2023-06-01"},
                )
            except Exception as e:
                logger.error(f"Failed to initialize Anthropic client: {str(e)}")
                self.anthropic_client = None

    def _get_model_provider(self, model: str) -> ModelProvider:
        """Determine the provider for a given model name.

        Args:
            model (str): The model name

        Returns:
            ModelProvider: The model provider
        """
        return self.MODEL_PROVIDERS.get(model, ModelProvider.OPENAI)

    def _get_client_for_model(self, model: str):
        """Get the appropriate client for the model.

        Args:
            model (str): The model name

        Returns:
            Union[AsyncOpenAI, AsyncAnthropic]: The client for the model
        """
        provider = self._get_model_provider(model)
        if provider == ModelProvider.OPENAI:
            return self.openai_client
        elif provider == ModelProvider.ANTHROPIC:
            return self.anthropic_client
        return self.openai_client  # Default to OpenAI

    def _get_default_settings_for_model(self, model: str) -> Dict:
        """Get the default settings for a model.

        Args:
            model (str): The model name

        Returns:
            Dict: The default settings for the model
        """
        provider = self._get_model_provider(model)
        return self.PROVIDER_DEFAULT_SETTINGS[provider]

    def _prepare_openai_messages(
        self, messages: list[ChatMessage], context: str = ""
    ) -> List[Dict]:
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

    def _prepare_anthropic_messages(
        self, messages: list[ChatMessage], context: str = ""
    ) -> tuple[List[MessageParam], str]:
        """Prepare messages for Anthropic API format with optional context.

        Args:
            messages: List of chat messages
            context: Optional context to include

        Returns:
            tuple: (formatted_messages, system_message)
        """
        formatted_messages: List[MessageParam] = []
        system_message = None

        # Find system message or create one with context
        for message in messages:
            if message.role == ChatRole.SYSTEM:
                system_message = message.content
                break

        if not system_message:
            system_message = (
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

        # Convert chat history to Anthropic message format
        for message in messages:
            if message.role == ChatRole.SYSTEM:
                continue  # Skip system messages as they're handled separately

            role = "user" if message.role == ChatRole.USER else "assistant"

            formatted_messages.append({"role": role, "content": message.content})

        return formatted_messages, system_message

    async def generate_streaming_response(
        self,
        db: AsyncSession,
        chat_id: UUID,
        user: schemas.User,
    ) -> AsyncGenerator[Union[ChatCompletionChunk, MessageStreamEvent], None]:
        """Generate a streaming AI response.

        Args:
            db (AsyncSession): Database session
            chat_id (UUID): Chat ID
            user (schemas.User): Current user

        Yields:
            AsyncGenerator[Union[ChatCompletionChunk, MessageStreamEvent]]: Stream of response chunks
        """
        try:
            chat = await crud.chat.get_with_messages(db=db, id=chat_id, current_user=user)
            if not chat:
                logger.error(f"Chat {chat_id} not found")
                return

            # Get relevant context from last user message
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

            # Get model and determine provider
            model = chat.model_name or self.DEFAULT_MODEL
            provider = self._get_model_provider(model)
            client = self._get_client_for_model(model)

            if not client:
                logger.error(f"No client available for model {model}")
                error_message = schemas.ChatMessageCreate(
                    content=f"Error: API key not configured for {provider} models",
                    role=ChatRole.ASSISTANT,
                )
                await crud.chat.add_message(
                    db=db, chat_id=chat_id, obj_in=error_message, current_user=user
                )
                return

            # Get default settings for the model and enable streaming
            model_settings = {
                **self._get_default_settings_for_model(model),
                "stream": True,  # Enable streaming
            }

            full_content = ""
            if provider == ModelProvider.OPENAI:
                # Prepare messages for OpenAI
                messages = self._prepare_openai_messages(chat.messages, context)

                # Create streaming response with OpenAI
                stream = await self.openai_client.chat.completions.create(
                    model=model,
                    messages=messages,
                    **model_settings,
                )

                async for chunk in stream:
                    if chunk.choices[0].delta.content:
                        full_content += chunk.choices[0].delta.content
                    yield chunk

            elif provider == ModelProvider.ANTHROPIC:
                # Prepare messages for Anthropic
                messages, system_message = self._prepare_anthropic_messages(chat.messages, context)

                try:
                    # Create streaming response with Anthropic
                    stream = await self.anthropic_client.messages.stream(
                        model=model,
                        messages=messages,
                        system=system_message,
                        max_tokens=model_settings.get("max_tokens", 1000),
                        temperature=model_settings.get("temperature", 0.7),
                    )

                    async with stream as stream_manager:
                        async for chunk in stream_manager:
                            if (
                                hasattr(chunk, "delta")
                                and hasattr(chunk.delta, "text")
                                and chunk.delta.text
                            ):
                                full_content += chunk.delta.text
                            yield chunk
                except Exception as e:
                    logger.error(f"Error in Anthropic streaming: {str(e)}")
                    # Try fallback to non-streaming for Anthropic if streaming fails
                    try:
                        response = await self.anthropic_client.messages.create(
                            model=model,
                            messages=messages,
                            system=system_message,
                            max_tokens=model_settings.get("max_tokens", 1000),
                            temperature=model_settings.get("temperature", 0.7),
                        )

                        content = "".join(
                            block["text"]
                            for block in response.content
                            if isinstance(block, dict) and block.get("type") == "text"
                        )
                        full_content = content
                    except Exception as inner_e:
                        logger.error(f"Error in Anthropic fallback: {str(inner_e)}")
                        raise

            # Save the complete message after streaming
            if full_content:
                message_create = schemas.ChatMessageCreate(
                    content=full_content,
                    role=ChatRole.ASSISTANT,
                )
                await crud.chat.add_message(
                    db=db, chat_id=chat_id, obj_in=message_create, current_user=user
                )

        except Exception as e:
            logger.error(f"Error generating streaming response: {str(e)}")
            # Create error message
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

            # Get model and determine provider
            model = chat.model_name or self.DEFAULT_MODEL
            provider = self._get_model_provider(model)
            client = self._get_client_for_model(model)

            if not client:
                logger.error(f"No client available for model {model}")
                error_message = schemas.ChatMessageCreate(
                    content=f"Error: API key not configured for {provider} models",
                    role=ChatRole.ASSISTANT,
                )
                return await crud.chat.add_message(
                    db=db, chat_id=chat_id, obj_in=error_message, current_user=user
                )

            # Get default settings for the model
            model_settings = {
                **self._get_default_settings_for_model(model),
                **chat.model_settings,
            }

            content = ""
            if provider == ModelProvider.OPENAI:
                # Prepare messages for OpenAI
                messages = self._prepare_openai_messages(chat.messages)

                # Generate response with OpenAI
                response = await self.openai_client.chat.completions.create(
                    model=model, messages=messages, **model_settings
                )

                if not response.choices:
                    logger.error("No response generated from OpenAI")
                    return None

                content = response.choices[0].message.content

            elif provider == ModelProvider.ANTHROPIC:
                # Prepare messages for Anthropic
                messages, system_message = self._prepare_anthropic_messages(chat.messages)

                try:
                    # Generate response with Anthropic
                    response = await self.anthropic_client.messages.create(
                        model=model,
                        messages=messages,
                        system=system_message,
                        max_tokens=model_settings.get("max_tokens", 1000),
                        temperature=model_settings.get("temperature", 0.7),
                    )

                    # Extract text content from the response
                    content = "".join(
                        block["text"]
                        for block in response.content
                        if isinstance(block, dict) and block.get("type") == "text"
                    )
                except Exception as e:
                    logger.error(f"Error in Anthropic response: {str(e)}")
                    raise

            # Save the response
            message_create = schemas.ChatMessageCreate(
                content=content,
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
            search_results = await search_service.search(
                db=db,
                query=query,
                sync_id=chat.sync_id,
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
        return self._prepare_openai_messages(messages, context)


# Create a singleton instance
chat_service = ChatService()
