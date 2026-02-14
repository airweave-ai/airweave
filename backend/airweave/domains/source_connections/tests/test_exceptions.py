"""Unit tests for source connection domain exceptions.

Verifies instantiation and inheritance (middleware maps base class to HTTP status).
"""

from dataclasses import dataclass
from typing import Type
from uuid import uuid4

import pytest

from airweave.core.exceptions import BadRequestError, NotFoundException
from airweave.domains.source_connections.exceptions import (
    ByocRequiredError,
    CollectionNotFoundError,
    InvalidAuthMethodError,
    NoSyncError,
    SourceConnectionNotFoundError,
    SyncImmediatelyNotAllowedError,
)


@dataclass
class ExceptionCase:
    desc: str
    exception: Exception
    expected_base: Type[Exception]
    expected_substr: str


CASES = [
    ExceptionCase(
        desc="SourceConnectionNotFoundError is NotFoundException",
        exception=SourceConnectionNotFoundError(uuid4()),
        expected_base=NotFoundException,
        expected_substr="Source connection not found",
    ),
    ExceptionCase(
        desc="CollectionNotFoundError is NotFoundException",
        exception=CollectionNotFoundError("col-abc"),
        expected_base=NotFoundException,
        expected_substr="Collection not found",
    ),
    ExceptionCase(
        desc="InvalidAuthMethodError is BadRequestError",
        exception=InvalidAuthMethodError("oauth_token", ["direct", "oauth_browser"]),
        expected_base=BadRequestError,
        expected_substr="Unsupported auth method",
    ),
    ExceptionCase(
        desc="ByocRequiredError is BadRequestError",
        exception=ByocRequiredError("shopify"),
        expected_base=BadRequestError,
        expected_substr="requires custom OAuth",
    ),
    ExceptionCase(
        desc="SyncImmediatelyNotAllowedError is BadRequestError",
        exception=SyncImmediatelyNotAllowedError(),
        expected_base=BadRequestError,
        expected_substr="cannot use sync_immediately",
    ),
    ExceptionCase(
        desc="NoSyncError is BadRequestError",
        exception=NoSyncError(uuid4()),
        expected_base=BadRequestError,
        expected_substr="has no associated sync",
    ),
]


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.desc)
def test_exception_inheritance_and_message(case: ExceptionCase):
    assert isinstance(case.exception, case.expected_base)
    assert case.expected_substr in str(case.exception)
