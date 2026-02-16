"""Microsoft Teams source implementation.

Retrieves data from Microsoft Teams, including:
 - Teams the user has joined
 - Channels within teams
 - Chats (1:1, group, meeting)
 - Messages in channels and chats
 - Team members

Reference:
  https://learn.microsoft.com/en-us/graph/api/resources/teams-api-overview
  https://learn.microsoft.com/en-us/graph/api/user-list-joinedteams
  https://learn.microsoft.com/en-us/graph/api/channel-list
  https://learn.microsoft.com/en-us/graph/api/chat-list
"""

from datetime import datetime
from typing import Any, AsyncGenerator, Dict, Optional

import httpx
from tenacity import retry, stop_after_attempt

from airweave.core.shared_models import RateLimitLevel
from airweave.platform.configs.config import TeamsConfig
from airweave.platform.decorators import source
from airweave.platform.entities._base import BaseEntity, Breadcrumb
from airweave.platform.entities.teams import (
    TeamsChannelEntity,
    TeamsChatEntity,
    TeamsMessageEntity,
    TeamsTeamEntity,
    TeamsUserEntity,
)
from airweave.platform.sources._base import BaseSource
from airweave.platform.sources.retry_helpers import (
    retry_if_rate_limit_or_timeout,
    wait_rate_limit_with_backoff,
)
from airweave.schemas.source_connection import AuthenticationMethod, OAuthType


