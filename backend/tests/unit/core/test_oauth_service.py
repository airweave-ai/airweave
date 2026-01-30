"""Unit tests for OAuth service utility methods."""

import hashlib

import pytest

from airweave.core.oauth_service import OAuthService


class TestOAuthService:
    """Test OAuth service utility methods (non-database)."""

    def test_hash_token(self):
        """Test token hashing produces consistent results."""
        token = "test-token-12345"
        hash1 = OAuthService.hash_token(token)
        hash2 = OAuthService.hash_token(token)
        
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA256 produces 64 hex characters
        
        # Verify it's actually SHA256
        expected = hashlib.sha256(token.encode()).hexdigest()
        assert hash1 == expected

    def test_generate_token(self):
        """Test token generation creates unique tokens."""
        token1 = OAuthService._generate_token()
        token2 = OAuthService._generate_token()
        
        assert token1 != token2
        assert len(token1) > 32  # Should be reasonably long
        
        # Test with prefix
        token_with_prefix = OAuthService._generate_token(prefix="oat_")
        assert token_with_prefix.startswith("oat_")

    def test_verify_pkce_challenge(self):
        """Test PKCE challenge verification."""
        # Generate a code verifier and challenge
        from airweave.platform.auth.oauth2_service import OAuth2Service
        
        code_verifier, code_challenge = OAuth2Service._generate_pkce_challenge_pair()
        
        # Verify the challenge
        assert OAuthService._verify_pkce_challenge(code_verifier, code_challenge) is True
        
        # Verify wrong verifier fails
        wrong_verifier = "wrong_verifier_12345"
        assert OAuthService._verify_pkce_challenge(wrong_verifier, code_challenge) is False

    def test_token_constants(self):
        """Test OAuth token configuration constants."""
        assert OAuthService.AUTHORIZATION_CODE_TTL_SECONDS == 600  # 10 minutes
        assert OAuthService.ACCESS_TOKEN_TTL_SECONDS == 3600  # 1 hour
        assert OAuthService.TOKEN_PREFIX == "oat_"


# Note: Database-dependent tests (create_authorization_code, exchange_code_for_token,
# validate_access_token, etc.) are in tests/e2e/test_oauth_flow.py
