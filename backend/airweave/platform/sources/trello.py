"""Trello source implementation for syncing boards, lists, cards, and checklists."""

import hashlib
import hmac
import secrets
import time
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Optional
from urllib.parse import quote

import httpx
from tenacity import retry, stop_after_attempt

from airweave.core.shared_models import RateLimitLevel
from airweave.platform.configs.auth import TrelloAuthConfig
from airweave.platform.configs.config import TrelloConfig
from airweave.platform.decorators import source
from airweave.platform.entities._base import BaseEntity, Breadcrumb
from airweave.platform.entities.trello import (
    TrelloBoardEntity,
    TrelloCardEntity,
    TrelloChecklistEntity,
    TrelloListEntity,
    TrelloMemberEntity,
)
from airweave.platform.sources._base import BaseSource
from airweave.platform.sources.retry_helpers import (
    retry_if_rate_limit_or_timeout,
    wait_rate_limit_with_backoff,
)
from airweave.schemas.source_connection import AuthenticationMethod, OAuthType


@source(
    name="Trello",
    short_name="trello",
    auth_methods=[
        AuthenticationMethod.OAUTH_BROWSER,
        AuthenticationMethod.AUTH_PROVIDER,
    ],
    oauth_type=OAuthType.OAUTH1,
    auth_config_class=TrelloAuthConfig,
    config_class=TrelloConfig,
    labels=["Project Management"],
    supports_continuous=False,
    rate_limit_level=RateLimitLevel.ORG,
)
class TrelloSource(BaseSource):
    """Trello source connector integrates with the Trello API using OAuth1.

    Connects to your Trello boards and syncs boards, lists, cards, checklists, and members.

    Note: Trello uses OAuth1.0, not OAuth2.
    """

    API_BASE = "https://api.trello.com/1"

    @classmethod
    async def create(
        cls, credentials: Dict[str, Any], config: Optional[Dict[str, Any]] = None
    ) -> "TrelloSource":
        """Create a new Trello source.

        Args:
            credentials: OAuth1 credentials with oauth_token and oauth_token_secret
            config: Optional configuration parameters

        Returns:
            Configured TrelloSource instance
        """
        instance = cls()

        # Extract OAuth1 credentials
        if isinstance(credentials, dict):
            instance.oauth_token = credentials.get("oauth_token")
            instance.oauth_token_secret = credentials.get("oauth_token_secret")
            # Also get consumer key/secret if provided (needed for OAuth1 signing)
            instance.consumer_key = credentials.get("consumer_key")
            instance.consumer_secret = credentials.get("consumer_secret")
        else:
            # Pydantic model
            instance.oauth_token = getattr(credentials, "oauth_token", None)
            instance.oauth_token_secret = getattr(credentials, "oauth_token_secret", None)
            instance.consumer_key = getattr(credentials, "consumer_key", None)
            instance.consumer_secret = getattr(credentials, "consumer_secret", None)

        if not instance.oauth_token or not instance.oauth_token_secret:
            raise ValueError("Trello requires oauth_token and oauth_token_secret")

        # If consumer credentials not in credentials, get from integration settings
        if not instance.consumer_key or not instance.consumer_secret:
            from airweave.platform.auth.settings import integration_settings

            try:
                oauth_settings = await integration_settings.get_by_short_name("trello")
                from airweave.platform.auth.schemas import OAuth1Settings

                if isinstance(oauth_settings, OAuth1Settings):
                    instance.consumer_key = oauth_settings.consumer_key
                    instance.consumer_secret = oauth_settings.consumer_secret
            except Exception:
                # If we can't get settings, that's okay - they might be in credentials
                pass

        # Store config values as instance attributes
        if config:
            instance.board_filter = config.get("board_filter", "")
        else:
            instance.board_filter = ""

        return instance

    def _percent_encode(self, value: str) -> str:
        """Percent-encode a value for OAuth1 signature.

        OAuth1 requires specific encoding per RFC 3986.
        """
        return quote(str(value), safe="~")

    def _build_oauth1_params(self, include_token: bool = True) -> Dict[str, str]:
        """Build OAuth1 protocol parameters for API requests.

        Args:
            include_token: Whether to include the oauth_token parameter

        Returns:
            Dict of OAuth1 parameters
        """
        params = {
            "oauth_consumer_key": self.consumer_key or "placeholder",
            "oauth_signature_method": "HMAC-SHA1",
            "oauth_timestamp": str(int(time.time())),
            "oauth_nonce": secrets.token_urlsafe(32),
            "oauth_version": "1.0",
        }

        if include_token and self.oauth_token:
            params["oauth_token"] = self.oauth_token

        return params

    def _sign_request(
        self,
        method: str,
        url: str,
        params: Dict[str, str],
    ) -> str:
        """Sign an OAuth1 request using HMAC-SHA1.

        Args:
            method: HTTP method (GET, POST, etc.)
            url: Base URL without query parameters
            params: All parameters (OAuth + query params)

        Returns:
            Base64-encoded signature
        """
        # Build signature base string
        sorted_params = sorted(params.items())
        param_str = "&".join(
            f"{self._percent_encode(k)}={self._percent_encode(v)}" for k, v in sorted_params
        )

        base_parts = [
            method.upper(),
            self._percent_encode(url),
            self._percent_encode(param_str),
        ]
        base_string = "&".join(base_parts)

        # Build signing key: consumer_secret&token_secret
        consumer_sec = self.consumer_secret or ""
        token_sec = self.oauth_token_secret or ""
        signing_key = f"{self._percent_encode(consumer_sec)}&{self._percent_encode(token_sec)}"

        # Sign with HMAC-SHA1
        signature_bytes = hmac.new(
            signing_key.encode("utf-8"),
            base_string.encode("utf-8"),
            hashlib.sha1,
        ).digest()

        # Base64 encode
        import base64

        return base64.b64encode(signature_bytes).decode("utf-8")

    def _build_auth_header(self, oauth_params: Dict[str, str]) -> str:
        """Build OAuth1 Authorization header.

        Args:
            oauth_params: OAuth parameters including signature

        Returns:
            Authorization header value
        """
        sorted_items = sorted(oauth_params.items())
        param_strings = [
            f'{self._percent_encode(k)}="{self._percent_encode(v)}"' for k, v in sorted_items
        ]
        return "OAuth " + ", ".join(param_strings)

    @retry(
        stop=stop_after_attempt(5),
        retry=retry_if_rate_limit_or_timeout,
        wait=wait_rate_limit_with_backoff,
        reraise=True,
    )
    async def _get_with_oauth1(
        self,
        client: httpx.AsyncClient,
        url: str,
        query_params: Optional[Dict[str, Any]] = None,
    ) -> Dict:
        """Make authenticated GET request using OAuth1.

        Args:
            client: HTTP client
            url: API endpoint URL
            query_params: Optional query parameters

        Returns:
            JSON response

        Raises:
            httpx.HTTPStatusError: On HTTP errors
        """
        # Build OAuth parameters
        oauth_params = self._build_oauth1_params(include_token=True)

        # Merge with query parameters for signing
        all_params = {**oauth_params}
        if query_params:
            # Convert all query params to strings for signing
            all_params.update({k: str(v) for k, v in query_params.items()})

        # Sign the request
        signature = self._sign_request("GET", url, all_params)
        oauth_params["oauth_signature"] = signature

        # Build Authorization header (only OAuth params)
        auth_header = self._build_auth_header(oauth_params)

        # Make request with query params in URL
        try:
            response = await client.get(
                url,
                headers={"Authorization": auth_header},
                params=query_params,
            )
            response.raise_for_status()
            return response.json()

        except httpx.HTTPStatusError as e:
            self.logger.error(f"HTTP error from Trello API: {e.response.status_code} for {url}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error accessing Trello API: {url}, {str(e)}")
            raise

    @staticmethod
    def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
        """Parse Trello ISO8601 timestamps."""
        if not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None

    async def _generate_board_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate board entities for the authenticated user."""
        # Get boards for the authenticated user
        boards_data = await self._get_with_oauth1(
            client,
            f"{self.API_BASE}/members/me/boards",
            query_params={
                "fields": "id,name,desc,closed,url,shortUrl,prefs,idOrganization,pinned",
            },
        )

        for board in boards_data:
            # Skip if board name matches filter
            if self.board_filter and self.board_filter in board.get("name", ""):
                self.logger.info(f"Skipping filtered board: {board.get('name')}")
                continue

            snapshot_time = datetime.utcnow()
            board_name = board.get("name", "Untitled Board")
            web_url = board.get("url") or board.get("shortUrl")

            yield TrelloBoardEntity(
                # Base fields
                entity_id=board["id"],
                breadcrumbs=[],
                name=board_name,
                created_at=snapshot_time,
                updated_at=snapshot_time,
                # API fields
                trello_id=board["id"],
                board_name=board_name,
                created_time=snapshot_time,
                updated_time=snapshot_time,
                web_url_value=web_url,
                desc=board.get("desc"),
                closed=board.get("closed", False),
                url=board.get("url"),
                short_url=board.get("shortUrl"),
                prefs=board.get("prefs"),
                id_organization=board.get("idOrganization"),
                pinned=board.get("pinned", False),
            )

    async def _generate_list_entities(
        self, client: httpx.AsyncClient, board: Dict, board_breadcrumb: Breadcrumb
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate list entities for a board."""
        lists_data = await self._get_with_oauth1(
            client,
            f"{self.API_BASE}/boards/{board['id']}/lists",
            query_params={"fields": "id,name,closed,pos,idBoard,subscribed"},
        )

        for list_item in lists_data:
            snapshot_time = datetime.utcnow()
            list_name = list_item.get("name", "Untitled List")
            board_url = board.get("shortUrl") or board.get("url")

            yield TrelloListEntity(
                # Base fields
                entity_id=list_item["id"],
                breadcrumbs=[board_breadcrumb],
                name=list_name,
                created_at=snapshot_time,
                updated_at=snapshot_time,
                # API fields
                trello_id=list_item["id"],
                list_name=list_name,
                created_time=snapshot_time,
                updated_time=snapshot_time,
                web_url_value=board_url,
                id_board=list_item["idBoard"],
                board_name=board.get("name", ""),
                closed=list_item.get("closed", False),
                pos=list_item.get("pos"),
                subscribed=list_item.get("subscribed"),
            )

    async def _get_members_for_card(
        self, client: httpx.AsyncClient, card_id: str
    ) -> List[Dict[str, Any]]:
        """Get member details for a card.

        Args:
            client: HTTP client
            card_id: Card ID

        Returns:
            List of member dictionaries
        """
        try:
            members_data = await self._get_with_oauth1(
                client,
                f"{self.API_BASE}/cards/{card_id}/members",
                query_params={"fields": "id,username,fullName,initials,avatarUrl"},
            )
            return members_data
        except Exception as e:
            self.logger.warning(f"Failed to fetch members for card {card_id}: {e}")
            return []

    async def _generate_card_entities(
        self,
        client: httpx.AsyncClient,
        board: Dict,
        list_item: Dict,
        list_breadcrumbs: List[Breadcrumb],
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate card entities for a list."""
        cards_data = await self._get_with_oauth1(
            client,
            f"{self.API_BASE}/lists/{list_item['id']}/cards",
            query_params={
                "fields": "id,name,desc,closed,due,dueComplete,dateLastActivity,"
                "idBoard,idList,idMembers,idLabels,idChecklists,badges,pos,"
                "shortLink,shortUrl,url,start,subscribed,labels"
            },
        )

        for card in cards_data:
            # Fetch member details for the card
            members = await self._get_members_for_card(client, card["id"])

            updated_time = self._parse_datetime(card.get("dateLastActivity")) or datetime.utcnow()
            created_time = (
                self._parse_datetime(card.get("start"))
                or self._parse_datetime(card.get("due"))
                or updated_time
            )
            card_name = card.get("name", "Untitled Card")
            card_web_url = card.get("url") or card.get("shortUrl")

            yield TrelloCardEntity(
                # Base fields
                entity_id=card["id"],
                breadcrumbs=list_breadcrumbs,
                name=card_name,
                created_at=created_time,
                updated_at=updated_time,
                # API fields
                trello_id=card["id"],
                card_name=card_name,
                created_time=created_time,
                updated_time=updated_time,
                web_url_value=card_web_url,
                desc=card.get("desc"),
                id_board=card["idBoard"],
                board_name=board.get("name", ""),
                id_list=card["idList"],
                list_name=list_item.get("name", ""),
                closed=card.get("closed", False),
                due=card.get("due"),
                due_complete=card.get("dueComplete"),
                date_last_activity=card.get("dateLastActivity"),
                id_members=card.get("idMembers", []),
                members=members,
                id_labels=card.get("idLabels", []),
                labels=card.get("labels", []),
                id_checklists=card.get("idChecklists", []),
                badges=card.get("badges"),
                pos=card.get("pos"),
                short_link=card.get("shortLink"),
                short_url=card.get("shortUrl"),
                url=card.get("url"),
                start=card.get("start"),
                subscribed=card.get("subscribed"),
            )

    async def _generate_checklist_entities(
        self,
        client: httpx.AsyncClient,
        card: Dict,
        card_breadcrumbs: List[Breadcrumb],
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate checklist entities for a card."""
        # Get checklists for the card
        checklists_data = await self._get_with_oauth1(
            client,
            f"{self.API_BASE}/cards/{card['id']}/checklists",
            query_params={"fields": "id,name,pos,idBoard,idCard,checkItems"},
        )

        for checklist in checklists_data:
            snapshot_time = datetime.utcnow()
            checklist_name = checklist.get("name", "Checklist")
            web_url = card.get("url") or card.get("shortUrl")

            yield TrelloChecklistEntity(
                # Base fields
                entity_id=checklist["id"],
                breadcrumbs=card_breadcrumbs,
                name=checklist_name,
                created_at=snapshot_time,
                updated_at=snapshot_time,
                # API fields
                trello_id=checklist["id"],
                checklist_name=checklist_name,
                created_time=snapshot_time,
                updated_time=snapshot_time,
                web_url_value=web_url,
                id_board=checklist.get("idBoard", card.get("idBoard", "")),
                id_card=checklist["idCard"],
                card_name=card.get("name", ""),
                pos=checklist.get("pos"),
                check_items=checklist.get("checkItems", []),
            )

    async def _generate_member_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate member entity for the authenticated user."""
        # Get authenticated user's member info
        member_data = await self._get_with_oauth1(
            client,
            f"{self.API_BASE}/members/me",
            query_params={
                "fields": "id,username,fullName,initials,avatarUrl,bio,url,idBoards,memberType"
            },
        )

        # Get member name from full_name or username
        member_name = member_data.get("fullName") or member_data.get("username", "unknown")
        snapshot_time = datetime.utcnow()
        member_url = member_data.get("url")

        yield TrelloMemberEntity(
            # Base fields
            entity_id=member_data["id"],
            breadcrumbs=[],
            name=member_name,
            created_at=snapshot_time,
            updated_at=snapshot_time,
            # API fields
            username=member_data.get("username", "unknown"),
            trello_id=member_data["id"],
            display_name=member_name,
            created_time=snapshot_time,
            updated_time=snapshot_time,
            web_url_value=member_url,
            full_name=member_data.get("fullName"),
            initials=member_data.get("initials"),
            avatar_url=member_data.get("avatarUrl"),
            bio=member_data.get("bio"),
            url=member_url,
            id_boards=member_data.get("idBoards", []),
            member_type=member_data.get("memberType"),
        )

    async def generate_entities(self) -> AsyncGenerator[BaseEntity, None]:
        """Generate all entities from Trello.

        Hierarchy: Board → List → Card → Checklist
        Also generates: Member (authenticated user)
        """
        self.logger.info("Starting Trello sync")

        async with self.http_client() as client:
            # Generate authenticated user's member entity
            async for member_entity in self._generate_member_entities(client):
                yield member_entity

            # Generate board entities
            async for board_entity in self._generate_board_entities(client):
                self.logger.debug(f"Processing board: {board_entity.name}")
                yield board_entity

                board_breadcrumb = Breadcrumb(
                    entity_id=board_entity.entity_id,
                    name=board_entity.name,
                    entity_type=TrelloBoardEntity.__name__,
                )

                # Generate lists for this board
                async for list_entity in self._generate_list_entities(
                    client,
                    {
                        "id": board_entity.entity_id,
                        "name": board_entity.name,
                        "url": getattr(board_entity, "url", None),
                        "shortUrl": getattr(board_entity, "short_url", None),
                    },
                    board_breadcrumb,
                ):
                    self.logger.debug(f"Processing list: {list_entity.name}")
                    yield list_entity

                    list_breadcrumb = Breadcrumb(
                        entity_id=list_entity.entity_id,
                        name=list_entity.name,
                        entity_type=TrelloListEntity.__name__,
                    )
                    list_breadcrumbs = [board_breadcrumb, list_breadcrumb]

                    # Generate cards for this list
                    async for card_entity in self._generate_card_entities(
                        client,
                        {"id": board_entity.entity_id, "name": board_entity.name},
                        {
                            "id": list_entity.entity_id,
                            "name": list_entity.name,
                            "url": getattr(list_entity, "web_url", None),
                        },
                        list_breadcrumbs,
                    ):
                        self.logger.debug(f"Processing card: {card_entity.name}")
                        yield card_entity

                        # Generate checklists for this card
                        card_breadcrumb = Breadcrumb(
                            entity_id=card_entity.entity_id,
                            name=card_entity.name,
                            entity_type=TrelloCardEntity.__name__,
                        )
                        card_breadcrumbs = [*list_breadcrumbs, card_breadcrumb]

                        async for checklist_entity in self._generate_checklist_entities(
                            client,
                            {
                                "id": card_entity.entity_id,
                                "name": card_entity.name,
                                "idBoard": card_entity.id_board,
                                "url": getattr(card_entity, "web_url", None),
                                "shortUrl": getattr(card_entity, "short_url", None),
                            },
                            card_breadcrumbs,
                        ):
                            self.logger.debug(f"Processing checklist: {checklist_entity.name}")
                            yield checklist_entity

        self.logger.info("Trello sync completed")

    async def validate(self) -> bool:
        """Verify OAuth1 credentials by calling the /members/me endpoint.

        Returns:
            True if credentials are valid, False otherwise
        """
        try:
            async with self.http_client() as client:
                await self._get_with_oauth1(
                    client,
                    f"{self.API_BASE}/members/me",
                    query_params={"fields": "id,username"},
                )
            return True
        except Exception as e:
            self.logger.error(f"OAuth1 validation failed: {str(e)}")
            return False
