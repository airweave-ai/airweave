"""CRUD operations for OAuth Client model."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import schemas
from airweave.core.exceptions import NotFoundException
from airweave.crud._base_public import CRUDPublic
from airweave.models.oauth_client import OAuthClient


class CRUDOAuthClient(CRUDPublic[OAuthClient, schemas.OAuthClientCreate, schemas.OAuthClientUpdate]):
    """CRUD operations for OAuth clients."""

    async def get_by_client_id(self, db: AsyncSession, *, client_id: str) -> OAuthClient:
        """Get OAuth client by client_id.

        Args:
            db: Database session
            client_id: OAuth client ID

        Returns:
            OAuthClient model

        Raises:
            NotFoundException: If client not found
        """
        query = select(OAuthClient).where(OAuthClient.client_id == client_id)
        result = await db.execute(query)
        client = result.scalar_one_or_none()
        
        if not client:
            raise NotFoundException(f"OAuth client with client_id {client_id} not found")
        
        return client

    def validate_redirect_uri(self, client: OAuthClient, redirect_uri: str) -> bool:
        """Validate that redirect_uri is allowed for this client.

        Args:
            client: OAuth client model
            redirect_uri: Redirect URI to validate

        Returns:
            True if valid, False otherwise
        """
        return redirect_uri in client.redirect_uris


oauth_client = CRUDOAuthClient(OAuthClient)
