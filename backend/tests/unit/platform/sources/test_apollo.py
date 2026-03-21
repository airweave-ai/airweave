"""Tests for the Apollo source — v2 contract, pagination, 403 handling."""

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from airweave.domains.sources.exceptions import SourceAuthError, SourceEntityForbiddenError
from airweave.platform.configs.config import ApolloConfig
from airweave.platform.entities.apollo import (
    ApolloAccountEntity,
    ApolloContactEntity,
    ApolloEmailActivityEntity,
    ApolloSequenceEntity,
)
from airweave.platform.sources.apollo import ApolloSource
from airweave.schemas.source_connection import AuthenticationMethod


def _mock_auth(api_key: str = "test_apollo_api_key_12345"):
    """Mock a DirectCredentialProvider[ApolloAuthConfig] for tests."""
    from airweave.domains.sources.token_providers.credential import DirectCredentialProvider

    creds = MagicMock()
    creds.api_key = api_key
    return DirectCredentialProvider(creds, source_short_name="apollo")


def _mock_http_client():
    client = AsyncMock()
    client.get = AsyncMock()
    client.post = AsyncMock()
    return client


def _mock_logger():
    return MagicMock()


def _ok_response(data: dict, method: str = "POST", url: str = "https://api.apollo.io/api/v1/accounts/search") -> httpx.Response:
    import json

    return httpx.Response(
        status_code=200,
        content=json.dumps(data).encode(),
        request=httpx.Request(method, url),
    )


def _error_response(status_code: int, data: dict = None, method: str = "POST", url: str = "https://api.apollo.io/api/v1/accounts/search") -> httpx.Response:
    import json

    return httpx.Response(
        status_code=status_code,
        content=json.dumps(data or {}).encode(),
        request=httpx.Request(method, url),
    )


# ---------------------------------------------------------------------------
# Create contract
# ---------------------------------------------------------------------------


class TestCreateContract:
    """Tests for ApolloSource.create() — v2 contract."""

    @pytest.mark.asyncio
    async def test_create_returns_instance(self):
        source = await ApolloSource.create(
            auth=_mock_auth(),
            logger=_mock_logger(),
            http_client=_mock_http_client(),
            config=ApolloConfig(),
        )
        assert isinstance(source, ApolloSource)

    @pytest.mark.asyncio
    async def test_create_requires_auth(self):
        with pytest.raises(TypeError):
            await ApolloSource.create(
                logger=_mock_logger(),
                http_client=_mock_http_client(),
                config=ApolloConfig(),
            )

    @pytest.mark.asyncio
    async def test_create_requires_logger(self):
        with pytest.raises(TypeError):
            await ApolloSource.create(
                auth=_mock_auth(),
                http_client=_mock_http_client(),
                config=ApolloConfig(),
            )

    @pytest.mark.asyncio
    async def test_create_requires_http_client(self):
        with pytest.raises(TypeError):
            await ApolloSource.create(
                auth=_mock_auth(),
                logger=_mock_logger(),
                config=ApolloConfig(),
            )

    @pytest.mark.asyncio
    async def test_auth_accessible_via_property(self):
        auth = _mock_auth()
        source = await ApolloSource.create(
            auth=auth,
            logger=_mock_logger(),
            http_client=_mock_http_client(),
            config=ApolloConfig(),
        )
        assert source.auth is auth

    @pytest.mark.asyncio
    async def test_http_client_accessible_via_property(self):
        client = _mock_http_client()
        source = await ApolloSource.create(
            auth=_mock_auth(),
            logger=_mock_logger(),
            http_client=client,
            config=ApolloConfig(),
        )
        assert source.http_client is client


# ---------------------------------------------------------------------------
# Headers
# ---------------------------------------------------------------------------


class TestHeaders:
    """Tests for ApolloSource._headers() — uses auth.get_token()."""

    @pytest.mark.asyncio
    async def test_headers_include_api_key(self):
        source = await ApolloSource.create(
            auth=_mock_auth("my-key"),
            logger=_mock_logger(),
            http_client=_mock_http_client(),
            config=ApolloConfig(),
        )
        headers = source._headers()
        assert headers["x-api-key"] == "my-key"
        assert "application/json" in headers["Content-Type"]
        assert "application/json" in headers["Accept"]


