"""Unit tests for tokenizer factory and implementations."""

import pytest
from unittest.mock import patch, MagicMock


class TestTikTokenTokenizer:
    """Tests for TikTokenTokenizer."""

    def test_creates_with_valid_encoding(self):
        """Test creating tokenizer with valid encoding name."""
        from airweave.platform.tokenizers import TikTokenTokenizer

        tokenizer = TikTokenTokenizer("cl100k_base")
        assert tokenizer.name == "cl100k_base"

    def test_raises_on_invalid_encoding(self):
        """Test that invalid encoding raises ValueError."""
        from airweave.platform.tokenizers import TikTokenTokenizer

        with pytest.raises(ValueError) as exc_info:
            TikTokenTokenizer("invalid_encoding_name")

        assert "Failed to load tiktoken encoding" in str(exc_info.value)

    def test_encode_returns_token_ids(self):
        """Test encode returns list of integers."""
        from airweave.platform.tokenizers import TikTokenTokenizer

        tokenizer = TikTokenTokenizer("cl100k_base")
        tokens = tokenizer.encode("Hello, world!")

        assert isinstance(tokens, list)
        assert all(isinstance(t, int) for t in tokens)
        assert len(tokens) > 0

    def test_decode_returns_text(self):
        """Test decode returns original text."""
        from airweave.platform.tokenizers import TikTokenTokenizer

        tokenizer = TikTokenTokenizer("cl100k_base")
        text = "Hello, world!"
        tokens = tokenizer.encode(text)
        decoded = tokenizer.decode(tokens)

        assert decoded == text

    def test_count_tokens(self):
        """Test count_tokens returns accurate count."""
        from airweave.platform.tokenizers import TikTokenTokenizer

        tokenizer = TikTokenTokenizer("cl100k_base")
        text = "Hello, world!"
        count = tokenizer.count_tokens(text)

        # Manual encode to verify
        tokens = tokenizer.encode(text)
        assert count == len(tokens)

    def test_handles_special_tokens(self):
        """Test that special tokens like <|endoftext|> are handled."""
        from airweave.platform.tokenizers import TikTokenTokenizer

        tokenizer = TikTokenTokenizer("cl100k_base")

        # Should not raise with special tokens
        text = "Some text <|endoftext|> more text"
        tokens = tokenizer.encode(text)

        assert len(tokens) > 0

    def test_encode_batch(self):
        """Test batch encoding multiple texts."""
        from airweave.platform.tokenizers import TikTokenTokenizer

        tokenizer = TikTokenTokenizer("cl100k_base")
        texts = ["Hello", "World", "Test"]
        batched = tokenizer.encode_batch(texts)

        assert len(batched) == 3
        assert all(isinstance(tokens, list) for tokens in batched)

    def test_decode_batch(self):
        """Test batch decoding multiple token lists."""
        from airweave.platform.tokenizers import TikTokenTokenizer

        tokenizer = TikTokenTokenizer("cl100k_base")
        texts = ["Hello", "World"]
        token_lists = tokenizer.encode_batch(texts)
        decoded = tokenizer.decode_batch(token_lists)

        assert decoded == texts

    def test_tokenize_alias(self):
        """Test tokenize is alias for encode."""
        from airweave.platform.tokenizers import TikTokenTokenizer

        tokenizer = TikTokenTokenizer("cl100k_base")
        text = "Test text"

        assert tokenizer.tokenize(text) == tokenizer.encode(text)

    def test_exposes_raw_encoding(self):
        """Test encoding property returns tiktoken Encoding."""
        from airweave.platform.tokenizers import TikTokenTokenizer
        from tiktoken import Encoding

        tokenizer = TikTokenTokenizer("cl100k_base")
        assert isinstance(tokenizer.encoding, Encoding)


