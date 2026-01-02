# Vespa Integration Notes

## Deployment

To start Vespa locally:

```bash
cd backend/airweave/vespa
docker-compose up -d
./deploy.sh
```

## Schema Design

The `base_entity` schema implements:

### Chunking
- Automatic chunking via Vespa's `chunk fixed-length 1024` indexing
- No pre-chunking needed from Airweave

### Embeddings (Two-tier)
1. **Small embeddings** (`chunk_small_embeddings`): int8 binary packed, 96 dimensions
   - Used for fast ANN retrieval with hamming distance
   - 32x faster than float cosine similarity

2. **Large embeddings** (`chunk_large_embeddings`): bfloat16, 768 dimensions
   - Used for accurate ranking
   - Not indexed (only used in second-phase ranking)

### Ranking Profiles

1. **hybrid-rrf**: Reciprocal Rank Fusion
   - Recommended when no training data available
   - Combines lexical and semantic scores by rank position

2. **hybrid-linear**: Simple linear combination
   - Uses atan normalization for BM25
   - Manual weight tuning

### Multi-tenant Isolation
- `collection_id` field with `fast-search` attribute
- All queries must include `collection_id` filter

## Resources

- [Vespa RAG Blueprint](https://docs.vespa.ai/en/llms-rag.html)
- [Hybrid Text Search Tutorial](https://docs.vespa.ai/en/tutorials/text-search.html)
- [Phased Ranking](https://docs.vespa.ai/en/phased-ranking.html)
- [ColBERT Embedder](https://blog.vespa.ai/announcing-colbert-embedder-in-vespa/)
