"""Tests for the secure key handling modules."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from airweave.core.secure_keys import (
    SecureKeyManager, 
    KeyAccessMonitor, 
    log_key_access
)
from airweave.utils.key_validation import (
    is_valid_ethereum_private_key,
    is_valid_ethereum_address,
    sanitize_private_key,
    mask_private_key
)

# Test data
TEST_ETHEREUM_PRIVATE_KEY = "0x0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
TEST_ETHEREUM_ADDRESS = "0x742d35Cc6634C0532925a3b844Bc454e4438f44e"
TEST_API_KEY = "abc123def456ghi789"


class TestKeyValidation:
    """Tests for key validation utilities."""
    
    def test_valid_ethereum_private_key(self):
        """Test validation of valid Ethereum private keys."""
        # With 0x prefix
        assert is_valid_ethereum_private_key(TEST_ETHEREUM_PRIVATE_KEY)
        
        # Without 0x prefix
        assert is_valid_ethereum_private_key(TEST_ETHEREUM_PRIVATE_KEY[2:])
        
    def test_invalid_ethereum_private_key(self):
        """Test validation of invalid Ethereum private keys."""
        # Too short
        assert not is_valid_ethereum_private_key("0x1234")
        
        # Too long
        assert not is_valid_ethereum_private_key(TEST_ETHEREUM_PRIVATE_KEY + "00")
        
        # Invalid characters
        assert not is_valid_ethereum_private_key("0xZZZZZZ6789abcdef0123456789abcdef0123456789abcdef0123456789abcdef")
        
        # Empty or None
        assert not is_valid_ethereum_private_key("")
        assert not is_valid_ethereum_private_key(None)
        
    def test_valid_ethereum_address(self):
        """Test validation of valid Ethereum addresses."""
        # With 0x prefix
        assert is_valid_ethereum_address(TEST_ETHEREUM_ADDRESS)
        
        # Without 0x prefix
        assert is_valid_ethereum_address(TEST_ETHEREUM_ADDRESS[2:])
        
    def test_invalid_ethereum_address(self):
        """Test validation of invalid Ethereum addresses."""
        # Too short
        assert not is_valid_ethereum_address("0x1234")
        
        # Too long
        assert not is_valid_ethereum_address(TEST_ETHEREUM_ADDRESS + "00")
        
        # Invalid characters
        assert not is_valid_ethereum_address("0xZZZZ35Cc6634C0532925a3b844Bc454e4438f44e")
        
        # Empty or None
        assert not is_valid_ethereum_address("")
        assert not is_valid_ethereum_address(None)
        
    def test_sanitize_private_key(self):
        """Test sanitization of private keys."""
        # Add 0x prefix if missing
        assert sanitize_private_key(TEST_ETHEREUM_PRIVATE_KEY[2:]) == TEST_ETHEREUM_PRIVATE_KEY
        
        # Keep 0x prefix if present
        assert sanitize_private_key(TEST_ETHEREUM_PRIVATE_KEY) == TEST_ETHEREUM_PRIVATE_KEY
        
        # Trim whitespace
        assert sanitize_private_key(" " + TEST_ETHEREUM_PRIVATE_KEY + " ") == TEST_ETHEREUM_PRIVATE_KEY
        
    def test_mask_private_key(self):
        """Test masking of private keys for logging."""
        # Private key with 0x prefix
        masked = mask_private_key(TEST_ETHEREUM_PRIVATE_KEY)
        # Should keep 0x prefix, first 4 and last 4 chars of the key
        assert masked.startswith("0x0123")
        assert masked.endswith("cdef")
        assert "*" in masked
        assert len(masked) == len(TEST_ETHEREUM_PRIVATE_KEY)
        
        # Private key without 0x prefix
        masked = mask_private_key(TEST_ETHEREUM_PRIVATE_KEY[2:])
        assert masked.startswith("0123")
        assert masked.endswith("cdef")
        assert "*" in masked
        assert len(masked) == len(TEST_ETHEREUM_PRIVATE_KEY[2:])
        
        # Short key
        short_key = "1234"
        masked = mask_private_key(short_key)
        assert masked == "**34" or masked == "*34"  # Depends on implementation details


class TestKeyAccessMonitor:
    """Tests for the key access monitoring functionality."""
    
    def test_log_access(self):
        """Test logging key access."""
        monitor = KeyAccessMonitor()
        
        # Log some accesses
        monitor.log_access("test_key_1", "read", "test_function")
        monitor.log_access("test_key_1", "write", "another_function")
        monitor.log_access("test_key_2", "read", "test_function")
        
        # Check access statistics
        stats = monitor.get_access_statistics()
        
        assert stats["total_keys_tracked"] == 2
        assert stats["total_accesses"] == 3
        
    def test_mask_key_id(self):
        """Test masking of key IDs for logging."""
        monitor = KeyAccessMonitor()
        
        # Short key ID
        short_id = "1234"
        masked = monitor._mask_key_id(short_id)
        assert len(masked) >= 3
        assert "***" in masked
        
        # Longer key ID
        long_id = "abcdef1234567890"
        masked = monitor._mask_key_id(long_id)
        assert masked.startswith("abc")
        assert "***" in masked


@pytest.mark.asyncio
class TestSecureKeyManager:
    """Tests for the secure key manager."""
    
    @pytest.fixture
    def mock_secret_manager(self):
        """Create a mock secret manager."""
        with patch("airweave.core.secure_keys.secret_manager") as mock:
            # Setup the mock
            mock.get_secret = AsyncMock()
            mock.set_secret = AsyncMock(return_value=True)
            yield mock
    
    async def test_get_api_key(self, mock_secret_manager):
        """Test retrieving an API key."""
        # Setup mock return value
        mock_secret_manager.get_secret.return_value = TEST_API_KEY
        
        # Test retrieval
        manager = SecureKeyManager()
        result = await manager.get_api_key("test_api_key")
        
        assert result == TEST_API_KEY
        mock_secret_manager.get_secret.assert_called_once()
        
    async def test_store_api_key(self, mock_secret_manager):
        """Test storing an API key."""
        # Setup mock return value
        mock_secret_manager.set_secret.return_value = True
        
        # Test storage
        manager = SecureKeyManager()
        result = await manager.store_api_key("test_api_key", TEST_API_KEY)
        
        assert result is True
        mock_secret_manager.set_secret.assert_called_once()
        
    async def test_get_private_key(self, mock_secret_manager):
        """Test retrieving a private key."""
        # Setup mock return value
        mock_secret_manager.get_secret.return_value = TEST_ETHEREUM_PRIVATE_KEY
        
        # Test retrieval
        manager = SecureKeyManager()
        result = await manager.get_private_key("test_private_key")
        
        assert result == TEST_ETHEREUM_PRIVATE_KEY
        mock_secret_manager.get_secret.assert_called_once()
        
    async def test_store_private_key(self, mock_secret_manager):
        """Test storing a private key."""
        # Setup mock return value
        mock_secret_manager.set_secret.return_value = True
        
        # Test storage
        manager = SecureKeyManager()
        result = await manager.store_private_key("test_private_key", TEST_ETHEREUM_PRIVATE_KEY)
        
        assert result is True
        mock_secret_manager.set_secret.assert_called_once()
        
    async def test_get_token(self, mock_secret_manager):
        """Test retrieving a token."""
        # Setup mock return value - token as JSON string
        token_data = '{"access_token": "test_token", "expires_in": 3600}'
        mock_secret_manager.get_secret.return_value = token_data
        
        # Test retrieval
        manager = SecureKeyManager()
        result = await manager.get_token("test_token")
        
        assert "access_token" in result
        assert result["access_token"] == "test_token"
        mock_secret_manager.get_secret.assert_called_once()
        
    async def test_delete_key(self, mock_secret_manager):
        """Test deleting a key."""
        # Test deletion
        manager = SecureKeyManager()
        result = await manager.delete_key("api_key", "test_api_key")
        
        assert result is True
        mock_secret_manager.set_secret.assert_called_once()
        
    async def test_log_key_access_decorator(self):
        """Test that the log_key_access decorator works correctly."""
        # Create a decorated function using the decorator
        @log_key_access("read")
        async def test_function(self, key_id):
            return key_id
            
        # Create a spy on the log_access method
        with patch("airweave.core.secure_keys.key_monitor.log_access") as mock_log:
            # Call the decorated function
            result = await test_function(None, "test_key_id")
            
            # Verify that the log_access was called correctly
            assert result == "test_key_id"
            mock_log.assert_called_once_with("test_key_id", "read", "test_function")