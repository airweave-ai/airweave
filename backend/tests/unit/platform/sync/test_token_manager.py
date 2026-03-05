"""
Unit tests for TokenManager.

Tests the token manager's ability to:
- Detect refresh token presence in credentials
- Determine refresh capability based on credentials
- Handle direct token injection (access_token only, no refresh_token)
"""

import pytest
from unittest.mock import MagicMock, AsyncMock
from uuid import uuid4

from airweave.platform.sync.token_manager import TokenManager


class TestCheckHasRefreshToken:
    """Tests for TokenManager._check_has_refresh_token method."""

    def _create_minimal_token_manager(self, credentials):
        """Create a TokenManager instance for testing _check_has_refresh_token."""
        # Create mock dependencies
        mock_db = MagicMock()
        mock_source_connection = MagicMock()
        mock_source_connection.id = uuid4()
        mock_source_connection.integration_credential_id = uuid4()
        mock_source_connection.config_fields = None
        mock_ctx = MagicMock()
        mock_ctx.logger = MagicMock()

        # TokenManager constructor will call _check_has_refresh_token
        # We need to ensure credentials has access_token
        if isinstance(credentials, dict) and "access_token" not in credentials:
            credentials["access_token"] = "test_access_token"
        elif not isinstance(credentials, dict):
            # For non-dict credentials, we'll test the method directly
            pass

        manager = TokenManager(
            db=mock_db,
            source_short_name="test_source",
            source_connection=mock_source_connection,
            ctx=mock_ctx,
            initial_credentials=credentials if isinstance(credentials, dict) else {"access_token": "test"},
            is_direct_injection=False,
            logger_instance=MagicMock(),
        )

        return manager

    def test_dict_with_refresh_token(self):
        """Test detection of refresh token in dict credentials."""
        credentials = {
            "access_token": "test_access_token",
            "refresh_token": "test_refresh_token",
        }
        manager = self._create_minimal_token_manager(credentials)
        assert manager._has_refresh_token is True

    def test_dict_without_refresh_token(self):
        """Test no refresh token in dict credentials (direct token injection)."""
        credentials = {
            "access_token": "test_access_token",
        }
        manager = self._create_minimal_token_manager(credentials)
        assert manager._has_refresh_token is False

    def test_dict_with_empty_refresh_token(self):
        """Test empty refresh token is treated as no refresh token."""
        credentials = {
            "access_token": "test_access_token",
            "refresh_token": "",
        }
        manager = self._create_minimal_token_manager(credentials)
        assert manager._has_refresh_token is False

    def test_dict_with_whitespace_refresh_token(self):
        """Test whitespace-only refresh token is treated as no refresh token."""
        credentials = {
            "access_token": "test_access_token",
            "refresh_token": "   ",
        }
        manager = self._create_minimal_token_manager(credentials)
        assert manager._has_refresh_token is False

    def test_dict_with_none_refresh_token(self):
        """Test None refresh token is treated as no refresh token."""
        credentials = {
            "access_token": "test_access_token",
            "refresh_token": None,
        }
        manager = self._create_minimal_token_manager(credentials)
        assert manager._has_refresh_token is False


class TestDetermineRefreshCapability:
    """Tests for TokenManager._determine_refresh_capability method."""

    def _create_token_manager(
        self,
        credentials,
        is_direct_injection=False,
        auth_provider_instance=None,
    ):
        """Create a TokenManager instance for testing _determine_refresh_capability."""
        mock_db = MagicMock()
        mock_source_connection = MagicMock()
        mock_source_connection.id = uuid4()
        mock_source_connection.integration_credential_id = uuid4()
        mock_source_connection.config_fields = None
        mock_ctx = MagicMock()
        mock_ctx.logger = MagicMock()

        manager = TokenManager(
            db=mock_db,
            source_short_name="test_source",
            source_connection=mock_source_connection,
            ctx=mock_ctx,
            initial_credentials=credentials,
            is_direct_injection=is_direct_injection,
            logger_instance=MagicMock(),
            auth_provider_instance=auth_provider_instance,
        )

        return manager

    def test_direct_injection_disables_refresh(self):
        """Test that direct injection flag disables refresh capability."""
        credentials = {
            "access_token": "test_access_token",
            "refresh_token": "test_refresh_token",  # Even with refresh token
        }
        manager = self._create_token_manager(
            credentials=credentials,
            is_direct_injection=True,  # Direct injection
        )
        assert manager._can_refresh is False

    def test_auth_provider_enables_refresh(self):
        """Test that auth provider instance enables refresh capability."""
        credentials = {
            "access_token": "test_access_token",
            # No refresh token
        }
        mock_auth_provider = MagicMock()
        manager = self._create_token_manager(
            credentials=credentials,
            auth_provider_instance=mock_auth_provider,
        )
        assert manager._can_refresh is True

    def test_no_refresh_token_disables_refresh(self):
        """Test that missing refresh token disables refresh capability.

        This is the key fix for direct token injection via OAuthTokenAuthentication.
        """
        credentials = {
            "access_token": "test_access_token",
            # No refresh token - simulates OAuthTokenAuthentication
        }
        manager = self._create_token_manager(
            credentials=credentials,
            is_direct_injection=False,  # Not flagged as direct injection
            auth_provider_instance=None,  # No auth provider
        )
        # Should detect missing refresh token and disable refresh
        assert manager._can_refresh is False

    def test_refresh_token_present_enables_refresh(self):
        """Test that present refresh token enables refresh capability."""
        credentials = {
            "access_token": "test_access_token",
            "refresh_token": "test_refresh_token",
        }
        manager = self._create_token_manager(
            credentials=credentials,
            is_direct_injection=False,
            auth_provider_instance=None,
        )
        # Should detect refresh token and enable refresh
        assert manager._can_refresh is True


