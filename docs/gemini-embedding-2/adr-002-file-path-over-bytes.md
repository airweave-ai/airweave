# ADR-002: File Path Input Over In-Memory Bytes

## Status
Accepted

## Context
`embed_file()` needs to receive file content for the Gemini API. Two options: pass raw `bytes` from the caller, or pass a `file_path: str` and let the embedder read from disk.

## Decision
`embed_file()` accepts `file_path: str` and reads the file internally via `aiofiles`. The bytes are discarded after the API call returns.

```python
async def embed_file(self, file_path: str, mime_type: str, *, purpose=...) -> DenseEmbedding:
    self._validate_file_input(file_path, mime_type)
    file_bytes = await self._read_file_bytes(file_path)
    part = Part(inline_data=Blob(data=file_bytes, mime_type=mime_type))
    response = await self._call_multimodal_api(part, purpose)
    # file_bytes goes out of scope here -- GC reclaims
```

## Alternatives Considered

### A. Pass `bytes` from the pipeline
The pipeline already has the entity's `local_path`. If it read the bytes itself, it would hold them in memory across the entire batch processing loop. With `model_copy(deep=True)` at chunk_embed.py:203, each entity copy would duplicate the bytes. A 20MB PDF in a batch of 50 entities = 1GB memory spike.

### B. Pass an `AsyncIterator[bytes]` (streaming)
The Gemini `embed_content` API requires the full `Blob(data=bytes)` upfront -- it doesn't support streaming input. So streaming from disk only to buffer in memory before the call adds complexity without reducing peak memory.

## Consequences
- **Positive**: Zero memory amplification from `model_copy()`. The pipeline never holds file bytes.
- **Positive**: The embedder controls its own I/O lifecycle. File read failures surface as `EmbedderInputError`, consistent with all other validation errors.
- **Positive**: Validation (MIME type, file size, PDF page count) runs before any I/O.
- **Negative**: Requires the file to exist on the local filesystem. This is already guaranteed by Airweave's `FileService` download step.
