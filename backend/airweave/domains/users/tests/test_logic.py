"""Unit tests for user pure logic.

Direct function calls — zero fixtures, zero I/O.
Tests every edge case and boundary condition.
"""

import pytest

from airweave.domains.users.types import (
    CreateOrUpdateResult,
    has_auth0_id_conflict,
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
# has_auth0_id_conflict
# ---------------------------------------------------------------------------


class TestHasAuth0IdConflict:
    def test_different_ids_is_conflict(self):
        assert has_auth0_id_conflict("auth0|abc", "auth0|xyz") is True

    def test_same_ids_no_conflict(self):
        assert has_auth0_id_conflict("auth0|abc", "auth0|abc") is False

    def test_existing_none_no_conflict(self):
        assert has_auth0_id_conflict(None, "auth0|xyz") is False

    def test_incoming_none_no_conflict(self):
        assert has_auth0_id_conflict("auth0|abc", None) is False

    def test_both_none_no_conflict(self):
        assert has_auth0_id_conflict(None, None) is False

    def test_existing_empty_no_conflict(self):
        assert has_auth0_id_conflict("", "auth0|xyz") is False

    def test_incoming_empty_no_conflict(self):
        assert has_auth0_id_conflict("auth0|abc", "") is False

    def test_both_empty_no_conflict(self):
        assert has_auth0_id_conflict("", "") is False


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
