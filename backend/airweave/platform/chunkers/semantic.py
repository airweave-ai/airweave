"""Semantic chunker using NeuralChunker with SentenceChunker safety net."""

from typing import Any, Dict, List, Optional

from airweave.core.logging import logger
from airweave.platform.chunkers._base import BaseChunker
from airweave.platform.sync.async_helpers import run_in_thread_pool
from airweave.platform.sync.exceptions import SyncFailureError


class SemanticChunker(BaseChunker):
    """Singleton semantic chunker with local inference (no API calls).

    Two-stage approach (internal implementation detail):
    1. SemanticChunker: Detects semantic boundaries via embedding similarity
    2. SentenceChunker: Safety net to split any chunks exceeding token limit

    The chunker is shared across all syncs in the pod to avoid reloading
    the embedding model for every sync job.
    """

    # Configuration constants
    MAX_TOKENS_PER_CHUNK = 8192  # OpenAI text-embedding-3-small hard limit (safety net)
    SEMANTIC_CHUNK_SIZE = 2048  # Soft target for semantic groups (better search quality)
    OVERLAP_TOKENS = 128  # Token overlap between chunks

    # SemanticChunker configuration
    # Available embedding models (sorted by speed, fastest first):
    #
    # Model2Vec models (DEFAULT - included with chonkie[semantic]):
    #   - "minishlab/potion-base-8M"   (8M params,  fastest ~0.5s/doc, good quality)
    #   - "minishlab/potion-base-32M"  (32M params, fast ~1s/doc, better quality)
    #   - "minishlab/potion-base-128M" (128M params, medium ~2-3s/doc, best Model2Vec)
    #
    # SentenceTransformer models (requires: poetry add sentence-transformers):
    #   - "all-MiniLM-L6-v2"    (33M params,  fast ~1-2s/doc, good quality)
    #   - "all-MiniLM-L12-v2"   (66M params,  medium ~2-3s/doc, better quality)
    #   - "all-mpnet-base-v2"   (110M params, medium ~3-5s/doc, best quality)
    #
    # Note: These models are ONLY for finding semantic boundaries (chunking decisions).
    # Final search embeddings use OpenAI text-embedding-3-small separately.
    EMBEDDING_MODEL = "minishlab/potion-base-128M"  # Default: Good speed/quality balance

    SIMILARITY_THRESHOLD = 0.3  # 0-1: Lower=larger chunks, Higher=smaller chunks
    SIMILARITY_WINDOW = 10  # Number of sentences to compare for similarity
    MIN_SENTENCES_PER_CHUNK = 1  # Prevent tiny fragment chunks
    MIN_CHARACTERS_PER_SENTENCE = 24  # Minimum chars per sentence

    # Advanced SemanticChunker features
    SKIP_WINDOW = 0  # 0=disabled, >0=merge non-consecutive similar groups
    FILTER_WINDOW = 5  # Savitzky-Golay filter window length
    FILTER_POLYORDER = 3  # Polynomial order for Savitzky-Golay filter
    FILTER_TOLERANCE = 0.2  # Filter boundary detection tolerance

    # Sentence splitting delimiters
    SENTENCE_DELIMITERS = [". ", "! ", "? ", "\n"]
    INCLUDE_DELIMITER = "prev"  # Include delimiter with previous sentence

    # Tokenizer for accurate OpenAI token counting
    TOKENIZER = "cl100k_base"

    # Singleton instance
    _instance: Optional["SemanticChunker"] = None

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

        self._semantic_chunker = None  # Lazy init
        self._sentence_chunker = None  # Lazy init
        self._tiktoken_tokenizer = None  # Lazy init
        self._initialized = True

        logger.debug(
            f"SemanticChunker singleton initialized "
            f"(model: {self.EMBEDDING_MODEL}, max_tokens: {self.MAX_TOKENS_PER_CHUNK})"
        )

    def _ensure_chunkers(self):
        """Lazy initialization of chunker models.

        Initializes SemanticChunker (embedding similarity) + SentenceChunker (safety net).
        SemanticChunker uses local embedding model for fast semantic boundary detection.

        Raises:
            SyncFailureError: If model loading fails (infrastructure error)
        """
        if self._semantic_chunker is not None:
            return

        try:
            import tiktoken
            from chonkie import SemanticChunker as ChonkieSemanticChunker
            from chonkie import SentenceChunker

            # Initialize tiktoken tokenizer for accurate OpenAI token counting
            self._tiktoken_tokenizer = tiktoken.get_encoding(self.TOKENIZER)

            # Initialize Chonkie's SemanticChunker with ALL parameters explicit
            # NOTE: Uses local embedding model for chunking decisions (fast, no API calls)
            # This is separate from OpenAI embeddings used later for final search vectors
            self._semantic_chunker = ChonkieSemanticChunker(
                # Embedding model for semantic similarity computation
                embedding_model=self.EMBEDDING_MODEL,
                # Size and threshold controls
                chunk_size=self.SEMANTIC_CHUNK_SIZE,  # Soft target (2048 for search quality)
                threshold=self.SIMILARITY_THRESHOLD,  # Lower=larger chunks, Higher=smaller
                # Similarity calculation
                similarity_window=self.SIMILARITY_WINDOW,  # Sentences to compare
                # Sentence splitting configuration
                min_sentences_per_chunk=self.MIN_SENTENCES_PER_CHUNK,
                min_characters_per_sentence=self.MIN_CHARACTERS_PER_SENTENCE,
                delim=self.SENTENCE_DELIMITERS,
                include_delim=self.INCLUDE_DELIMITER,
                # Advanced features (Savitzky-Golay filtering, skip-window merging)
                skip_window=self.SKIP_WINDOW,  # Merge non-consecutive similar groups
                filter_window=self.FILTER_WINDOW,  # Savitzky-Golay filter window
                filter_polyorder=self.FILTER_POLYORDER,  # Polynomial order
                filter_tolerance=self.FILTER_TOLERANCE,  # Boundary tolerance
            )

            # Initialize SentenceChunker for safety net (hard limit enforcement)
            self._sentence_chunker = SentenceChunker(
                tokenizer=self._tiktoken_tokenizer,
                chunk_size=self.MAX_TOKENS_PER_CHUNK,
                chunk_overlap=self.OVERLAP_TOKENS,
                min_sentences_per_chunk=1,
            )

            logger.info(
                f"Loaded SemanticChunker (model: {self.EMBEDDING_MODEL}, "
                f"target_size: {self.SEMANTIC_CHUNK_SIZE}, threshold: {self.SIMILARITY_THRESHOLD}, "
                f"hard_limit: {self.MAX_TOKENS_PER_CHUNK}) + SentenceChunker safety net"
            )

        except Exception as e:
            raise SyncFailureError(f"Failed to initialize chunkers: {e}")

    async def chunk_batch(self, texts: List[str]) -> List[List[Dict[str, Any]]]:
        """Chunk a batch of texts with two-stage approach.

        Stage 1: SemanticChunker detects semantic boundaries (embedding similarity)
        Stage 1.5: Recount tokens with tiktoken cl100k_base (OpenAI compatibility)
        Stage 2: SentenceChunker splits any chunks exceeding MAX_TOKENS_PER_CHUNK

        Uses run_in_thread_pool because Chonkie is synchronous (avoids blocking event loop).

        Args:
            texts: List of textual representations to chunk

        Returns:
            List of chunk lists (one per input text), where each chunk is a dict

        Raises:
            SyncFailureError: If model initialization or batch processing fails
        """
        self._ensure_chunkers()

        # Stage 1: Semantic chunking (finds topic boundaries via embedding similarity)
        try:
            semantic_results = await run_in_thread_pool(self._semantic_chunker.chunk_batch, texts)
        except Exception as e:
            raise SyncFailureError(f"SemanticChunker batch processing failed: {e}")

        # Stage 1.5: Recount tokens with tiktoken (semantic chunker uses its own tokenizer)
        semantic_results_with_tiktoken = await run_in_thread_pool(
            self._recount_tokens_with_tiktoken, semantic_results
        )

        # Stage 2: Safety net (batched for efficiency, uses tiktoken counts)
        final_results = await run_in_thread_pool(
            self._apply_safety_net_batched, semantic_results_with_tiktoken
        )

        # Validate all chunks meet requirements
        for doc_chunks in final_results:
            for chunk in doc_chunks:
                # Check for empty chunks
                if not chunk["text"] or not chunk["text"].strip():
                    raise SyncFailureError("PROGRAMMING ERROR: Empty chunk produced by chunker")

                # Check token limit enforced (using tiktoken counts)
                if chunk["token_count"] > self.MAX_TOKENS_PER_CHUNK:
                    raise SyncFailureError(
                        f"PROGRAMMING ERROR: Chunk has {chunk['token_count']} tokens "
                        f"after safety net (max: {self.MAX_TOKENS_PER_CHUNK}). "
                        "SentenceChunker failed to enforce hard limit."
                    )

        return final_results

    def _recount_tokens_with_tiktoken(self, semantic_results: List[List[Any]]) -> List[List[Any]]:
        """Recount all chunks with tiktoken cl100k_base for OpenAI compatibility.

        SemanticChunker uses its own tokenizer internally, so we recount
        with tiktoken to get accurate token counts for OpenAI embedding API.

        Args:
            semantic_results: Chunks from SemanticChunker with its own token counts

        Returns:
            Same chunks but with token_count field updated to tiktoken counts
        """
        for chunks in semantic_results:
            for chunk in chunks:
                # Recount with tiktoken
                chunk.token_count = len(self._tiktoken_tokenizer.encode(chunk.text))

        return semantic_results

    def _apply_safety_net_batched(
        self, semantic_results: List[List[Any]]
    ) -> List[List[Dict[str, Any]]]:
        """Split oversized chunks using batched sentence chunking.

        Example flow:
        # INPUT: semantic_results (List of List of Chunk objects)
            semantic_results = [
                # Document 0: 3 chunks, one oversized
                [Chunk(text="...", token_count=2000),    # OK
                Chunk(text="...", token_count=9500),    # OVERSIZED!
                Chunk(text="...", token_count=1500)],   # OK

                # Document 1: 2 chunks, both OK
                [Chunk(text="...", token_count=3000),    # OK
                Chunk(text="...", token_count=4000)],   # OK

                # Document 2: 1 chunk, oversized
                [Chunk(text="...", token_count=10000)]   # OVERSIZED!
            ]

            # STEP 1: Collect oversized chunks
            oversized_texts = [
                "...(9500 token text)...",   # From doc 0, chunk 1
                "...(10000 token text)..."   # From doc 2, chunk 0
            ]

            oversized_map = {
                0: (0, 1),  # Position 0 in oversized_texts → doc_idx=0, chunk_idx=1
                1: (2, 0),  # Position 1 in oversized_texts → doc_idx=2, chunk_idx=0
            }

            # STEP 2: Batch split with SentenceChunker
            split_results = sentence_chunker.chunk_batch(oversized_texts)
            # Returns:
            split_results = [
                # Position 0 (doc 0, chunk 1) → split into 2
                [Chunk(text="...", token_count=4750),
                Chunk(text="...", token_count=4750)],

                # Position 1 (doc 2, chunk 0) → split into 2
                [Chunk(text="...", token_count=5000),
                Chunk(text="...", token_count=5000)]
            ]

            split_results_by_pos = {
                0: [Chunk(...), Chunk(...)],  # 2 sub-chunks
                1: [Chunk(...), Chunk(...)]   # 2 sub-chunks
            }

            # STEP 3: Reconstruct final results
            final_results = [
                # Document 0: chunk 0 (OK), chunk 1 (REPLACED with 2 sub-chunks), chunk 2 (OK)
                [
                    {"text": "...", "token_count": 2000},     # Original chunk 0
                    {"text": "...", "token_count": 4750},     # Sub-chunk 0 from split
                    {"text": "...", "token_count": 4750},     # Sub-chunk 1 from split
                    {"text": "...", "token_count": 1500}      # Original chunk 2
                ],

                # Document 1: both OK, kept as-is
                [
                    {"text": "...", "token_count": 3000},
                    {"text": "...", "token_count": 4000}
                ],

                # Document 2: chunk 0 (REPLACED with 2 sub-chunks)
                [
                    {"text": "...", "token_count": 5000},     # Sub-chunk 0 from split
                    {"text": "...", "token_count": 5000}      # Sub-chunk 1 from split
                ]
            ]

        Args:
            semantic_results: Chunks from SemanticChunker with tiktoken counts

        Returns:
            Final chunks as dicts, all guaranteed ≤ MAX_TOKENS_PER_CHUNK
        """
        # Collect oversized chunks with position mapping
        oversized_texts = []
        oversized_map = {}  # position in oversized_texts → (doc_idx, chunk_idx)

        for doc_idx, chunks in enumerate(semantic_results):
            for chunk_idx, chunk in enumerate(chunks):
                if chunk.token_count > self.MAX_TOKENS_PER_CHUNK:
                    pos = len(oversized_texts)
                    oversized_texts.append(chunk.text)
                    oversized_map[pos] = (doc_idx, chunk_idx)

        # Batch process all oversized chunks with SentenceChunker
        split_results_by_position = {}
        if oversized_texts:
            logger.debug(
                f"Safety net: splitting {len(oversized_texts)} chunks "
                f"exceeding {self.MAX_TOKENS_PER_CHUNK} tokens"
            )
            split_results = self._sentence_chunker.chunk_batch(oversized_texts)
            split_results_by_position = dict(enumerate(split_results))

        # Reconstruct final results
        final_results = []
        for doc_idx, chunks in enumerate(semantic_results):
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
                f"Safety net split {len(oversized_texts)} chunks "
                f"exceeding {self.MAX_TOKENS_PER_CHUNK} tokens"
            )

        return final_results

    def _convert_chunk(self, chunk) -> Dict[str, Any]:
        """Convert Chonkie Chunk object to dict format.

        Token counts have already been recounted with tiktoken in
        _recount_tokens_with_tiktoken(), so we just use them directly.

        Args:
            chunk: Chonkie Chunk object with tiktoken token_count

        Returns:
            Dict with chunk data and accurate OpenAI token count
        """
        return {
            "text": chunk.text,
            "start_index": chunk.start_index,
            "end_index": chunk.end_index,
            "token_count": chunk.token_count,  # Already tiktoken count
        }
