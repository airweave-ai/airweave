# Code Chunker Integration Plan

## Overview
Add CodeChunker for code entities (CodeFileEntity) using AST-based parsing, while keeping SemanticChunker for textual entities.

## Key Findings from Chonkie Code

### 1. "auto" Language Detection
✅ **Supported** (line 46, 79 in code.py):
```python
language: Union[Literal["auto"], Any] = "auto"  # Default
if language == "auto":
    self.magika = Magika()  # Google's language detection
```

### 2. CodeChunker chunk_size Behavior
**Mostly hard limit with edge cases**:
- Lines 140-157: Recursively splits nodes >chunk_size
- **BUT**: If single AST node (massive function) has no children, it can't split
- **Verdict**: STILL need SentenceChunker safety net

### 3. Supported Languages
From tree-sitter-language-pack (need to verify vs our code extensions):
- **Confirmed**: python, javascript, typescript, java, cpp, c, go, rust
- **Need to check**: ruby (.rb), php (.php), swift (.swift), kotlin (.kt, .kts)

Our code extensions (entity_pipeline.py lines 727-743):
`.py`, `.js`, `.ts`, `.tsx`, `.jsx`, `.java`, `.cpp`, `.c`, `.h`, `.hpp`, `.go`, `.rs`, `.rb`, `.php`, `.swift`, `.kt`, `.kts`

**Action**: Remove unsupported extensions or verify tree-sitter-language-pack support

## Architecture

### Entity Routing
```
EntityPipeline._chunk_and_multiply_entities()
  → Partition entities by type
      - CodeFileEntity → CodeChunker (AST-based)
      - All others → SemanticChunker (embedding similarity)
  → Chunk each partition
  → Merge results
  → Return all chunk entities
```

## Implementation

### 1. Create CodeChunker (`platform/chunkers/code.py`)

```python
from typing import Any, Dict, List, Optional
from airweave.core.logging import logger
from airweave.platform.chunkers._base import BaseChunker
from airweave.platform.sync.async_helpers import run_in_thread_pool
from airweave.platform.sync.exceptions import SyncFailureError

class CodeChunker(BaseChunker):
    """Singleton code chunker using AST-based parsing.
    
    Uses tree-sitter to parse code and chunk at logical boundaries
    (functions, classes, methods) while preserving structure.
    
    Note: Even though CodeChunker respects chunk_size, single large AST nodes
    without children (massive functions) can exceed the limit, so we still
    use SentenceChunker as a safety net.
    """
    
    # Configuration
    MAX_TOKENS_PER_CHUNK = 8192  # OpenAI hard limit (safety net)
    CHUNK_SIZE = 2048  # Target chunk size for AST grouping
    OVERLAP_TOKENS = 128  # For safety net
    TOKENIZER = "cl100k_base"
    
    # Supported file extensions (verified against tree-sitter-language-pack)
    SUPPORTED_EXTENSIONS = {
        ".py", ".js", ".ts", ".tsx", ".jsx",  # Python, JavaScript, TypeScript
        ".java", ".cpp", ".c", ".h", ".hpp",  # Java, C, C++
        ".go", ".rs",                         # Go, Rust
        # TODO: Verify these are supported by tree-sitter-language-pack:
        # ".rb", ".php", ".swift", ".kt", ".kts"
    }
    
    _instance: Optional["CodeChunker"] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._code_chunker = None
        self._sentence_chunker = None
        self._tiktoken_tokenizer = None
        self._initialized = True
    
    def _ensure_chunkers(self):
        if self._code_chunker is not None:
            return
        
        try:
            import tiktoken
            from chonkie import CodeChunker as ChonkieCodeChunker, SentenceChunker
            
            self._tiktoken_tokenizer = tiktoken.get_encoding(self.TOKENIZER)
            
            # Initialize CodeChunker with auto language detection
            # Uses Magika (Google's deep learning language detector)
            self._code_chunker = ChonkieCodeChunker(
                language="auto",  # Auto-detect from code content
                tokenizer=self._tiktoken_tokenizer,
                chunk_size=self.CHUNK_SIZE,
                include_nodes=False,
            )
            
            # Safety net: Even with AST-based splitting, single large nodes
            # (massive functions with no children) can exceed chunk_size
            self._sentence_chunker = SentenceChunker(
                tokenizer=self._tiktoken_tokenizer,
                chunk_size=self.MAX_TOKENS_PER_CHUNK,
                chunk_overlap=self.OVERLAP_TOKENS,
                min_sentences_per_chunk=1,
            )
            
            logger.info(
                f"Loaded CodeChunker (auto-detect, target: {self.CHUNK_SIZE}) + "
                f"SentenceChunker safety net (hard limit: {self.MAX_TOKENS_PER_CHUNK})"
            )
        except Exception as e:
            raise SyncFailureError(f"Failed to initialize CodeChunker: {e}")
    
    async def chunk_batch(self, texts: List[str]) -> List[List[Dict[str, Any]]]:
        """Chunk code with AST parsing + safety net."""
        self._ensure_chunkers()
        
        # Stage 1: AST-based code chunking
        try:
            code_results = await run_in_thread_pool(
                self._code_chunker.chunk_batch, texts
            )
        except Exception as e:
            # CodeChunker failure = SyncFailureError (not entity-level)
            raise SyncFailureError(f"CodeChunker batch processing failed: {e}")
        
        # Stage 2: Safety net for edge cases (large single functions)
        final_results = await run_in_thread_pool(
            self._apply_safety_net_batched, code_results
        )
        
        # Validation
        for doc_chunks in final_results:
            for chunk in doc_chunks:
                if not chunk["text"] or not chunk["text"].strip():
                    raise SyncFailureError("Empty chunk produced by CodeChunker")
                if chunk["token_count"] > self.MAX_TOKENS_PER_CHUNK:
                    raise SyncFailureError(
                        f"Chunk has {chunk['token_count']} tokens after safety net"
                    )
        
        return final_results
    
    def _apply_safety_net_batched(self, code_results):
        """Same implementation as SemanticChunker._apply_safety_net_batched."""
        # ... copy from SemanticChunker ...
```

