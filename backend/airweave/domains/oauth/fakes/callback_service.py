"""Fake OAuthCallbackService for testing."""

from typing import Any, List, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from airweave.schemas.source_connection import SourceConnection as SourceConnectionSchema


class FakeOAuthCallbackService:
    """In-memory fake for OAuthCallbackServiceProtocol."""

    def __init__(self) -> None:
        self._calls: List[Tuple[str, ...]] = []
        self._oauth2_result: Optional[SourceConnectionSchema] = None
        self._oauth1_result: Optional[SourceConnectionSchema] = None

    def seed_oauth2_result(self, result: SourceConnectionSchema) -> None:
        self._oauth2_result = result

    def seed_oauth1_result(self, result: SourceConnectionSchema) -> None:
        self._oauth1_result = result

    async def complete_oauth2_callback(
        self,
        db: AsyncSession,
        *,
        state: str,
        code: str,
    ) -> SourceConnectionSchema:
        self._calls.append(("complete_oauth2_callback", state, code))
        if self._oauth2_result:
            return self._oauth2_result
        raise ValueError("FakeOAuthCallbackService: seed_oauth2_result not called")

    async def complete_oauth1_callback(
        self,
        db: AsyncSession,
        *,
        oauth_token: str,
        oauth_verifier: str,
    ) -> SourceConnectionSchema:
        self._calls.append(("complete_oauth1_callback", oauth_token, oauth_verifier))
        if self._oauth1_result:
            return self._oauth1_result
        raise ValueError("FakeOAuthCallbackService: seed_oauth1_result not called")