# ---------------------------------------------------------------------------
# HTTP methods
# ---------------------------------------------------------------------------


class TestPost:
    """Tests for ApolloSource._post() — authenticated POST with raise_for_status."""

    @pytest.mark.asyncio
    async def test_post_sends_auth_header(self):
        client = _mock_http_client()
        client.post.return_value = _ok_response({"accounts": []})

        source = await ApolloSource.create(
            auth=_mock_auth(),
            logger=_mock_logger(),
            http_client=client,
            config=ApolloConfig(),
        )
        await source._post("https://api.apollo.io/api/v1/accounts/search", {"page": 1})

        call_kwargs = client.post.call_args
        assert call_kwargs.kwargs["headers"]["x-api-key"] == "test_apollo_api_key_12345"

    @pytest.mark.asyncio
    async def test_post_raises_source_auth_on_401(self):
        client = _mock_http_client()
        client.post.return_value = _error_response(401, {"error": "Unauthorized"})

        source = await ApolloSource.create(
            auth=_mock_auth(),
            logger=_mock_logger(),
            http_client=client,
            config=ApolloConfig(),
        )
        with pytest.raises(SourceAuthError) as exc_info:
            await source._post("https://api.apollo.io/api/v1/test")
        assert exc_info.value.status_code == 401


class TestGet:
    """Tests for ApolloSource._get() — authenticated GET with raise_for_status."""

    @pytest.mark.asyncio
    async def test_get_sends_auth_header(self):
        client = _mock_http_client()
        client.get.return_value = _ok_response({"emailer_messages": []}, method="GET")

        source = await ApolloSource.create(
            auth=_mock_auth(),
            logger=_mock_logger(),
            http_client=client,
            config=ApolloConfig(),
        )
        await source._get("https://api.apollo.io/api/v1/emailer_messages/search")

        call_kwargs = client.get.call_args
        assert call_kwargs.kwargs["headers"]["x-api-key"] == "test_apollo_api_key_12345"


# ---------------------------------------------------------------------------
# Entity generation: accounts
# ---------------------------------------------------------------------------


class TestGenerateAccounts:

    @pytest.mark.asyncio
    async def test_yields_account_entity(self):
        client = _mock_http_client()
        client.post.return_value = _ok_response({
            "accounts": [
                {
                    "id": "acc_abc",
                    "name": "Acme Corp",
                    "domain": "acme.com",
                    "created_at": "2024-01-15T10:00:00Z",
                    "num_contacts": 5,
                }
            ],
            "pagination": {"total_pages": 1},
        })

        source = await ApolloSource.create(
            auth=_mock_auth(),
            logger=_mock_logger(),
            http_client=client,
            config=ApolloConfig(),
        )
        entities = [e async for e in source._generate_accounts()]

        assert len(entities) == 1
        ent = entities[0]
        assert isinstance(ent, ApolloAccountEntity)
        assert ent.entity_id == "acc_abc"
        assert ent.name == "Acme Corp"
        assert ent.domain == "acme.com"
        assert ent.num_contacts == 5
        assert ent.web_url_value == "https://app.apollo.io/accounts/acc_abc"

    @pytest.mark.asyncio
    async def test_skips_items_without_id(self):
        client = _mock_http_client()
        client.post.return_value = _ok_response({
            "accounts": [
                {"name": "No Id", "domain": "x.com"},
                {"id": "acc_only", "name": "With Id"},
            ],
            "pagination": {"total_pages": 1},
        })

        source = await ApolloSource.create(
            auth=_mock_auth(),
            logger=_mock_logger(),
            http_client=client,
            config=ApolloConfig(),
        )
        entities = [e async for e in source._generate_accounts()]

        assert len(entities) == 1
        assert entities[0].entity_id == "acc_only"


# ---------------------------------------------------------------------------
# Entity generation: contacts
# ---------------------------------------------------------------------------


