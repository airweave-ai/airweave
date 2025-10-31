"""Code chunker using AST-based parsing with TokenChunker safety net."""

from typing import Any, Dict, List, Optional

from airweave.core.logging import logger
from airweave.platform.chunkers._base import BaseChunker
from airweave.platform.sync.async_helpers import run_in_thread_pool
from airweave.platform.sync.exceptions import SyncFailureError


class CodeChunker(BaseChunker):
    """Singleton code chunker with AST-based parsing (no API calls).

    Two-stage approach (internal implementation detail):
    1. CodeChunker: Chunks at logical code boundaries (functions, classes, methods)
    2. TokenChunker fallback: Force-splits any oversized chunks at token boundaries

    The chunker is shared across all syncs in the pod to avoid reloading
    the Magika language detection model for every sync job.

    Note: Even with AST-based splitting, single large AST nodes (massive functions
    without children) can exceed chunk_size, so we use TokenChunker as safety net.
    """

    # Configuration constants
    MAX_TOKENS_PER_CHUNK = 8192  # OpenAI hard limit (safety net)
    CHUNK_SIZE = 2048  # Target chunk size (can be exceeded by large AST nodes)
    TOKENIZER = "cl100k_base"  # For accurate OpenAI token counting

    # Singleton instance
    _instance: Optional["CodeChunker"] = None

    def __new__(cls):
        """Singleton pattern - one instance per pod."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Initialize once per pod (models load lazily on first use)."""
        if self._initialized:
            return

        self._code_chunker = None  # Lazy init
        self._token_chunker = None  # Lazy init (emergency fallback)
        self._tiktoken_tokenizer = None  # Lazy init
        self._initialized = True

        logger.debug(
            f"CodeChunker singleton initialized "
            f"(target: {self.CHUNK_SIZE}, hard_limit: {self.MAX_TOKENS_PER_CHUNK})"
        )

    def _ensure_chunkers(self):
        """Lazy initialization of chunker models.

        Initializes CodeChunker (AST parsing) + TokenChunker (safety net).

        Raises:
            SyncFailureError: If model loading fails (infrastructure error)
        """
        if self._code_chunker is not None:
            return

        try:
            import tiktoken
            from chonkie import CodeChunker as ChonkieCodeChunker
            from chonkie import TokenChunker

            # Initialize tiktoken tokenizer for accurate OpenAI token counting
            self._tiktoken_tokenizer = tiktoken.get_encoding(self.TOKENIZER)

            # Initialize Chonkie's CodeChunker with auto language detection
            # Uses Magika (Google's ML-based language detector) to identify language
            self._code_chunker = ChonkieCodeChunker(
                language="auto",  # Auto-detect using Magika
                tokenizer=self._tiktoken_tokenizer,
                chunk_size=self.CHUNK_SIZE,
                include_nodes=False,
            )

            # Initialize TokenChunker for fallback
            # Splits at exact token boundaries when code chunking produces oversized chunks
            # GUARANTEES chunks ≤ MAX_TOKENS_PER_CHUNK (uses same tokenizer for encode/decode)
            self._token_chunker = TokenChunker(
                tokenizer=self._tiktoken_tokenizer,
                chunk_size=self.MAX_TOKENS_PER_CHUNK,
                chunk_overlap=0,
            )

            logger.info(
                f"Loaded CodeChunker (auto-detect, target: {self.CHUNK_SIZE}) + "
                f"TokenChunker fallback (hard_limit: {self.MAX_TOKENS_PER_CHUNK})"
            )

        except Exception as e:
            raise SyncFailureError(f"Failed to initialize CodeChunker: {e}")

    async def chunk_batch(self, texts: List[str]) -> List[List[Dict[str, Any]]]:
        """Chunk a batch of code texts with two-stage approach.

        Stage 1: CodeChunker chunks at AST boundaries (functions, classes)
        Stage 2: TokenChunker force-splits any chunks exceeding MAX_TOKENS_PER_CHUNK (hard limit)

        Uses run_in_thread_pool because Chonkie is synchronous (avoids blocking event loop).

        Args:
            texts: List of code textual representations to chunk

        Returns:
            List of chunk lists (one per input text), where each chunk is a dict

        Raises:
            SyncFailureError: If model initialization or batch processing fails
        """
        self._ensure_chunkers()

        # Stage 1: AST-based code chunking
        try:
            code_results = await run_in_thread_pool(self._code_chunker.chunk_batch, texts)
        except Exception as e:
            # CodeChunker failure = sync failure (not entity-level)
            raise SyncFailureError(f"CodeChunker batch processing failed: {e}")

        # Stage 2: Safety net (batched for efficiency)
        final_results = await run_in_thread_pool(self._apply_safety_net_batched, code_results)

        # Validate all chunks meet requirements
        for doc_chunks in final_results:
            for chunk in doc_chunks:
                # Check for empty chunks
                if not chunk["text"] or not chunk["text"].strip():
                    raise SyncFailureError("PROGRAMMING ERROR: Empty chunk produced by CodeChunker")

                # Check token limit enforced
                if chunk["token_count"] > self.MAX_TOKENS_PER_CHUNK:
                    raise SyncFailureError(
                        f"PROGRAMMING ERROR: Chunk has {chunk['token_count']} tokens "
                        f"after safety net (max: {self.MAX_TOKENS_PER_CHUNK})"
                    )

        return final_results

    def _apply_safety_net_batched(
        self, code_results: List[List[Any]]
    ) -> List[List[Dict[str, Any]]]:
        """Split oversized chunks using TokenChunker fallback.

        Same implementation as SemanticChunker - collects oversized chunks,
        batch processes them, then reconstructs results.

        Args:
            code_results: Chunks from CodeChunker

        Returns:
            Final chunks as dicts, all guaranteed ≤ MAX_TOKENS_PER_CHUNK
        """
        # Collect oversized chunks with position mapping
        oversized_texts = []
        oversized_map = {}  # position in oversized_texts → (doc_idx, chunk_idx)

        for doc_idx, chunks in enumerate(code_results):
            for chunk_idx, chunk in enumerate(chunks):
                if chunk.token_count > self.MAX_TOKENS_PER_CHUNK:
                    pos = len(oversized_texts)
                    oversized_texts.append(chunk.text)
                    oversized_map[pos] = (doc_idx, chunk_idx)

        # Batch process all oversized chunks with TokenChunker fallback
        # TokenChunker enforces hard limit in one pass (no recursion needed)
        split_results_by_position = {}
        if oversized_texts:
            logger.debug(
                f"Safety net: splitting {len(oversized_texts)} oversized code chunks "
                f"exceeding {self.MAX_TOKENS_PER_CHUNK} tokens with TokenChunker"
            )

            # Use TokenChunker to split at exact token boundaries
            # GUARANTEED to produce chunks ≤ MAX_TOKENS_PER_CHUNK in one pass
            split_results = self._token_chunker.chunk_batch(oversized_texts)
            split_results_by_position = dict(enumerate(split_results))

        # Reconstruct final results
        final_results = []
        for doc_idx, chunks in enumerate(code_results):
            final_chunks = []
            for chunk_idx, chunk in enumerate(chunks):
                # Check if this chunk was oversized
                oversized_pos = next(
                    (
                        pos
                        for pos, (d_idx, c_idx) in oversized_map.items()
                        if d_idx == doc_idx and c_idx == chunk_idx
                    ),
                    None,
                )

                if oversized_pos is not None:
                    # Replace with split sub-chunks
                    split_chunks = split_results_by_position[oversized_pos]
                    for sub_chunk in split_chunks:
                        final_chunks.append(self._convert_chunk(sub_chunk))
                else:
                    # Keep original chunk
                    final_chunks.append(self._convert_chunk(chunk))

            final_results.append(final_chunks)

        if oversized_texts:
            logger.debug(
                f"TokenChunker fallback split {len(oversized_texts)} code chunks "
                f"that exceeded {self.MAX_TOKENS_PER_CHUNK} tokens"
            )

        return final_results

    def _convert_chunk(self, chunk) -> Dict[str, Any]:
        """Convert Chonkie Chunk object to dict format.

        Args:
            chunk: Chonkie Chunk object with text, start_index, end_index, token_count

        Returns:
            Dict with chunk data
        """
        return {
            "text": chunk.text,
            "start_index": chunk.start_index,
            "end_index": chunk.end_index,
            "token_count": chunk.token_count,
        }