### 2. Update Entity Pipeline (`entity_pipeline.py`)

**Rename `_chunk_and_multiply_entities()` to `_chunk_entities()` and add routing**:

```python
async def _chunk_entities(
    self,
    entities: List[BaseEntity],
    sync_context: SyncContext,
) -> List[BaseEntity]:
    """Chunk entities using type-specific chunkers.
    
    Routing:
    - CodeFileEntity → CodeChunker (AST-based)
    - All others → SemanticChunker (embedding similarity)
    """
    if not entities:
        sync_context.logger.debug("No entities to chunk (all failed conversion)")
        return []
    
    from airweave.platform.entities._base import CodeFileEntity
    
    # Partition entities by type
    code_entities = [e for e in entities if isinstance(e, CodeFileEntity)]
    textual_entities = [e for e in entities if not isinstance(e, CodeFileEntity)]
    
    sync_context.logger.info(
        f"Entity routing: {len(code_entities)} code, {len(textual_entities)} textual"
    )
    
    # Chunk each partition with appropriate chunker
    all_chunk_entities = []
    
    if code_entities:
        code_chunks = await self._chunk_with_code_chunker(code_entities, sync_context)
        all_chunk_entities.extend(code_chunks)
    
    if textual_entities:
        text_chunks = await self._chunk_with_semantic_chunker(textual_entities, sync_context)
        all_chunk_entities.extend(text_chunks)
    
    # Statistics and validation
    await self._log_chunk_statistics(all_chunk_entities, sync_context)
    
    sync_context.logger.info(
        f"Entity multiplication: {len(entities)} → {len(all_chunk_entities)} chunk entities"
    )
    
    return all_chunk_entities
```

**Add chunker helper methods**:

