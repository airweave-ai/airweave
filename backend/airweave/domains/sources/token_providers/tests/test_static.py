"""Unit tests for StaticTokenProvider.

StaticTokenProvider is the simplest provider: holds a fixed string,
never refreshes. Tests verify the contract and edge cases.
"""

from dataclasses import dataclass

import pytest

from airweave.domains.sources.token_providers.exceptions import TokenRefreshNotSupportedError
from airweave.domains.sources.token_providers.protocol import AuthProviderKind
from airweave.domains.sources.token_providers.static import StaticTokenProvider


# ---------------------------------------------------------------------------
# Construction — table-driven
# ---------------------------------------------------------------------------


@dataclass
class ConstructCase:
    id: str
    token: str
    expect_error: bool = False


CONSTRUCT_TABLE = [
    ConstructCase(id="valid-token", token="sk-abc123"),
    ConstructCase(id="empty-string-rejected", token="", expect_error=True),
]


@pytest.mark.parametrize("case", CONSTRUCT_TABLE, ids=lambda c: c.id)
def test_construction(case: ConstructCase):
    if case.expect_error:
        with pytest.raises(ValueError, match="non-empty"):
            StaticTokenProvider(case.token)
    else:
        p = StaticTokenProvider(case.token, source_short_name="test")
        assert p.provider_kind == AuthProviderKind.STATIC
        assert p.supports_refresh is False


# ---------------------------------------------------------------------------
# get_token — always returns the same value
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_token_returns_fixed_value():
    p = StaticTokenProvider("my-api-key")
    assert await p.get_token() == "my-api-key"
    assert await p.get_token() == "my-api-key"


# ---------------------------------------------------------------------------
# force_refresh — always raises
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_force_refresh_raises():
    p = StaticTokenProvider("tok", source_short_name="github")
    with pytest.raises(TokenRefreshNotSupportedError) as exc_info:
        await p.force_refresh()
    assert exc_info.value.source_short_name == "github"
    assert exc_info.value.provider_kind == AuthProviderKind.STATIC


# ---------------------------------------------------------------------------
# Protocol compliance
# ---------------------------------------------------------------------------


def test_implements_token_provider_protocol():
    from airweave.domains.sources.token_providers.protocol import TokenProviderProtocol

    p = StaticTokenProvider("tok")
    assert isinstance(p, TokenProviderProtocol)
