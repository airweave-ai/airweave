"""Unit tests for user pure logic.

Direct function calls — zero fixtures, zero I/O.
Tests every edge case and boundary condition.
"""

import pytest

from airweave.domains.users.types import (
    CreateOrUpdateResult,
    is_email_authorized,
)

# ---------------------------------------------------------------------------
# is_email_authorized
# ---------------------------------------------------------------------------


class TestIsEmailAuthorized:
    def test_matching_emails(self):
        assert is_email_authorized("user@test.com", "user@test.com") is True

    def test_mismatched_emails(self):
        assert is_email_authorized("user@test.com", "other@test.com") is False

    def test_case_sensitive(self):
        assert is_email_authorized("User@test.com", "user@test.com") is False

    def test_empty_strings(self):
        assert is_email_authorized("", "") is True

    def test_one_empty(self):
        assert is_email_authorized("user@test.com", "") is False
        assert is_email_authorized("", "user@test.com") is False


# ---------------------------------------------------------------------------
# CreateOrUpdateResult
# ---------------------------------------------------------------------------


class TestCreateOrUpdateResult:
    def test_is_frozen_dataclass(self):
        from unittest.mock import MagicMock

        user = MagicMock()
        result = CreateOrUpdateResult(user=user, is_new=True)
        assert result.user is user
        assert result.is_new is True

        with pytest.raises(AttributeError):
            result.is_new = False  # type: ignore[misc]

    def test_new_user_flag(self):
        from unittest.mock import MagicMock

        result = CreateOrUpdateResult(user=MagicMock(), is_new=True)
        assert result.is_new is True

    def test_existing_user_flag(self):
        from unittest.mock import MagicMock

        result = CreateOrUpdateResult(user=MagicMock(), is_new=False)
        assert result.is_new is False
