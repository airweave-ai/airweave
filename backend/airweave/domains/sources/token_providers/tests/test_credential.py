"""Unit tests for DirectCredentialProvider.

DirectCredentialProvider holds typed structured credentials (not a string
token). It implements SourceAuthProvider but NOT TokenProviderProtocol.
"""

from dataclasses import dataclass

import pytest
from pydantic import BaseModel

from airweave.domains.sources.token_providers.credential import DirectCredentialProvider
from airweave.domains.sources.token_providers.protocol import (
    AuthProviderKind,
    SourceAuthProvider,
    TokenProviderProtocol,
)


# ---------------------------------------------------------------------------
# Test auth config models
# ---------------------------------------------------------------------------


class NtlmAuthConfig(BaseModel):
    username: str
    password: str
    domain: str


class DbAuthConfig(BaseModel):
    host: str
    port: int
    database: str


# ---------------------------------------------------------------------------
# Construction and properties — table-driven
# ---------------------------------------------------------------------------


@dataclass
class ConstructCase:
    id: str
    creds: object
    expected_kind: AuthProviderKind = AuthProviderKind.CREDENTIAL


CONSTRUCT_TABLE = [
    ConstructCase(id="pydantic-model", creds=NtlmAuthConfig(username="u", password="p", domain="d")),
    ConstructCase(id="db-config", creds=DbAuthConfig(host="localhost", port=5432, database="test")),
    ConstructCase(id="plain-dict", creds={"key": "value"}),
]


@pytest.mark.parametrize("case", CONSTRUCT_TABLE, ids=lambda c: c.id)
def test_construction(case: ConstructCase):
    p = DirectCredentialProvider(case.creds, source_short_name="test")
    assert p.provider_kind == case.expected_kind
    assert p.supports_refresh is False
    assert p.credentials is case.creds


# ---------------------------------------------------------------------------
# Typed credential access
# ---------------------------------------------------------------------------


def test_generic_type_preservation():
    config = NtlmAuthConfig(username="admin", password="secret", domain="CORP")
    p = DirectCredentialProvider[NtlmAuthConfig](config)
    creds = p.credentials
    assert creds.username == "admin"
    assert creds.password == "secret"
    assert creds.domain == "CORP"


# ---------------------------------------------------------------------------
# Protocol compliance
# ---------------------------------------------------------------------------


def test_implements_source_auth_provider():
    p = DirectCredentialProvider({"k": "v"})
    assert isinstance(p, SourceAuthProvider)


def test_does_not_implement_token_provider_protocol():
    p = DirectCredentialProvider({"k": "v"})
    assert not isinstance(p, TokenProviderProtocol)
