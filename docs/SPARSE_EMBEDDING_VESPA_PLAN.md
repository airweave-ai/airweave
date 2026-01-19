# Implementation Plan: FastEmbed Sparse Embeddings for Vespa

## Overview

This document outlines the plan to use FastEmbed's `Qdrant/bm25` sparse embeddings for Vespa **scoring** instead of Vespa's native BM25. This ensures consistent keyword ranking behavior between Qdrant and Vespa, with the benefits of:

- **Pre-trained vocabulary & IDF** from massive corpus (not collection-dependent)
- **Stopword removal** (built into the model)
- **Learned term weights** (not just raw frequency)
- **Consistent scoring** across both vector databases
- **Index-size independent** - same scoring behavior whether Vespa has 100 docs or 5M docs

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│ MATCHING PHASE (UNCHANGED)                                      │
│                                                                 │
│   Query "Do we have Information Retrieval.pdf?"                │
│                    ↓                                            │
│   userInput(@query) → Vespa inverted index                     │
│                    ↓                                            │
│   Returns 5000 candidates (TARGET_HITS)                        │
│                                                                 │
│   Note: Vespa tokenizer still used for retrieval               │
│   (includes stopwords, but that's OK - retrieval is broad)     │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ FIRST-PHASE RANKING (CHANGED)                                   │
│                                                                 │
│   OLD: bm25(textual_representation) + bm25(payload)            │
│        - IDF from Vespa index (collection-dependent)           │
│        - Stopwords contribute to score                         │
│                                                                 │
│   NEW: sum(query(q_sparse) * attribute(sparse_embedding))      │
│        - IDF from FastEmbed pre-training (fixed)               │
│        - No stopwords (removed by FastEmbed)                   │
│        - Same weights as Qdrant                                │
└─────────────────────────────────────────────────────────────────┘
```

**Key insight**: We only change SCORING, not RETRIEVAL. The inverted index still provides efficient candidate selection.

---

## Current Architecture

### Sparse Embedding Generation
```
ChunkEmbedProcessor
├── generate_sparse=True  → Qdrant (sparse embeddings generated)
└── generate_sparse=False → Vespa (BM25 computed server-side)
```

### Vespa Keyword Search (Current)
- **Retrieval**: `userInput(@query)` → inverted index → 5000 candidates
- **Scoring**: `bm25(textual_representation) + bm25(payload)`
- IDF calculated from ALL documents in Vespa content cluster
- No stopword removal - common words contribute to scores

---

## Target Architecture

### Sparse Embedding Generation
```
ChunkEmbedProcessor
└── Always generates sparse embeddings for ALL destinations
```

### Vespa Keyword Search (New)
- **Retrieval**: UNCHANGED - `userInput(@query)` → inverted index → 5000 candidates
- **Scoring**: `sum(query(q_sparse) * attribute(sparse_embedding))`
  - Sparse embeddings stored as `tensor<float>(token{})` field
  - Uses same FastEmbed model as Qdrant
  - Vocabulary & IDF from pre-trained model (fixed)
  - No stopwords in scoring (FastEmbed removes them)

### Why Keep the Inverted Index for Retrieval?

1. **Efficiency**: Inverted index retrieval is O(query_terms), scanning all docs would be O(collection_size)
2. **5000 candidates is sufficient**: Plenty of room for relevant docs
3. **Vespa's retrieval already favors rare terms**: BM25 in retrieval phase gives higher scores to docs with rare terms
4. **Simplicity**: Fewer changes, easier to implement and test

### Future Optimization (if needed)

If recall issues arise (relevant docs not in top 5000 candidates), we could:
- Add stopword removal to the inverted index
- Increase TARGET_HITS
- Add linguistic processing to better match tokens

---

## Implementation Steps

### Phase 1: Schema Changes

#### 1.1 Update Vespa Schema (`vespa/app/schemas/base_entity.sd`)

Add sparse embedding field:

```sd
# Add after dense_embedding field (around line 152)

# Sparse embedding for keyword SCORING (FastEmbed BM25)
# Mapped tensor: token ID → weight (token IDs as strings for Vespa compatibility)
# Uses same embeddings as Qdrant for consistent keyword SCORING
# Note: Retrieval still uses inverted index via userInput(), this is for SCORING only
field sparse_embedding type tensor<float>(token{}) {
    indexing: attribute
    attribute {
        paged  # Disk-based, not in RAM - only loaded during ranking
    }
}
```

**Memory impact**:
- ~1.6 KB per document (100-200 non-zero tokens × 8 bytes)
- With `paged`: stored on disk, loaded on-demand during ranking
- Does NOT replace inverted index - we keep both

**Note**: All other entity schemas (`file_entity.sd`, `code_file_entity.sd`, `email_entity.sd`, `web_entity.sd`) inherit from or mirror `base_entity.sd` and will need the same field added.

#### 1.2 Update Rank Profiles (`vespa/app/schemas/base_entity.sd`)

Update ranking to use sparse embedding instead of BM25 for **scoring** (retrieval unchanged):

```sd
# In rank-profile default, add input for sparse query:
rank-profile default {
    inputs {
        # ... existing dense embedding inputs (unchanged) ...

        # Sparse embedding for keyword SCORING (FastEmbed BM25)
        query(q_sparse) tensor<float>(token{})
    }

    # ... existing semantic_score() function (unchanged) ...
}

# Update hybrid-rrf profile:
rank-profile hybrid-rrf inherits default {

    # CHANGE: Replace bm25() with sparse embedding dotproduct for SCORING
    # Retrieval still uses inverted index via userInput() in YQL
    function keyword_score() {
        expression: sum(query(q_sparse) * attribute(sparse_embedding))
    }

    # Keep semantic_score() unchanged (uses dense embedding closeness)

    first-phase {
        expression: keyword_score() + semantic_score()
    }

    global-phase {
        rerank-count: 100
        expression {
            reciprocal_rank(keyword_score) +
            reciprocal_rank(semantic_score)
        }
    }

    match-features {
        keyword_score
        semantic_score
    }
}

# Update keyword-only profile:
rank-profile keyword-only inherits default {
    function keyword_score() {
        expression: sum(query(q_sparse) * attribute(sparse_embedding))
    }

    first-phase {
        expression: keyword_score()
    }
}
```

**Architecture clarification**:
- `userInput(@query)` in YQL → inverted index finds candidates (UNCHANGED)
- `keyword_score()` in rank profile → sparse dotproduct scores candidates (NEW)
- We're replacing HOW documents are scored, not HOW they're retrieved

---

### Phase 2: Backend Changes

#### 2.1 Remove `generate_sparse` Flag

**File**: `backend/airweave/platform/sync/processors/chunk_embed.py`

```python
# BEFORE (line 44-51):
def __init__(self, generate_sparse: bool = True):
    """Initialize processor.

    Args:
        generate_sparse: Whether to generate sparse embeddings for hybrid search.
                        Set to True for Qdrant, False for Vespa.
    """
    self._generate_sparse = generate_sparse

# AFTER:
def __init__(self):
    """Initialize processor.

    Always generates both dense and sparse embeddings for all destinations.
    """
    pass  # No configuration needed
```

Update `_embed_entities` method (lines 217-263):
```python
async def _embed_entities(
    self,
    chunk_entities: List[BaseEntity],
    sync_context: "SyncContext",
) -> None:
    """Compute dense and sparse embeddings for all destinations.

    Both Qdrant and Vespa use:
    - 3072-dim dense embeddings for neural search
    - FastEmbed sparse embeddings for keyword search
    """
    if not chunk_entities:
        return

    from airweave.platform.embedders import DenseEmbedder, SparseEmbedder

    # Dense embeddings (3072-dim)
    dense_texts = [e.textual_representation for e in chunk_entities]
    dense_embedder = DenseEmbedder(vector_size=sync_context.collection.vector_size)
    dense_embeddings = await dense_embedder.embed_many(dense_texts, sync_context)

    # Sparse embeddings (always - for consistent keyword search)
    sparse_texts = [
        json.dumps(
            e.model_dump(mode="json", exclude={"airweave_system_metadata"}),
            sort_keys=True,
        )
        for e in chunk_entities
    ]
    sparse_embedder = SparseEmbedder()
    sparse_embeddings = await sparse_embedder.embed_many(sparse_texts, sync_context)

    # Assign embeddings to entities
    for i, entity in enumerate(chunk_entities):
        entity.airweave_system_metadata.dense_embedding = dense_embeddings[i]
        entity.airweave_system_metadata.sparse_embedding = sparse_embeddings[i]

    # Validate
    for entity in chunk_entities:
        if entity.airweave_system_metadata.dense_embedding is None:
            raise SyncFailureError(f"Entity {entity.entity_id} has no dense embedding")
        if entity.airweave_system_metadata.sparse_embedding is None:
            raise SyncFailureError(f"Entity {entity.entity_id} has no sparse embedding")
```

#### 2.2 Simplify ProcessingRequirement Enum

**File**: `backend/airweave/platform/sync/pipeline/enums.py`

```python
# BEFORE:
class ProcessingRequirement(Enum):
    CHUNKS_AND_EMBEDDINGS = "chunks_and_embeddings"
    CHUNKS_AND_EMBEDDINGS_DENSE_ONLY = "chunks_and_embeddings_dense_only"  # Remove this
    TEXT_ONLY = "text_only"
    RAW = "raw"

# AFTER:
class ProcessingRequirement(Enum):
    """What processing a destination expects from Airweave."""

    CHUNKS_AND_EMBEDDINGS = "chunks_and_embeddings"  # Dense + Sparse for all vector DBs
    TEXT_ONLY = "text_only"
    RAW = "raw"
```

#### 2.3 Update Destination Handler

**File**: `backend/airweave/platform/sync/handlers/destination.py`

```python
# BEFORE (lines 36-45):
_PROCESSORS: Dict[ProcessingRequirement, ContentProcessor] = {
    ProcessingRequirement.CHUNKS_AND_EMBEDDINGS: ChunkEmbedProcessor(generate_sparse=True),
    ProcessingRequirement.CHUNKS_AND_EMBEDDINGS_DENSE_ONLY: ChunkEmbedProcessor(
        generate_sparse=False
    ),
    ProcessingRequirement.TEXT_ONLY: TextOnlyProcessor(),
    ProcessingRequirement.RAW: RawProcessor(),
}

# AFTER:
_PROCESSORS: Dict[ProcessingRequirement, ContentProcessor] = {
    ProcessingRequirement.CHUNKS_AND_EMBEDDINGS: ChunkEmbedProcessor(),
    ProcessingRequirement.TEXT_ONLY: TextOnlyProcessor(),
    ProcessingRequirement.RAW: RawProcessor(),
}
```

#### 2.4 Update VespaDestination Processing Requirement

**File**: `backend/airweave/platform/destinations/vespa/destination.py`

```python
# BEFORE (line 59):
processing_requirement = ProcessingRequirement.CHUNKS_AND_EMBEDDINGS_DENSE_ONLY

# AFTER:
processing_requirement = ProcessingRequirement.CHUNKS_AND_EMBEDDINGS
```

#### 2.5 Update Vespa EntityTransformer

**File**: `backend/airweave/platform/destinations/vespa/transformer.py`

Add method to convert FastEmbed sparse embedding to Vespa tensor format:

```python
def _add_embedding_fields(self, fields: Dict[str, Any], entity: BaseEntity) -> None:
    """Add pre-computed embeddings from airweave_system_metadata."""
    meta = entity.airweave_system_metadata
    if meta is None:
        self._logger.warning(
            f"[EntityTransformer] Entity {entity.entity_id} has NO system metadata!"
        )
        return

    # Dense embedding (unchanged)
    dense_emb = meta.dense_embedding
    if dense_emb is not None and isinstance(dense_emb, list) and len(dense_emb) > 0:
        fields["dense_embedding"] = {"values": dense_emb}
    else:
        self._logger.warning(
            f"[EntityTransformer] Entity {entity.entity_id}: No valid dense_embedding"
        )

    # Sparse embedding (NEW)
    sparse_emb = meta.sparse_embedding
    if sparse_emb is not None:
        sparse_tensor = self._convert_sparse_to_vespa_tensor(sparse_emb, entity.entity_id)
        if sparse_tensor:
            fields["sparse_embedding"] = sparse_tensor

def _convert_sparse_to_vespa_tensor(
    self,
    sparse_emb: Any,
    entity_id: str
) -> Optional[Dict[str, Any]]:
    """Convert FastEmbed SparseEmbedding to Vespa mapped tensor format.

    FastEmbed SparseEmbedding has:
    - indices: List[int] - token IDs
    - values: List[float] - token weights

    Vespa mapped tensor format:
    - {"cells": [{"address": {"token": "123"}, "value": 0.5}, ...]}

    We use token IDs as strings since we don't have access to the tokenizer.
    This works because Vespa just needs consistent keys for matching.
    """
    try:
        # Get indices and values from sparse embedding
        if hasattr(sparse_emb, 'indices') and hasattr(sparse_emb, 'values'):
            indices = sparse_emb.indices
            values = sparse_emb.values
        elif isinstance(sparse_emb, dict):
            indices = sparse_emb.get('indices', [])
            values = sparse_emb.get('values', [])
        else:
            self._logger.warning(
                f"[EntityTransformer] Entity {entity_id}: Unknown sparse embedding format"
            )
            return None

        if not indices or not values:
            return None

        # Convert to Vespa cells format
        cells = []
        for idx, val in zip(indices, values):
            cells.append({
                "address": {"token": str(idx)},
                "value": float(val)
            })

        return {"cells": cells}

    except Exception as e:
        self._logger.warning(
            f"[EntityTransformer] Failed to convert sparse embedding for {entity_id}: {e}"
        )
        return None
```

#### 2.6 Update Vespa QueryBuilder

**File**: `backend/airweave/platform/destinations/vespa/query_builder.py`

**No changes needed to retrieval clause** - we keep using `userInput(@query)` for efficient candidate retrieval via inverted index. The sparse embeddings are only used for **ranking** (replacing `bm25()` with `dotproduct(sparse)`).

The existing `_build_retrieval_clause` stays the same:
```python
# BM25 text search clause - KEEP THIS for retrieval
bm25_clause = f"{{targetHits:{TARGET_HITS}}}userInput(@query)"
```

The change is only in the **rank profile** - we replace `bm25(textual_representation)` with sparse vector dotproduct for scoring.

Update `build_params` to include sparse query embedding:

```python
def build_params(
    self,
    queries: List[str],
    limit: int,
    offset: int,
    dense_embeddings: Optional[List[List[float]]],
    sparse_embeddings: Optional[List[Any]] = None,  # NEW parameter
    retrieval_strategy: str = "hybrid",
) -> Dict[str, Any]:
    """Build Vespa query parameters with pre-computed embeddings."""
    primary_query = queries[0] if queries else ""

    # ... existing params setup ...

    # Add dense embeddings (unchanged)
    if dense_embeddings:
        query_params["ranking.features.query(query_embedding)"] = {
            "values": dense_embeddings[0]
        }
        for i, dense_emb in enumerate(dense_embeddings):
            query_params[f"input.query(q{i})"] = {"values": dense_emb}

    # Add sparse embedding for keyword scoring (NEW)
    if sparse_embeddings and retrieval_strategy in ("keyword", "hybrid"):
        sparse_tensor = self._convert_sparse_query_to_tensor(sparse_embeddings[0])
        if sparse_tensor:
            query_params["ranking.features.query(q_sparse)"] = sparse_tensor

    return query_params

def _convert_sparse_query_to_tensor(self, sparse_emb: Any) -> Optional[Dict[str, Any]]:
    """Convert FastEmbed sparse embedding to Vespa query tensor format."""
    try:
        if hasattr(sparse_emb, 'indices') and hasattr(sparse_emb, 'values'):
            indices = sparse_emb.indices
            values = sparse_emb.values
        elif isinstance(sparse_emb, dict):
            indices = sparse_emb.get('indices', [])
            values = sparse_emb.get('values', [])
        else:
            return None

        if not indices or not values:
            return None

        cells = []
        for idx, val in zip(indices, values):
            cells.append({
                "address": {"token": str(idx)},
                "value": float(val)
            })

        return {"cells": cells}
    except Exception:
        return None
```

#### 2.7 Update VespaDestination Search Method

**File**: `backend/airweave/platform/destinations/vespa/destination.py`

Update search to pass sparse embeddings:

```python
async def search(
    self,
    queries: List[str],
    airweave_collection_id: UUID,
    limit: int,
    offset: int,
    filter: Optional[Dict[str, Any]] = None,
    dense_embeddings: Optional[List[List[float]]] = None,
    sparse_embeddings: Optional[List[Any]] = None,  # Now used!
    retrieval_strategy: str = "hybrid",
    temporal_config: Optional[AirweaveTemporalConfig] = None,
) -> List[AirweaveSearchResult]:
    """Execute search against Vespa using pre-computed embeddings."""
    # ... existing validation ...

    # Validate sparse embeddings for keyword/hybrid scoring
    if retrieval_strategy in ("keyword", "hybrid"):
        if not sparse_embeddings:
            raise ValueError(
                "Vespa requires pre-computed sparse embeddings for keyword/hybrid search. "
                "Ensure EmbedQuery operation ran before Retrieval."
            )

    # Build YQL and params (now with sparse embeddings for scoring)
    yql = self._query_builder.build_yql(
        queries, airweave_collection_id, filter, retrieval_strategy
    )
    query_params = self._query_builder.build_params(
        queries, limit, offset, dense_embeddings, sparse_embeddings, retrieval_strategy
    )
    query_params["yql"] = yql

    # ... rest unchanged ...
```

---

### Phase 3: Testing & Migration

#### 3.1 Schema Deployment

1. Update all Vespa schema files with new `sparse_embedding` field
2. Deploy schema changes via `vespa-deploy`
3. Monitor deployment for any errors

#### 3.2 Re-sync Collections

Since sparse embeddings weren't stored before, existing collections need to be re-synced:
- Trigger full sync for each collection
- Or implement backfill script that computes and updates sparse embeddings

#### 3.3 Run Evaluation

Re-run the evaluation suite to compare:
- Vespa keyword (old BM25) vs Vespa keyword (FastEmbed sparse)
- Vespa hybrid (old) vs Vespa hybrid (new)
- Ensure Qdrant and Vespa keyword results are now consistent

---

## File Change Summary

| File | Change Type | Description |
|------|-------------|-------------|
| `vespa/app/schemas/base_entity.sd` | Modify | Add `sparse_embedding` field, update rank profiles |
| `vespa/app/schemas/file_entity.sd` | Modify | Add `sparse_embedding` field (if not inherited) |
| `vespa/app/schemas/code_file_entity.sd` | Modify | Add `sparse_embedding` field |
| `vespa/app/schemas/email_entity.sd` | Modify | Add `sparse_embedding` field |
| `vespa/app/schemas/web_entity.sd` | Modify | Add `sparse_embedding` field |
| `backend/.../sync/processors/chunk_embed.py` | Modify | Remove `generate_sparse` flag, always generate sparse |
| `backend/.../sync/pipeline/enums.py` | Modify | Remove `CHUNKS_AND_EMBEDDINGS_DENSE_ONLY` |
| `backend/.../sync/handlers/destination.py` | Modify | Simplify processor mapping |
| `backend/.../destinations/vespa/destination.py` | Modify | Update processing requirement, pass sparse to query |
| `backend/.../destinations/vespa/transformer.py` | Modify | Add sparse embedding conversion |
| `backend/.../destinations/vespa/query_builder.py` | Modify | Add sparse query tensor parameter |

---

## Rollback Plan

If issues arise:
1. Revert `processing_requirement` in VespaDestination to `DENSE_ONLY`
2. Revert rank profiles to use `bm25()` functions
3. Sparse embedding field can remain (unused but harmless)

---

## FAQ

### Does this affect TARGET_HITS?
**No.** TARGET_HITS controls candidate retrieval via `userInput()` / `nearestNeighbor()`. Since we keep the inverted index for retrieval, TARGET_HITS stays at 5000.

### Will this blow up memory?
**No.**
- Sparse embeddings use `paged` attribute (disk-based, not RAM)
- ~1.6 KB per doc vs 6 KB for dense embeddings
- Inverted index memory usage unchanged

### What about retrieval performance?
**Unchanged.** We keep `userInput(@query)` which uses the inverted index for O(query_terms) retrieval. Sparse vectors are only used for scoring the candidates.

### Summary: What changes vs what stays the same

| Component | Current | After Change |
|-----------|---------|--------------|
| **Retrieval mechanism** | `userInput()` + inverted index | UNCHANGED |
| **Keyword scoring** | `bm25(textual_representation)` | `sum(q_sparse * sparse_embedding)` |
| **Dense retrieval** | nearestNeighbor + HNSW | UNCHANGED |
| **Dense scoring** | closeness() | UNCHANGED |
| **Memory (RAM)** | Inverted index + HNSW | UNCHANGED (sparse is paged) |
| **Disk storage** | +6KB/doc (dense) | +1.6KB/doc (sparse) |

---

## Future Considerations

1. **Token ID vs Token String**: Currently using token IDs as strings. If we need actual tokens for debugging, we'd need to expose the FastEmbed tokenizer.

2. **Retrieval optimization**: If recall issues arise (relevant docs not in top 5000 candidates), we could:
   - Add stopword removal to the inverted index
   - Increase TARGET_HITS
   - Add linguistic processing configuration

3. **Memory optimization**: If `paged` attribute causes latency issues, we could:
   - Use `bfloat16` precision for sparse weights
   - Reduce number of tokens stored (top-K only)

4. **SPLADE**: Vespa has a built-in SPLADE embedder. Future work could evaluate SPLADE vs FastEmbed BM25.
