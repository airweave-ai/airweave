"""Unit tests for OAuth1Service.

Covers:
- _generate_nonce (length, uniqueness)
- _percent_encode (RFC 3986 compliance)
- _build_signature_base_string (known vectors)
- _sign_hmac_sha1 (known vectors)
- _build_authorization_header (format)
- get_request_token (happy path with mocked httpx, error cases)
- exchange_token (happy path with mocked httpx, error cases)
- build_authorization_url (with/without optional params)

Uses table-driven @dataclass cases wherever possible.
"""

import base64
import hashlib
import hmac
from dataclasses import dataclass, field
from typing import Optional
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from airweave.core.logging import logger
from airweave.domains.oauth.oauth1_service import OAuth1Service
from airweave.domains.oauth.types import OAuth1TokenResponse


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _svc() -> OAuth1Service:
    return OAuth1Service()


def _logger():
    return logger.with_context(request_id="test-oauth1")


def _mock_httpx(response: httpx.Response):
    """Context manager that patches httpx.AsyncClient to return `response`."""
    patcher = patch("airweave.domains.oauth.oauth1_service.httpx.AsyncClient")

    class _Ctx:
        def __enter__(self):
            mock_cls = patcher.start()
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client
            return mock_client

        def __exit__(self, *args):
            patcher.stop()

    return _Ctx()


# ===========================================================================
# _generate_nonce
# ===========================================================================


def test_nonce_length_is_nonzero():
    assert len(_svc()._generate_nonce()) > 0


def test_nonce_uniqueness():
    nonces = {_svc()._generate_nonce() for _ in range(100)}
    assert len(nonces) == 100


# ===========================================================================
# _percent_encode — RFC 3986 (table-driven)
# ===========================================================================


@dataclass
class PercentEncodeCase:
    desc: str
    input_val: str
    expected: str


PERCENT_ENCODE_CASES = [
    PercentEncodeCase("plain ascii", "abc", "abc"),
    PercentEncodeCase("space", "hello world", "hello%20world"),
    PercentEncodeCase("tilde unreserved", "~", "~"),
    PercentEncodeCase("plus sign", "a+b", "a%2Bb"),
    PercentEncodeCase("percent literal", "100%", "100%25"),
    PercentEncodeCase("slash", "foo/bar", "foo%2Fbar"),
    PercentEncodeCase("ampersand and equals", "a=1&b=2", "a%3D1%26b%3D2"),
    PercentEncodeCase("unicode", "naïve", "na%C3%AFve"),
    PercentEncodeCase("empty string", "", ""),
]


@pytest.mark.parametrize("case", PERCENT_ENCODE_CASES, ids=lambda c: c.desc)
def test_percent_encode(case: PercentEncodeCase):
    assert _svc()._percent_encode(case.input_val) == case.expected


# ===========================================================================
# _build_signature_base_string (table-driven)
# ===========================================================================


@dataclass
class SigBaseCase:
    desc: str
    method: str
    url: str
    params: dict
    expect_prefix: str
    expect_params_sorted: bool = False


SIG_BASE_CASES = [
    SigBaseCase(
        "POST uppercase preserved",
        "POST",
        "https://api.example.com/oauth/request_token",
        {"oauth_consumer_key": "key1", "oauth_nonce": "nonce1"},
        "POST&",
    ),
    SigBaseCase(
        "get normalised to GET",
        "get",
        "https://api.example.com/resource",
        {"a": "1", "b": "2"},
        "GET&",
    ),
    SigBaseCase(
        "params sorted alphabetically",
        "POST",
        "https://example.com",
        {"z_param": "z_val", "a_param": "a_val"},
        "POST&",
        expect_params_sorted=True,
    ),
]


@pytest.mark.parametrize("case", SIG_BASE_CASES, ids=lambda c: c.desc)
def test_build_signature_base_string(case: SigBaseCase):
    svc = _svc()
    result = svc._build_signature_base_string(case.method, case.url, case.params)
    assert result.startswith(case.expect_prefix)
    if case.expect_params_sorted:
        parts = result.split("&", 2)
        expected_param_str = svc._percent_encode("a_param=a_val&z_param=z_val")
        assert parts[2] == expected_param_str


# ===========================================================================
# _sign_hmac_sha1 (table-driven)
# ===========================================================================