class TestMistralTokenizer:
    """Tests for MistralTokenizer."""

    def test_creates_with_mistral_model(self):
        """Test creating tokenizer with mistral model name."""
        from airweave.platform.tokenizers import MistralTokenizer

        tokenizer = MistralTokenizer("mistral-embed")
        assert "mistral" in tokenizer.name.lower()

    def test_encode_returns_token_ids(self):
        """Test encode returns list of integers."""
        from airweave.platform.tokenizers import MistralTokenizer

        tokenizer = MistralTokenizer("mistral-embed")
        tokens = tokenizer.encode("Hello, world!")

        assert isinstance(tokens, list)
        assert all(isinstance(t, int) for t in tokens)
        assert len(tokens) > 0

    def test_count_tokens(self):
        """Test count_tokens returns accurate count."""
        from airweave.platform.tokenizers import MistralTokenizer

        tokenizer = MistralTokenizer("mistral-embed")
        text = "Hello, world!"
        count = tokenizer.count_tokens(text)

        # Should be positive
        assert count > 0

    def test_handles_empty_text(self):
        """Test handling of empty text."""
        from airweave.platform.tokenizers import MistralTokenizer

        tokenizer = MistralTokenizer("mistral-embed")
        count = tokenizer.count_tokens("")

        assert count == 0

    def test_handles_unicode(self):
        """Test handling of unicode text."""
        from airweave.platform.tokenizers import MistralTokenizer

        tokenizer = MistralTokenizer("mistral-embed")
        count = tokenizer.count_tokens("Hello 你好 مرحبا 🎉")

        assert count > 0


class TestTokenizerFactory:
    """Tests for get_tokenizer() factory."""

    def test_returns_tiktoken_for_cl100k(self):
        """Test factory returns TikTokenTokenizer for cl100k_base."""
        from airweave.platform.tokenizers import TikTokenTokenizer, get_tokenizer

        tokenizer = get_tokenizer("cl100k_base")
        assert isinstance(tokenizer, TikTokenTokenizer)

    def test_returns_tiktoken_for_o200k(self):
        """Test factory returns TikTokenTokenizer for o200k_base."""
        from airweave.platform.tokenizers import TikTokenTokenizer, get_tokenizer

        tokenizer = get_tokenizer("o200k_base")
        assert isinstance(tokenizer, TikTokenTokenizer)

    def test_returns_mistral_for_mistral_model(self):
        """Test factory returns MistralTokenizer for mistral models."""
        from airweave.platform.tokenizers import MistralTokenizer, get_tokenizer

        tokenizer = get_tokenizer("mistral-embed")
        assert isinstance(tokenizer, MistralTokenizer)

    def test_caches_tokenizer_instances(self):
        """Test that tokenizer instances are cached."""
        from airweave.platform.tokenizers import get_tokenizer

        tokenizer1 = get_tokenizer("cl100k_base")
        tokenizer2 = get_tokenizer("cl100k_base")

        # Should be same instance
        assert tokenizer1 is tokenizer2

    def test_raises_on_unknown_tokenizer(self):
        """Test that unknown tokenizer name raises ValueError."""
        from airweave.platform.tokenizers import get_tokenizer

        with pytest.raises(ValueError) as exc_info:
            get_tokenizer("completely_unknown_tokenizer_xyz")

        assert "Unknown tokenizer" in str(exc_info.value)


class TestIsTiktokenEncoding:
    """Tests for is_tiktoken_encoding()."""

    def test_recognizes_standard_encodings(self):
        """Test that standard encodings are recognized."""
        from airweave.platform.tokenizers.tiktoken import is_tiktoken_encoding

        assert is_tiktoken_encoding("cl100k_base") is True
        assert is_tiktoken_encoding("o200k_base") is True
        assert is_tiktoken_encoding("p50k_base") is True
        assert is_tiktoken_encoding("gpt2") is True

    def test_rejects_non_tiktoken_names(self):
        """Test that non-tiktoken names are rejected."""
        from airweave.platform.tokenizers.tiktoken import is_tiktoken_encoding

        assert is_tiktoken_encoding("mistral-embed") is False
        assert is_tiktoken_encoding("unknown") is False