@source(
    name="Teams",
    short_name="teams",
    auth_methods=[
        AuthenticationMethod.OAUTH_BROWSER,
        AuthenticationMethod.OAUTH_TOKEN,
        AuthenticationMethod.AUTH_PROVIDER,
    ],
    oauth_type=OAuthType.WITH_ROTATING_REFRESH,
    auth_config_class=None,
    config_class=TeamsConfig,
    labels=["Communication", "Collaboration"],
    supports_continuous=False,
    rate_limit_level=RateLimitLevel.ORG,
)
class TeamsSource(BaseSource):
    """Microsoft Teams source connector integrates with the Microsoft Graph API.

    Synchronizes data from Microsoft Teams including teams, channels, chats, and messages.

    It provides comprehensive access to Teams resources with proper token refresh
    and rate limiting.
    """

    GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"

    @classmethod
    async def create(
        cls, access_token: str, config: Optional[Dict[str, Any]] = None
    ) -> "TeamsSource":
        """Create a new Microsoft Teams source instance with the provided OAuth access token.

        Args:
            access_token: OAuth access token for Microsoft Graph API
            config: Optional configuration parameters

        Returns:
            Configured TeamsSource instance
        """
        instance = cls()
        instance.access_token = access_token
        return instance

    @retry(
        stop=stop_after_attempt(5),
        retry=retry_if_rate_limit_or_timeout,
        wait=wait_rate_limit_with_backoff,
        reraise=True,
    )
    async def _get_with_auth(
        self, client: httpx.AsyncClient, url: str, params: Optional[dict] = None
    ) -> dict:
        """Make an authenticated GET request to Microsoft Graph API.

        Args:
            client: HTTP client to use for the request
            url: API endpoint URL
            params: Optional query parameters

        Returns:
            JSON response data
        """
        # Get fresh token (will refresh if needed)
        access_token = await self.get_access_token()
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        }

        try:
            response = await client.get(url, headers=headers, params=params)

            # Handle 401 errors by refreshing token and retrying
            if response.status_code == 401:
                self.logger.warning(
                    f"Got 401 Unauthorized from Microsoft Graph API at {url}, refreshing token..."
                )
                await self.refresh_on_unauthorized()

                # Get new token and retry
                access_token = await self.get_access_token()
                headers = {
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/json",
                }
                response = await client.get(url, headers=headers, params=params)

            # Handle 429 Rate Limit
            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After", "60")
                self.logger.warning(
                    f"Rate limit hit for {url}, waiting {retry_after} seconds before retry"
                )
                import asyncio

                await asyncio.sleep(float(retry_after))
                # Retry after waiting
                response = await client.get(url, headers=headers, params=params)

            response.raise_for_status()
            data = response.json()
            return data
        except Exception as e:
            self.logger.error(f"Error in API request to {url}: {str(e)}")
            raise

    def _parse_datetime(self, dt_str: Optional[str]) -> Optional[datetime]:
        """Parse datetime string from Microsoft Graph API format.

        Args:
            dt_str: DateTime string from API

        Returns:
            Parsed datetime object or None
        """
        if not dt_str:
            return None
        try:
            if dt_str.endswith("Z"):
                dt_str = dt_str.replace("Z", "+00:00")
            return datetime.fromisoformat(dt_str)
        except (ValueError, TypeError) as e:
            self.logger.warning(f"Error parsing datetime {dt_str}: {str(e)}")
            return None

    async def _generate_user_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[TeamsUserEntity, None]:
        """Generate TeamsUserEntity objects for users in the organization.

        Args:
            client: HTTP client for API requests

        Yields:
            TeamsUserEntity objects
        """
        self.logger.info("Starting user entity generation")
        url = f"{self.GRAPH_BASE_URL}/users"
        params = {
            "$top": 100,
            "$select": ("id,displayName,userPrincipalName,mail,jobTitle,department,officeLocation"),
        }

        try:
            user_count = 0
            while url:
                self.logger.debug(f"Fetching users from: {url}")
                data = await self._get_with_auth(client, url, params=params)
                users = data.get("value", [])
                self.logger.info(f"Retrieved {len(users)} users")

                for user_data in users:
                    user_count += 1
                    user_id = user_data.get("id")
                    display_name = user_data.get("displayName", "Unknown User")

                    self.logger.debug(f"Processing user #{user_count}: {display_name}")

                    yield TeamsUserEntity(
                        breadcrumbs=[],
                        id=user_id,
                        name=display_name,
                        created_at=None,  # Users don't have creation timestamp in Teams API
                        updated_at=None,  # Users don't have update timestamp in Teams API
                        # API fields
                        display_name=display_name,
                        user_principal_name=user_data.get("userPrincipalName"),
                        mail=user_data.get("mail"),
                        job_title=user_data.get("jobTitle"),
                        department=user_data.get("department"),
                        office_location=user_data.get("officeLocation"),
                    )

                # Handle pagination
                url = data.get("@odata.nextLink")
                if url:
                    self.logger.debug("Following pagination to next page")
                    params = None  # params are included in the nextLink

            self.logger.info(f"Completed user generation. Total users: {user_count}")

        except Exception as e:
            self.logger.error(f"Error generating user entities: {str(e)}")
            # Don't raise - continue with other entities

    async def _generate_team_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[TeamsTeamEntity, None]:
        """Generate TeamsTeamEntity objects for teams the user has joined.

        Args:
            client: HTTP client for API requests

        Yields:
            TeamsTeamEntity objects
        """
        self.logger.info("Starting team entity generation")
        url = f"{self.GRAPH_BASE_URL}/me/joinedTeams"

        try:
            team_count = 0
            while url:
                self.logger.debug(f"Fetching teams from: {url}")
                data = await self._get_with_auth(client, url)
                teams = data.get("value", [])
                self.logger.info(f"Retrieved {len(teams)} teams")

                for team_data in teams:
                    team_count += 1
                    team_id = team_data.get("id")
                    display_name = team_data.get("displayName", "Unknown Team")

                    self.logger.debug(f"Processing team #{team_count}: {display_name}")

                    yield TeamsTeamEntity(
                        breadcrumbs=[],
                        id=team_id,
                        name=display_name,
                        created_at=self._parse_datetime(team_data.get("createdDateTime")),
                        updated_at=None,  # Teams don't have update timestamp
                        # API fields
                        display_name=display_name,
                        description=team_data.get("description"),
                        visibility=team_data.get("visibility"),
                        is_archived=team_data.get("isArchived"),
                        web_url=team_data.get("webUrl"),
                        web_url_override=team_data.get("webUrl"),
                        classification=team_data.get("classification"),
                        specialization=team_data.get("specialization"),
                        internal_id=team_data.get("internalId"),
                    )

                # Handle pagination
                url = data.get("@odata.nextLink")
                if url:
                    self.logger.debug("Following pagination to next page")

            self.logger.info(f"Completed team generation. Total teams: {team_count}")

        except Exception as e:
            self.logger.error(f"Error generating team entities: {str(e)}")
            raise

    async def _generate_channel_entities(
        self, client: httpx.AsyncClient, team_id: str, team_name: str
    ) -> AsyncGenerator[TeamsChannelEntity, None]:
        """Generate TeamsChannelEntity objects for channels in a team.

        Args:
            client: HTTP client for API requests
            team_id: ID of the team
            team_name: Name of the team

        Yields:
            TeamsChannelEntity objects
        """
        self.logger.info(f"Starting channel entity generation for team: {team_name}")
        url = f"{self.GRAPH_BASE_URL}/teams/{team_id}/channels"

        try:
            channel_count = 0
            while url:
                self.logger.debug(f"Fetching channels from: {url}")
                data = await self._get_with_auth(client, url)
                channels = data.get("value", [])
                self.logger.info(f"Retrieved {len(channels)} channels for team {team_name}")

                for channel_data in channels:
                    channel_count += 1
                    channel_id = channel_data.get("id")
                    display_name = channel_data.get("displayName", "Unknown Channel")

                    self.logger.debug(f"Processing channel #{channel_count}: {display_name}")

                    yield TeamsChannelEntity(
                        breadcrumbs=[
                            Breadcrumb(
                                entity_id=team_id,
                                name=team_name,
                                entity_type="TeamsTeamEntity",
                            )
                        ],
                        id=channel_id,
                        name=display_name,
                        created_at=self._parse_datetime(channel_data.get("createdDateTime")),
                        updated_at=None,  # Channels don't have update timestamp
                        # API fields
                        team_id=team_id,
                        display_name=display_name,
                        description=channel_data.get("description"),
                        email=channel_data.get("email"),
                        membership_type=channel_data.get("membershipType"),
                        is_archived=channel_data.get("isArchived"),
                        is_favorite_by_default=channel_data.get("isFavoriteByDefault"),
                        web_url_override=channel_data.get("webUrl"),
                    )

                # Handle pagination
                url = data.get("@odata.nextLink")
                if url:
                    self.logger.debug("Following pagination to next page")

            self.logger.info(
                f"Completed channel generation for team {team_name}. "
                f"Total channels: {channel_count}"
            )

        except Exception as e:
            self.logger.error(f"Error generating channel entities for team {team_name}: {str(e)}")
            # Don't raise - continue with other teams

    async def _generate_channel_message_entities(
        self,
        client: httpx.AsyncClient,
        team_id: str,
        team_name: str,
        channel_id: str,
        channel_name: str,
        team_breadcrumb: Breadcrumb,
        channel_breadcrumb: Breadcrumb,
    ) -> AsyncGenerator[TeamsMessageEntity, None]:
        """Generate TeamsMessageEntity objects for messages in a channel.

        Args:
            client: HTTP client for API requests
            team_id: ID of the team
            team_name: Name of the team
            channel_id: ID of the channel
            channel_name: Name of the channel
            team_breadcrumb: Breadcrumb for the team
            channel_breadcrumb: Breadcrumb for the channel

        Yields:
            TeamsMessageEntity objects
        """
        self.logger.info(f"Starting message generation for channel: {channel_name}")
        url = f"{self.GRAPH_BASE_URL}/teams/{team_id}/channels/{channel_id}/messages"
        params = {"$top": 50}  # Max allowed by Graph API

        try:
            message_count = 0
            while url:
                self.logger.debug(f"Fetching messages from: {url}")
                data = await self._get_with_auth(client, url, params=params)
                messages = data.get("value", [])
                self.logger.info(f"Retrieved {len(messages)} messages for channel {channel_name}")

                for message_data in messages:
                    message_count += 1
                    message_id = message_data.get("id")

                    self.logger.debug(f"Processing message #{message_count}: {message_id}")

                    # Extract sender info
                    from_info = message_data.get("from", {})

                    # Extract body content
                    body = message_data.get("body", {})
                    body_content = body.get("content", "")

                    # Create name from subject or body preview
                    subject = message_data.get("subject")
                    if subject:
                        name = subject
                    elif body_content:
                        # Use first 50 chars of body as name
                        name = body_content[:50] + "..." if len(body_content) > 50 else body_content
                    else:
                        name = f"Message {message_id}"

                    created_dt = self._parse_datetime(message_data.get("createdDateTime"))
                    updated_dt = self._parse_datetime(message_data.get("lastModifiedDateTime"))
                    subject_value = subject or name

                    yield TeamsMessageEntity(
                        breadcrumbs=[team_breadcrumb, channel_breadcrumb],
                        id=message_id,
                        name=name,
                        created_at=created_dt,
                        updated_at=updated_dt,
                        team_id=team_id,
                        channel_id=channel_id,
                        chat_id=None,
                        reply_to_id=message_data.get("replyToId"),
                        message_type=message_data.get("messageType"),
                        subject=subject_value,
                        body_content=body_content,
                        body_content_type=body.get("contentType"),
                        from_user=from_info,
                        last_edited_datetime=self._parse_datetime(
                            message_data.get("lastEditedDateTime")
                        ),
                        deleted_datetime=self._parse_datetime(message_data.get("deletedDateTime")),
                        importance=message_data.get("importance"),
                        mentions=message_data.get("mentions", []),
                        attachments=message_data.get("attachments", []),
                        reactions=message_data.get("reactions", []),
                        web_url_override=message_data.get("webUrl"),
                        created_datetime=created_dt,
                    )

                # Handle pagination
                url = data.get("@odata.nextLink")
                if url:
                    self.logger.debug("Following pagination to next page")
                    params = None  # params are included in the nextLink

            self.logger.info(
                f"Completed message generation for channel {channel_name}. "
                f"Total messages: {message_count}"
            )

        except Exception as e:
            self.logger.error(f"Error generating messages for channel {channel_name}: {str(e)}")
            # Don't raise - continue with other channels

    async def _generate_chat_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[TeamsChatEntity, None]:
        """Generate TeamsChatEntity objects for user's chats.

        Args:
            client: HTTP client for API requests

        Yields:
            TeamsChatEntity objects
        """
        self.logger.info("Starting chat entity generation")
        url = f"{self.GRAPH_BASE_URL}/me/chats"
        params = {"$top": 50}

        try:
            chat_count = 0
            while url:
                self.logger.debug(f"Fetching chats from: {url}")
                data = await self._get_with_auth(client, url, params=params)
                chats = data.get("value", [])
                self.logger.info(f"Retrieved {len(chats)} chats")

                for chat_data in chats:
                    chat_count += 1
                    chat_id = chat_data.get("id")
                    topic = chat_data.get("topic", "")
                    chat_type = chat_data.get("chatType", "oneOnOne")

                    self.logger.debug(f"Processing chat #{chat_count}: {chat_type} - {topic}")

                    # Create name from topic or chat type
                    name = topic if topic else f"{chat_type} chat"

                    yield TeamsChatEntity(
                        breadcrumbs=[],
                        id=chat_id,
                        name=name,
                        created_at=self._parse_datetime(chat_data.get("createdDateTime")),
                        updated_at=self._parse_datetime(chat_data.get("lastUpdatedDateTime")),
                        # API fields
                        chat_type=chat_type,
                        topic_label=name,
                        topic=topic if topic else None,
                        web_url_override=chat_data.get("webUrl"),
                    )

                # Handle pagination
                url = data.get("@odata.nextLink")
                if url:
                    self.logger.debug("Following pagination to next page")
                    params = None

            self.logger.info(f"Completed chat generation. Total chats: {chat_count}")

        except Exception as e:
            self.logger.error(f"Error generating chat entities: {str(e)}")
            # Don't raise - continue with other entities

    async def _generate_chat_message_entities(
        self,
        client: httpx.AsyncClient,
        chat_id: str,
        chat_topic: Optional[str],
        chat_breadcrumb: Breadcrumb,
    ) -> AsyncGenerator[TeamsMessageEntity, None]:
        """Generate TeamsMessageEntity objects for messages in a chat.

        Args:
            client: HTTP client for API requests
            chat_id: ID of the chat
            chat_topic: Topic of the chat
            chat_breadcrumb: Breadcrumb for the chat

        Yields:
            TeamsMessageEntity objects
        """
        display_chat = chat_topic if chat_topic else chat_id[:8]
        self.logger.info(f"Starting message generation for chat: {display_chat}")
        url = f"{self.GRAPH_BASE_URL}/chats/{chat_id}/messages"
        params = {"$top": 50}

        try:
            message_count = 0
            while url:
                self.logger.debug(f"Fetching chat messages from: {url}")
                data = await self._get_with_auth(client, url, params=params)
                messages = data.get("value", [])
                self.logger.info(f"Retrieved {len(messages)} messages for chat {display_chat}")

                for message_data in messages:
                    message_count += 1
                    message_id = message_data.get("id")

                    self.logger.debug(f"Processing message #{message_count}: {message_id}")

                    # Extract sender info
                    from_info = message_data.get("from", {})

                    # Extract body content
                    body = message_data.get("body", {})
                    body_content = body.get("content", "")

                    # Create name from subject or body preview
                    subject = message_data.get("subject")
                    if subject:
                        name = subject
                    elif body_content:
                        # Use first 50 chars of body as name
                        name = body_content[:50] + "..." if len(body_content) > 50 else body_content
                    else:
                        name = f"Message {message_id}"

                    created_dt = self._parse_datetime(message_data.get("createdDateTime"))
                    updated_dt = self._parse_datetime(message_data.get("lastModifiedDateTime"))
                    subject_value = subject or name

                    yield TeamsMessageEntity(
                        breadcrumbs=[chat_breadcrumb],
                        id=message_id,
                        name=name,
                        created_at=created_dt,
                        updated_at=updated_dt,
                        team_id=None,
                        channel_id=None,
                        chat_id=chat_id,
                        reply_to_id=message_data.get("replyToId"),
                        message_type=message_data.get("messageType"),
                        subject=subject_value,
                        body_content=body_content,
                        body_content_type=body.get("contentType"),
                        from_user=from_info,
                        last_edited_datetime=self._parse_datetime(
                            message_data.get("lastEditedDateTime")
                        ),
                        deleted_datetime=self._parse_datetime(message_data.get("deletedDateTime")),
                        importance=message_data.get("importance"),
                        mentions=message_data.get("mentions", []),
                        attachments=message_data.get("attachments", []),
                        reactions=message_data.get("reactions", []),
                        web_url_override=message_data.get("webUrl"),
                        created_datetime=created_dt,
                    )

                # Handle pagination
                url = data.get("@odata.nextLink")
                if url:
                    self.logger.debug("Following pagination to next page")
                    params = None

            self.logger.info(
                f"Completed message generation for chat {display_chat}. "
                f"Total messages: {message_count}"
            )

        except Exception as e:
            self.logger.error(f"Error generating messages for chat {display_chat}: {str(e)}")
            # Don't raise - continue with other chats

    async def generate_entities(self) -> AsyncGenerator[BaseEntity, None]:
        """Generate all Microsoft Teams entities.

        Yields entities in the following order:
          - TeamsUserEntity for users in the organization
          - TeamsTeamEntity for teams the user has joined
          - TeamsChannelEntity for channels in each team
          - TeamsMessageEntity for messages in each channel
          - TeamsChatEntity for user's chats
          - TeamsMessageEntity for messages in each chat
        """
        self.logger.info("===== STARTING MICROSOFT TEAMS ENTITY GENERATION =====")
        entity_count = 0

        try:
            async with self.http_client() as client:
                self.logger.info("HTTP client created, starting entity generation")

                # 1) Generate user entities
                self.logger.info("Generating user entities...")
                async for user_entity in self._generate_user_entities(client):
                    entity_count += 1
                    self.logger.debug(
                        f"Yielding entity #{entity_count}: User - {user_entity.display_name}"
                    )
                    yield user_entity

                # 2) Generate team entities and their channels
                self.logger.info("Generating team entities...")
                async for team_entity in self._generate_team_entities(client):
                    entity_count += 1
                    self.logger.info(
                        f"Yielding entity #{entity_count}: Team - {team_entity.display_name}"
                    )
                    yield team_entity

                    # Create team breadcrumb
                    team_id = team_entity.id
                    team_name = team_entity.display_name
                    team_breadcrumb = Breadcrumb(
                        entity_id=team_id,
                        name=team_entity.display_name,
                        entity_type="TeamsTeamEntity",
                    )

                    # 3) Generate channels for this team
                    async for channel_entity in self._generate_channel_entities(
                        client, team_id, team_name
                    ):
                        entity_count += 1
                        channel_display = channel_entity.display_name
                        self.logger.info(
                            f"Yielding entity #{entity_count}: Channel - {channel_display}"
                        )
                        yield channel_entity

                        # Create channel breadcrumb
                        channel_id = channel_entity.id
                        channel_name = channel_entity.display_name
                        channel_breadcrumb = Breadcrumb(
                            entity_id=channel_id,
                            name=channel_entity.display_name,
                            entity_type="TeamsChannelEntity",
                        )

                        # 4) Generate messages for this channel
                        async for message_entity in self._generate_channel_message_entities(
                            client,
                            team_id,
                            team_name,
                            channel_id,
                            channel_name,
                            team_breadcrumb,
                            channel_breadcrumb,
                        ):
                            entity_count += 1
                            msg_id = message_entity.id
                            self.logger.debug(
                                f"Yielding entity #{entity_count}: ChannelMessage - {msg_id}"
                            )
                            yield message_entity

                # 5) Generate chat entities
                self.logger.info("Generating chat entities...")
                async for chat_entity in self._generate_chat_entities(client):
                    entity_count += 1
                    self.logger.info(
                        f"Yielding entity #{entity_count}: Chat - {chat_entity.chat_type}"
                    )
                    yield chat_entity

                    # Create chat breadcrumb
                    chat_id = chat_entity.id
                    chat_breadcrumb = Breadcrumb(
                        entity_id=chat_id,
                        name=chat_entity.name,
                        entity_type="TeamsChatEntity",
                    )

                    # 6) Generate messages for this chat
                    async for message_entity in self._generate_chat_message_entities(
                        client, chat_id, chat_entity.topic, chat_breadcrumb
                    ):
                        entity_count += 1
                        msg_id = message_entity.id
                        self.logger.debug(
                            f"Yielding entity #{entity_count}: ChatMessage - {msg_id}"
                        )
                        yield message_entity

        except Exception as e:
            self.logger.error(f"Error in entity generation: {str(e)}", exc_info=True)
            raise
        finally:
            self.logger.info(
                f"===== MICROSOFT TEAMS ENTITY GENERATION COMPLETE: {entity_count} entities ====="
            )

    async def validate(self) -> bool:
        """Verify Microsoft Teams OAuth2 token by pinging the joinedTeams endpoint.

        Returns:
            True if token is valid, False otherwise
        """
        return await self._validate_oauth2(
            ping_url=f"{self.GRAPH_BASE_URL}/me/joinedTeams",
            headers={"Accept": "application/json"},
            timeout=10.0,
        )