class TestGenerateContacts:

    @pytest.mark.asyncio
    async def test_yields_contact_with_breadcrumb(self):
        client = _mock_http_client()
        client.post.return_value = _ok_response({
            "contacts": [
                {
                    "id": "con_123",
                    "first_name": "Jane",
                    "last_name": "Doe",
                    "email": "jane@acme.com",
                    "account_id": "acc_abc",
                    "account": {"name": "Acme Corp"},
                }
            ],
            "pagination": {"total_pages": 1},
        })

        source = await ApolloSource.create(
            auth=_mock_auth(),
            logger=_mock_logger(),
            http_client=client,
            config=ApolloConfig(),
        )
        entities = [e async for e in source._generate_contacts()]

        assert len(entities) == 1
        ent = entities[0]
        assert isinstance(ent, ApolloContactEntity)
        assert ent.entity_id == "con_123"
        assert ent.name == "Jane Doe"
        assert ent.email == "jane@acme.com"
        assert ent.account_id == "acc_abc"
        assert ent.account_name == "Acme Corp"
        assert len(ent.breadcrumbs) == 1
        assert ent.breadcrumbs[0].entity_id == "acc_abc"
        assert ent.breadcrumbs[0].entity_type == "ApolloAccountEntity"


# ---------------------------------------------------------------------------
# Entity generation: sequences (403 handling)
# ---------------------------------------------------------------------------


class TestGenerateSequences:

    @pytest.mark.asyncio
    async def test_403_skips_without_raise(self):
        """On 403, sequences are silently skipped (master key required)."""
        client = _mock_http_client()
        client.post.return_value = _error_response(403, {"error": "Forbidden"})

        source = await ApolloSource.create(
            auth=_mock_auth(),
            logger=_mock_logger(),
            http_client=client,
            config=ApolloConfig(),
        )
        entities = [e async for e in source._generate_sequences()]
        assert len(entities) == 0

    @pytest.mark.asyncio
    async def test_yields_entity_when_authorized(self):
        client = _mock_http_client()
        client.post.return_value = _ok_response({
            "emailer_campaigns": [
                {
                    "id": "seq_xyz",
                    "name": "Outreach Q1",
                    "active": True,
                    "num_steps": 3,
                }
            ],
            "pagination": {"total_pages": 1},
        })

        source = await ApolloSource.create(
            auth=_mock_auth(),
            logger=_mock_logger(),
            http_client=client,
            config=ApolloConfig(),
        )
        entities = [e async for e in source._generate_sequences()]

        assert len(entities) == 1
        ent = entities[0]
        assert isinstance(ent, ApolloSequenceEntity)
        assert ent.entity_id == "seq_xyz"
        assert ent.name == "Outreach Q1"
        assert ent.active is True
        assert ent.num_steps == 3


# ---------------------------------------------------------------------------
# Entity generation: email activities (403 handling)
# ---------------------------------------------------------------------------


class TestGenerateEmailActivities:

    @pytest.mark.asyncio
    async def test_403_skips_without_raise(self):
        client = _mock_http_client()
        client.get.return_value = _error_response(
            403, {"error": "Forbidden"}, method="GET",
            url="https://api.apollo.io/api/v1/emailer_messages/search",
        )

        source = await ApolloSource.create(
            auth=_mock_auth(),
            logger=_mock_logger(),
            http_client=client,
            config=ApolloConfig(),
        )
        entities = [e async for e in source._generate_email_activities()]
        assert len(entities) == 0

    @pytest.mark.asyncio
    async def test_yields_entity_when_authorized(self):
        client = _mock_http_client()
        client.get.return_value = _ok_response(
            {
                "emailer_messages": [
                    {
                        "id": "msg_1",
                        "subject": "Intro",
                        "to_email": "jane@acme.com",
                        "to_name": "Jane",
                        "emailer_campaign_id": "seq_xyz",
                        "campaign_name": "Outreach Q1",
                        "contact_id": "con_123",
                        "status": "delivered",
                    }
                ],
                "pagination": {"total_pages": 1},
            },
            method="GET",
        )

        source = await ApolloSource.create(
            auth=_mock_auth(),
            logger=_mock_logger(),
            http_client=client,
            config=ApolloConfig(),
        )
        entities = [e async for e in source._generate_email_activities()]

        assert len(entities) == 1
        ent = entities[0]
        assert isinstance(ent, ApolloEmailActivityEntity)
        assert ent.entity_id == "msg_1"
        assert "Intro" in ent.name
        assert ent.subject == "Intro"
        assert ent.to_email == "jane@acme.com"
        assert ent.campaign_name == "Outreach Q1"
        assert ent.emailer_campaign_id == "seq_xyz"
        assert ent.contact_id == "con_123"
        assert len(ent.breadcrumbs) == 2  # sequence + contact


