# ADR-001: Protocol-Based Multimodal Detection Over Class Inheritance

## Status
Accepted

## Context
Airweave supports 4 dense embedding providers (OpenAI, Mistral, Local/MiniLM, Gemini). Only Gemini supports native file embedding. The pipeline needs to detect multimodal capability at runtime without coupling to a concrete class or breaking existing providers.

## Decision
We introduce `MultimodalDenseEmbedderProtocol` as a `@runtime_checkable` Protocol (PEP 544). The pipeline detects capability via:

```python
if isinstance(embedder, MultimodalDenseEmbedderProtocol):
    # Route to native multimodal pipeline
```

The protocol requires three members:
- `supports_multimodal: bool` (property)
- `supported_mime_types: set[str]` (property)
- `embed_file(file_path, mime_type, *, purpose) -> DenseEmbedding` (async method)

## Error Handling at the Pipeline Boundary

The pipeline catches **both** `EmbedderInputError` and `EmbedderProviderError` in all fallback seams:

```python
except (EmbedderInputError, EmbedderProviderError) as e:
    # Fall back to text pipeline
```

This ensures that transient API failures (provider errors) receive the same graceful fallback as validation failures (input errors). Both exception types are part of the embedder's contract and are expected at the protocol boundary.

Catching both is essential for resilience -- a Gemini API 500 error should not crash the sync when the text pipeline can still produce valid embeddings for the entity.

## Alternatives Considered

### A. ABC with `embed_file()` on all embedders
Every embedder would need to implement `embed_file()`, even if only to raise `NotImplementedError`. This violates Interface Segregation and adds dead code to 3 providers.

### B. Configuration flag (`supports_multimodal` on registry entry)
Would require the pipeline to import registry metadata at runtime instead of checking the live object. Fragile coupling between config and capability.

### C. `hasattr(embedder, 'embed_file')` duck typing
Works but provides no IDE support, no type safety, and no formal contract documentation. Runtime checks via `isinstance()` with a Protocol give the same duck-typing semantics with better tooling.

## Consequences
- **Positive**: OpenAI, Mistral, and Local embedders are completely unaffected. Zero changes to their code.
- **Positive**: Future multimodal providers (e.g., if OpenAI adds vision embedding) only need to add 3 members to opt in.
- **Positive**: `FakeDenseEmbedder` does NOT satisfy the protocol (correctly), while `FakeMultimodalDenseEmbedder` does.
- **Positive**: Catching both error types at the protocol boundary means the pipeline degrades gracefully on both validation and API failures.
- **Negative**: `@runtime_checkable` only checks method/property existence, not signatures. This is a known Python limitation.
