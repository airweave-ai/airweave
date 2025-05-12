"""Discord entity definitions for Airweave."""

from typing import Optional
from pydantic import Field
from airweave.platform.entities._base import ChunkEntity


class DiscordUserEntity(ChunkEntity):
    """Discord User Entity."""

    entity_id: str = Field(..., description="Discord User ID")
    username: str = Field(..., description="Username of the Discord user")
    email: Optional[str] = Field(None, description="Email of the Discord user")