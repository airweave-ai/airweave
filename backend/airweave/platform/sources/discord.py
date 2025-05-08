"""Discord source implementation."""

import logging
from typing import AsyncGenerator, Dict, Any
import httpx
from tenacity import retry, wait_exponential, stop_after_attempt

from airweave.platform.auth.schemas import AuthType
from airweave.platform.decorators import source
from airweave.platform.entities.discord import DiscordUserEntity
from airweave.platform.sources._base import BaseSource

logger = logging.getLogger(__name__)


@source("Discord", "discord", AuthType.oauth2)
class DiscordSource(BaseSource):
    """Discord source integration for fetching user profile."""

    BASE_URL = "https://discord.com/api/v10"

    @classmethod
    async def create(cls, access_token: str) -> "DiscordSource":
        instance = cls()
        instance.access_token = access_token
        return instance

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), reraise=True)
    async def _make_request(self, endpoint: str) -> Dict[str, Any]:
        """Make an authenticated request to Discord API."""
        url = f"{self.BASE_URL}{endpoint}"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=headers)
            logger.debug(f"Request to {url}")
            response.raise_for_status()
            return response.json()

    async def generate_entities(self) -> AsyncGenerator[Any, None]:
        """Generate Discord user entities."""
        user_data = await self._make_request("/users/@me")
        yield DiscordUserEntity(
            entity_id=str(user_data["id"]),
            username=user_data.get("username", ""),
            email=user_data.get("email"),
        )