def _expected_hmac(base: str, consumer_secret: str, token_secret: str) -> str:
    svc = _svc()
    key = f"{svc._percent_encode(consumer_secret)}&{svc._percent_encode(token_secret)}"
    sig = hmac.new(key.encode("utf-8"), base.encode("utf-8"), hashlib.sha1).digest()
    return base64.b64encode(sig).decode("utf-8")


@dataclass
class HmacCase:
    desc: str
    base_string: str
    consumer_secret: str
    token_secret: str


HMAC_CASES = [
    HmacCase(
        "with token secret",
        "POST&https%3A%2F%2Fexample.com&oauth_consumer_key%3Dkey",
        "secret",
        "token_secret",
    ),
    HmacCase(
        "empty token secret (request-token step)",
        "GET&https%3A%2F%2Fexample.com&param%3Dval",
        "consumer",
        "",
    ),
    HmacCase(
        "special chars in secrets",
        "POST&https%3A%2F%2Fexample.com&p%3D1",
        "sec&ret",
        "tok/sec",
    ),
]


@pytest.mark.parametrize("case", HMAC_CASES, ids=lambda c: c.desc)
def test_sign_hmac_sha1(case: HmacCase):
    expected = _expected_hmac(case.base_string, case.consumer_secret, case.token_secret)
    assert _svc()._sign_hmac_sha1(
        case.base_string, case.consumer_secret, case.token_secret
    ) == expected


# ===========================================================================
# _build_authorization_header (table-driven)
# ===========================================================================


@dataclass
class AuthHeaderCase:
    desc: str
    params: dict
    expect_contains: list = field(default_factory=list)
    expect_sorted: bool = False


AUTH_HEADER_CASES = [
    AuthHeaderCase(
        "standard OAuth params",
        {"oauth_consumer_key": "mykey", "oauth_nonce": "mynonce"},
        ['oauth_consumer_key="mykey"', 'oauth_nonce="mynonce"'],
    ),
    AuthHeaderCase(
        "params sorted alphabetically",
        {"z_key": "z_val", "a_key": "a_val"},
        [],
        expect_sorted=True,
    ),
]


@pytest.mark.parametrize("case", AUTH_HEADER_CASES, ids=lambda c: c.desc)
def test_build_authorization_header(case: AuthHeaderCase):
    header = _svc()._build_authorization_header(case.params)
    assert header.startswith("OAuth ")
    for fragment in case.expect_contains:
        assert fragment in header
    if case.expect_sorted:
        a_pos = header.index("a_key")
        z_pos = header.index("z_key")
        assert a_pos < z_pos


# ===========================================================================
# get_request_token (table-driven)
# ===========================================================================


@dataclass
class GetRequestTokenCase:
    desc: str
    response_status: int
    response_body: str
    expect_success: bool
    expect_token: Optional[str] = None
    expect_secret: Optional[str] = None
    expect_extra: Optional[dict] = None