```python
async def _chunk_with_semantic_chunker(
    self, entities: List[BaseEntity], sync_context: SyncContext
) -> List[BaseEntity]:
    """Chunk textual entities with SemanticChunker."""
    from airweave.platform.chunkers.semantic import SemanticChunker
    
    chunker = SemanticChunker()
    texts = [e.textual_representation for e in entities]
    
    try:
        chunk_lists = await chunker.chunk_batch(texts)
    except SyncFailureError:
        raise
    except Exception as e:
        raise SyncFailureError(f"SemanticChunker failed: {e}")
    
    return await self._multiply_entities_from_chunks(entities, chunk_lists, sync_context)

async def _chunk_with_code_chunker(
    self, entities: List[BaseEntity], sync_context: SyncContext
) -> List[BaseEntity]:
    """Chunk code entities with CodeChunker."""
    from airweave.platform.chunkers.code import CodeChunker
    
    chunker = CodeChunker()
    texts = [e.textual_representation for e in entities]
    
    try:
        chunk_lists = await chunker.chunk_batch(texts)
    except SyncFailureError:
        raise  # CodeChunker failure = sync failure
    except Exception as e:
        raise SyncFailureError(f"CodeChunker failed: {e}")
    
    return await self._multiply_entities_from_chunks(entities, chunk_lists, sync_context)

async def _multiply_entities_from_chunks(
    self, entities: List[BaseEntity], chunk_lists: List[List[Dict]], sync_context
) -> List[BaseEntity]:
    """Create chunk entities from chunk dicts (shared logic for both chunkers)."""
    chunk_entities = []
    failed_entities = []
    
    for entity, chunks in zip(entities, chunk_lists, strict=True):
        if not chunks:
            sync_context.logger.warning(
                f"No chunks for {entity.__class__.__name__}[{entity.entity_id}]"
            )
            failed_entities.append(entity)
            continue
        
        # Create one entity per chunk
        for chunk_idx, chunk in enumerate(chunks):
            # Validate chunk has text
            if not chunk["text"] or not chunk["text"].strip():
                sync_context.logger.error(
                    f"Empty chunk for {entity.entity_id} - skipping entity"
                )
                failed_entities.append(entity)
                break
            
            # Clone entity
            chunk_entity = entity.model_copy(deep=True)
            chunk_entity.textual_representation = chunk["text"]
            
            # Metadata must exist
            if chunk_entity.airweave_system_metadata is None:
                raise SyncFailureError(f"No metadata for {entity.entity_id}")
            
            # Set chunk_index
            chunk_entity.airweave_system_metadata.chunk_index = chunk_idx
            chunk_entities.append(chunk_entity)
    
    # Mark failed entities as skipped
    if failed_entities:
        failed_entities = list(set(failed_entities))  # Deduplicate
        await sync_context.progress.increment("skipped", len(failed_entities))
    
    # Validate chunk_index set
    for chunk_entity in chunk_entities:
        if chunk_entity.airweave_system_metadata.chunk_index is None:
            raise SyncFailureError(f"chunk_index not set for {chunk_entity.entity_id}")
    
    return chunk_entities

async def _log_chunk_statistics(
    self, chunk_entities: List[BaseEntity], sync_context: SyncContext
) -> None:
    """Log chunk token statistics (min/max/avg)."""
    if not chunk_entities:
        return
    
    import tiktoken
    tokenizer = tiktoken.get_encoding("cl100k_base")
    token_counts = [
        len(tokenizer.encode(e.textual_representation))
        for e in chunk_entities
    ]
    
    sync_context.logger.info(
        f"Chunk statistics: min={min(token_counts)}, max={max(token_counts)}, "
        f"avg={sum(token_counts) / len(token_counts):.1f}"
    )
```

## Error Handling

**Critical**:
- CodeChunker failure → **SyncFailureError** (fail entire sync)
- Entity produces no chunks → Skip entity (mark as skipped)
- Empty chunk → Skip entity
- **NEVER** fallback to SemanticChunker silently

## Files

**New**:
- `backend/airweave/platform/chunkers/code.py`

**Modified**:
- `backend/airweave/platform/chunkers/__init__.py`
- `backend/airweave/platform/sync/entity_pipeline.py` (refactor _chunk_and_multiply_entities)
- `backend/pyproject.toml` (add chonkie[code])

## Testing

```bash
poetry run pytest airweave/platform/sync/test/main.py::test_pipeline_process_github -s -v
```

