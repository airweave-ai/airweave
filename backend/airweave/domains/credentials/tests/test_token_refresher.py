"""Unit tests for TokenRefresher (stateful timer/lock wrapper)."""

import time
from unittest.mock import MagicMock

import pytest

from airweave.core.exceptions import TokenRefreshError
from airweave.domains.credentials.fakes.refresher import FakeCredentialRefresher
from airweave.domains.credentials.token_refresher import (
    REFRESH_INTERVAL_SECONDS,
    TokenRefresher,
)


def _logger():
    m = MagicMock()
    m.info = MagicMock()
    m.debug = MagicMock()
    m.warning = MagicMock()
    m.error = MagicMock()
    return m


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


class TestTokenRefresherConstruction:
    def test_no_refresher_means_cannot_refresh(self):
        tr = TokenRefresher(initial_token="tok", source_short_name="x")
        assert not tr.can_refresh

    def test_with_refresher_means_can_refresh(self):
        tr = TokenRefresher(
            initial_token="tok",
            refresher=FakeCredentialRefresher(),
            source_short_name="x",
        )
        assert tr.can_refresh


# ---------------------------------------------------------------------------
# get_valid_token
# ---------------------------------------------------------------------------


class TestGetValidToken:
    @pytest.mark.asyncio
    async def test_returns_initial_token_when_no_refresher(self):
        tr = TokenRefresher(initial_token="static-tok", source_short_name="x")
        assert await tr.get_valid_token() == "static-tok"

    @pytest.mark.asyncio
    async def test_refreshes_on_first_call(self):
        fake = FakeCredentialRefresher(token="fresh-tok")
        tr = TokenRefresher(
            initial_token="old-tok",
            refresher=fake,
            source_short_name="x",
            logger=_logger(),
        )
        token = await tr.get_valid_token()
        assert token == "fresh-tok"
        assert fake.call_count == 1

    @pytest.mark.asyncio
    async def test_does_not_refresh_within_interval(self):
        fake = FakeCredentialRefresher(token="fresh-tok")
        tr = TokenRefresher(
            initial_token="old-tok",
            refresher=fake,
            source_short_name="x",
            logger=_logger(),
        )
        await tr.get_valid_token()
        await tr.get_valid_token()
        await tr.get_valid_token()
        assert fake.call_count == 1

    @pytest.mark.asyncio
    async def test_falls_back_to_current_token_on_failure(self):
        fake = FakeCredentialRefresher(fail=True)
        tr = TokenRefresher(
            initial_token="fallback-tok",
            refresher=fake,
            source_short_name="x",
            logger=_logger(),
        )
        token = await tr.get_valid_token()
        assert token == "fallback-tok"
        assert not tr.can_refresh

    @pytest.mark.asyncio
    async def test_refreshes_after_interval_expires(self):
        fake = FakeCredentialRefresher(token="fresh-tok")
        tr = TokenRefresher(
            initial_token="old-tok",
            refresher=fake,
            source_short_name="x",
            logger=_logger(),
        )
        await tr.get_valid_token()
        assert fake.call_count == 1

        # Simulate time passing beyond the refresh interval
        tr._last_refresh_time = time.time() - REFRESH_INTERVAL_SECONDS - 1
        await tr.get_valid_token()
        assert fake.call_count == 2


# ---------------------------------------------------------------------------
# refresh_on_unauthorized
# ---------------------------------------------------------------------------


class TestRefreshOnUnauthorized:
    @pytest.mark.asyncio
    async def test_raises_when_no_refresher(self):
        tr = TokenRefresher(initial_token="tok", source_short_name="x")
        with pytest.raises(TokenRefreshError, match="not supported"):
            await tr.refresh_on_unauthorized()

    @pytest.mark.asyncio
    async def test_returns_fresh_token(self):
        fake = FakeCredentialRefresher(token="401-fresh")
        tr = TokenRefresher(
            initial_token="old",
            refresher=fake,
            source_short_name="x",
            logger=_logger(),
        )
        token = await tr.refresh_on_unauthorized()
        assert token == "401-fresh"
        assert fake.call_count == 1

    @pytest.mark.asyncio
    async def test_raises_on_refresh_failure(self):
        fake = FakeCredentialRefresher(fail=True)
        tr = TokenRefresher(
            initial_token="old",
            refresher=fake,
            source_short_name="x",
            logger=_logger(),
        )
        with pytest.raises(TokenRefreshError, match="after 401"):
            await tr.refresh_on_unauthorized()