class TestGetValidToken:
    """Tests for TokenManager.get_valid_token method."""

    @pytest.mark.asyncio
    async def test_returns_current_token_when_refresh_disabled(self):
        """Test that get_valid_token returns current token when refresh is disabled."""
        credentials = {
            "access_token": "test_access_token",
            # No refresh token - refresh should be disabled
        }

        mock_db = MagicMock()
        mock_source_connection = MagicMock()
        mock_source_connection.id = uuid4()
        mock_source_connection.integration_credential_id = uuid4()
        mock_source_connection.config_fields = None
        mock_ctx = MagicMock()
        mock_ctx.logger = MagicMock()

        manager = TokenManager(
            db=mock_db,
            source_short_name="test_source",
            source_connection=mock_source_connection,
            ctx=mock_ctx,
            initial_credentials=credentials,
            is_direct_injection=False,
            logger_instance=MagicMock(),
        )

        # Refresh should be disabled
        assert manager._can_refresh is False

        # get_valid_token should return current token without attempting refresh
        token = await manager.get_valid_token()
        assert token == "test_access_token"

    @pytest.mark.asyncio
    async def test_direct_injection_returns_token_without_refresh(self):
        """Test direct injection mode returns token without refresh attempt."""
        credentials = {
            "access_token": "direct_injected_token",
            "refresh_token": "should_not_be_used",
        }

        mock_db = MagicMock()
        mock_source_connection = MagicMock()
        mock_source_connection.id = uuid4()
        mock_source_connection.integration_credential_id = uuid4()
        mock_source_connection.config_fields = None
        mock_ctx = MagicMock()
        mock_ctx.logger = MagicMock()

        manager = TokenManager(
            db=mock_db,
            source_short_name="test_source",
            source_connection=mock_source_connection,
            ctx=mock_ctx,
            initial_credentials=credentials,
            is_direct_injection=True,  # Explicit direct injection
            logger_instance=MagicMock(),
        )

        # Should be disabled due to direct_injection flag
        assert manager._can_refresh is False

        token = await manager.get_valid_token()
        assert token == "direct_injected_token"


class TestCredentialFormats:
    """Tests for different credential formats."""

    def _create_manager_with_credentials(self, credentials):
        """Helper to create manager with various credential formats."""
        mock_db = MagicMock()
        mock_source_connection = MagicMock()
        mock_source_connection.id = uuid4()
        mock_source_connection.integration_credential_id = uuid4()
        mock_source_connection.config_fields = None
        mock_ctx = MagicMock()
        mock_ctx.logger = MagicMock()

        return TokenManager(
            db=mock_db,
            source_short_name="test_source",
            source_connection=mock_source_connection,
            ctx=mock_ctx,
            initial_credentials=credentials,
            is_direct_injection=False,
            logger_instance=MagicMock(),
        )

    def test_string_credentials_no_refresh(self):
        """Test that string credentials (just token) have no refresh capability."""
        # String credentials are just the access token
        manager = self._create_manager_with_credentials("string_access_token")

        # String credentials don't have refresh token
        assert manager._has_refresh_token is False
        assert manager._can_refresh is False

    def test_object_credentials_with_refresh_token(self):
        """Test object credentials with refresh_token attribute."""
        # Create an object with access_token and refresh_token attributes
        class CredentialsObj:
            access_token = "obj_access_token"
            refresh_token = "obj_refresh_token"

        manager = self._create_manager_with_credentials(CredentialsObj())

        assert manager._has_refresh_token is True
        assert manager._can_refresh is True

    def test_object_credentials_without_refresh_token(self):
        """Test object credentials without refresh_token attribute."""
        class CredentialsObj:
            access_token = "obj_access_token"
            # No refresh_token attribute

        manager = self._create_manager_with_credentials(CredentialsObj())

        assert manager._has_refresh_token is False
        assert manager._can_refresh is False