GET_REQUEST_TOKEN_CASES = [
    GetRequestTokenCase(
        "happy path — valid response",
        200,
        "oauth_token=req_tok&oauth_token_secret=req_sec&extra=val",
        True,
        expect_token="req_tok",
        expect_secret="req_sec",
        expect_extra={"extra": "val"},
    ),
    GetRequestTokenCase(
        "200 but missing oauth_token — error",
        200,
        "some_other_param=value",
        False,
    ),
    GetRequestTokenCase(
        "401 HTTP error",
        401,
        "Unauthorized",
        False,
    ),
    GetRequestTokenCase(
        "500 server error",
        500,
        "Internal Server Error",
        False,
    ),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("case", GET_REQUEST_TOKEN_CASES, ids=lambda c: c.desc)
async def test_get_request_token(case: GetRequestTokenCase):
    resp = httpx.Response(
        case.response_status,
        text=case.response_body,
        request=httpx.Request("POST", "https://provider.com/oauth/request_token"),
    )

    with _mock_httpx(resp):
        if case.expect_success:
            result = await _svc().get_request_token(
                request_token_url="https://provider.com/oauth/request_token",
                consumer_key="ck",
                consumer_secret="cs",
                callback_url="https://app.com/callback",
                logger=_logger(),
            )
            assert isinstance(result, OAuth1TokenResponse)
            assert result.oauth_token == case.expect_token
            assert result.oauth_token_secret == case.expect_secret
            if case.expect_extra is not None:
                assert result.additional_params == case.expect_extra
        else:
            with pytest.raises(Exception) as exc_info:
                await _svc().get_request_token(
                    request_token_url="https://provider.com/oauth/request_token",
                    consumer_key="ck",
                    consumer_secret="cs",
                    callback_url="https://app.com/callback",
                    logger=_logger(),
                )
            assert exc_info.value.status_code == 400


# ===========================================================================
# exchange_token (table-driven)
# ===========================================================================


@dataclass
class ExchangeTokenCase:
    desc: str
    response_status: int
    response_body: str
    expect_success: bool
    expect_token: Optional[str] = None
    expect_secret: Optional[str] = None
    expect_extra: Optional[dict] = None


EXCHANGE_TOKEN_CASES = [
    ExchangeTokenCase(
        "happy path — valid access token",
        200,
        "oauth_token=access_tok&oauth_token_secret=access_sec&user_id=123",
        True,
        expect_token="access_tok",
        expect_secret="access_sec",
        expect_extra={"user_id": "123"},
    ),
    ExchangeTokenCase(
        "200 but missing tokens — error",
        200,
        "user_id=123",
        False,
    ),
    ExchangeTokenCase(
        "403 forbidden",
        403,
        "Forbidden",
        False,
    ),
    ExchangeTokenCase(
        "502 bad gateway",
        502,
        "Bad Gateway",
        False,
    ),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("case", EXCHANGE_TOKEN_CASES, ids=lambda c: c.desc)
async def test_exchange_token(case: ExchangeTokenCase):
    resp = httpx.Response(
        case.response_status,
        text=case.response_body,
        request=httpx.Request("POST", "https://provider.com/oauth/access_token"),
    )

    with _mock_httpx(resp):
        if case.expect_success:
            result = await _svc().exchange_token(
                access_token_url="https://provider.com/oauth/access_token",
                consumer_key="ck",
                consumer_secret="cs",
                oauth_token="req_tok",
                oauth_token_secret="req_sec",
                oauth_verifier="verifier123",
                logger=_logger(),
            )
            assert isinstance(result, OAuth1TokenResponse)
            assert result.oauth_token == case.expect_token
            assert result.oauth_token_secret == case.expect_secret
            if case.expect_extra is not None:
                assert result.additional_params == case.expect_extra
        else:
            with pytest.raises(Exception) as exc_info:
                await _svc().exchange_token(
                    access_token_url="https://provider.com/oauth/access_token",
                    consumer_key="ck",
                    consumer_secret="cs",
                    oauth_token="req_tok",
                    oauth_token_secret="req_sec",
                    oauth_verifier="verifier123",
                    logger=_logger(),
                )
            assert exc_info.value.status_code == 400


# ===========================================================================
# build_authorization_url (table-driven)
# ===========================================================================


@dataclass
class AuthUrlCase:
    desc: str
    kwargs: dict
    expect_contains: list = field(default_factory=list)
    expect_not_contains: list = field(default_factory=list)


AUTH_URL_CASES = [
    AuthUrlCase(
        "minimal — token only",
        {
            "authorization_url": "https://provider.com/authorize",
            "oauth_token": "tok123",
        },
        ["oauth_token=tok123"],
        ["name=", "scope=", "expiration="],
    ),
    AuthUrlCase(
        "all optional params",
        {
            "authorization_url": "https://provider.com/authorize",
            "oauth_token": "tok123",
            "app_name": "MyApp",
            "scope": "read,write",
            "expiration": "never",
        },
        ["oauth_token=tok123", "name=MyApp", "scope=read", "expiration=never"],
    ),
    AuthUrlCase(
        "partial — scope only",
        {
            "authorization_url": "https://provider.com/authorize",
            "oauth_token": "tok123",
            "scope": "read",
        },
        ["oauth_token=tok123", "scope=read"],
        ["name=", "expiration="],
    ),
    AuthUrlCase(
        "partial — app_name only",
        {
            "authorization_url": "https://provider.com/authorize",
            "oauth_token": "tok123",
            "app_name": "TestApp",
        },
        ["oauth_token=tok123", "name=TestApp"],
        ["scope=", "expiration="],
    ),
]


@pytest.mark.parametrize("case", AUTH_URL_CASES, ids=lambda c: c.desc)
def test_build_authorization_url(case: AuthUrlCase):
    url = _svc().build_authorization_url(**case.kwargs)
    assert url.startswith(case.kwargs["authorization_url"])
    for fragment in case.expect_contains:
        assert fragment in url
    for fragment in case.expect_not_contains:
        assert fragment not in url