# ---------------------------------------------------------------------------
# generate_entities (full flow)
# ---------------------------------------------------------------------------


class TestGenerateEntities:

    @pytest.mark.asyncio
    async def test_yields_accounts_then_contacts_and_skips_403(self):
        """generate_entities yields accounts, contacts; 403 on sequences/activities skips them."""
        client = _mock_http_client()

        post_responses = [
            _ok_response({
                "accounts": [{"id": "acc_1", "name": "A"}],
                "pagination": {"total_pages": 1},
            }),
            _ok_response({
                "contacts": [{"id": "con_1", "email": "c@a.com", "account_id": "acc_1"}],
                "pagination": {"total_pages": 1},
            }),
            _error_response(403, {"error": "Forbidden"}),  # sequences
        ]
        get_responses = [
            _error_response(403, {"error": "Forbidden"}, method="GET",
                            url="https://api.apollo.io/api/v1/emailer_messages/search"),
        ]

        post_idx = 0
        get_idx = 0

        async def post_side_effect(*args, **kwargs):
            nonlocal post_idx
            if post_idx < len(post_responses):
                resp = post_responses[post_idx]
                post_idx += 1
                return resp
            return _ok_response({})

        async def get_side_effect(*args, **kwargs):
            nonlocal get_idx
            if get_idx < len(get_responses):
                resp = get_responses[get_idx]
                get_idx += 1
                return resp
            return _ok_response({}, method="GET")

        client.post = AsyncMock(side_effect=post_side_effect)
        client.get = AsyncMock(side_effect=get_side_effect)

        source = await ApolloSource.create(
            auth=_mock_auth(),
            logger=_mock_logger(),
            http_client=client,
            config=ApolloConfig(),
        )

        entities = [e async for e in source.generate_entities()]

        assert len(entities) == 2
        assert isinstance(entities[0], ApolloAccountEntity)
        assert entities[0].entity_id == "acc_1"
        assert isinstance(entities[1], ApolloContactEntity)
        assert entities[1].entity_id == "con_1"


# ---------------------------------------------------------------------------
# validate
# ---------------------------------------------------------------------------


class TestValidate:

    @pytest.mark.asyncio
    async def test_validate_success(self):
        client = _mock_http_client()
        client.post.return_value = _ok_response(
            {"accounts": [], "pagination": {"total_pages": 0}}
        )

        source = await ApolloSource.create(
            auth=_mock_auth(),
            logger=_mock_logger(),
            http_client=client,
            config=ApolloConfig(),
        )
        await source.validate()

    @pytest.mark.asyncio
    async def test_validate_succeeds_when_http_ok_even_if_body_omits_accounts(self):
        """validate only requires a successful _post; response shape is not asserted here."""
        client = _mock_http_client()
        client.post.return_value = _ok_response({"data": []})

        source = await ApolloSource.create(
            auth=_mock_auth(),
            logger=_mock_logger(),
            http_client=client,
            config=ApolloConfig(),
        )
        await source.validate()

    @pytest.mark.asyncio
    async def test_validate_failure_http_error(self):
        client = _mock_http_client()
        client.post.return_value = _error_response(401, {"error": "Unauthorized"})

        source = await ApolloSource.create(
            auth=_mock_auth(),
            logger=_mock_logger(),
            http_client=client,
            config=ApolloConfig(),
        )
        with pytest.raises(SourceAuthError):
            await source.validate()


# ---------------------------------------------------------------------------
# Source class metadata
# ---------------------------------------------------------------------------


def test_apollo_source_class_metadata():
    """Apollo source has expected short_name and auth methods."""
    assert ApolloSource.short_name == "apollo"
    assert ApolloSource.source_name == "Apollo"
    assert AuthenticationMethod.DIRECT in ApolloSource.auth_methods
    assert AuthenticationMethod.AUTH_PROVIDER in ApolloSource.auth_methods
