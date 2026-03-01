"""Tests for the Redis cache adapter's SHA-256 API key hashing.

Verifies:
- Hash is deterministic (same key always produces same hash)
- Different keys produce different hashes
- Hash is a valid hex string of correct length (64 chars for SHA-256)
- Raw API key is never used as the cache key
"""

from airweave.adapters.cache.redis import RedisContextCache


class TestApiKeyHashing:
    def test_deterministic(self):
        h1 = RedisContextCache._hash_api_key("my-secret-key")
        h2 = RedisContextCache._hash_api_key("my-secret-key")
        assert h1 == h2

    def test_different_keys_different_hashes(self):
        h1 = RedisContextCache._hash_api_key("key-a")
        h2 = RedisContextCache._hash_api_key("key-b")
        assert h1 != h2

    def test_hash_is_64_char_hex(self):
        h = RedisContextCache._hash_api_key("test")
        assert len(h) == 64
        int(h, 16)  # raises ValueError if not valid hex

    def test_raw_key_not_in_hash(self):
        key = "super-secret-api-key-12345"
        h = RedisContextCache._hash_api_key(key)
        assert key not in h
