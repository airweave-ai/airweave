"""In-memory fake for TokenizerProtocol."""

from airweave.adapters.tokenizer.registry import TokenizerModelSpec


class FakeTokenizer:
    """In-memory fake for TokenizerProtocol.

    Returns a configurable tokens-per-character ratio (default: 1 token per 4 chars).
    """

    def __init__(
        self,
        model_spec: TokenizerModelSpec | None = None,
        chars_per_token: int = 4,
    ) -> None:
        self._model_spec = model_spec or TokenizerModelSpec(encoding_name="fake")
        self._chars_per_token = chars_per_token
        self._calls: list[tuple] = []

    @property
    def model_spec(self) -> TokenizerModelSpec:
        """Get the model specification."""
        return self._model_spec

    def count_tokens(self, text: str) -> int:
        """Count tokens using approximate chars-per-token ratio."""
        self._calls.append(("count_tokens", text))
        if not text:
            return 0
        return max(1, len(text) // self._chars_per_token)
