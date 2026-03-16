# ADR-002: File Path Input Over In-Memory Bytes

## Status
Accepted

## Context
`embed_file()` needs to receive file content for the Gemini API. Two options: pass raw `bytes` from the caller, or pass a `file_path: str` and let the embedder read from disk.

This decision also affects how audio and video files are split into segments for embedding within Gemini's duration and size limits.

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

### Audio Chunking: ffmpeg Stream-Copy Over pydub RAM Decode

The same file-path-first principle extends to `MediaChunker`. Audio splitting uses **ffmpeg stream-copy** (`-c copy`) instead of pydub's `AudioSegment.from_file()`, which decodes the entire file into memory:

```python
# ffmpeg stream-copy: zero decode, zero memory spike
cmd = ["ffmpeg", "-y", "-ss", str(start), "-i", file_path,
       "-t", str(seg_duration), "-c", "copy", segment_path]
```

Duration is detected via `ffprobe` (a metadata read, not a full decode). pydub is only used as a fallback when ffmpeg is unavailable.

### Size-Aware Segment Sizing

For files that fit within the duration limit but exceed Gemini's 20MB `inline_data` limit (e.g., a 40-second uncompressed WAV at 23MB), the chunker calculates segment duration from bitrate:

```python
if file_size > _MAX_SINGLE_FILE_BYTES and duration_seconds > 0:
    bytes_per_second = file_size / duration_seconds
    size_limited_max = (_MAX_SINGLE_FILE_BYTES * 0.95) / bytes_per_second  # 5% safety margin
    audio_max = min(audio_max, size_limited_max)
```

The 5% safety margin accounts for container/header overhead (e.g., WAV headers, MP3 frame boundaries).

## Alternatives Considered

### A. Pass `bytes` from the pipeline
The pipeline already has the entity's `local_path`. If it read the bytes itself, it would hold them in memory across the entire batch processing loop. With `model_copy(deep=True)` at chunk_embed.py:203, each entity copy would duplicate the bytes. A 20MB PDF in a batch of 50 entities = 1GB memory spike.

### B. Pass an `AsyncIterator[bytes]` (streaming)
The Gemini `embed_content` API requires the full `Blob(data=bytes)` upfront -- it doesn't support streaming input. So streaming from disk only to buffer in memory before the call adds complexity without reducing peak memory.

### C. pydub for all audio splitting
pydub's `AudioSegment.from_file()` decodes the entire file into uncompressed PCM in memory. A 20MB compressed MP3 expands to hundreds of megabytes of PCM. For a Temporal worker processing multiple entities concurrently, this causes OOM. ffmpeg stream-copy never decodes the audio, operating directly on the compressed bitstream.

## Consequences
- **Positive**: Zero memory amplification from `model_copy()`. The pipeline never holds file bytes.
- **Positive**: The embedder controls its own I/O lifecycle. File read failures surface as `EmbedderInputError`, consistent with all other validation errors.
- **Positive**: Validation (MIME type, file size, PDF page count) runs before any I/O.
- **Positive**: Audio chunking via ffmpeg stream-copy avoids OOM on large files. No full decode into RAM.
- **Positive**: Size-aware segment sizing handles edge cases where short files exceed the size limit.
- **Negative**: Requires the file to exist on the local filesystem. This is already guaranteed by Airweave's `FileService` download step.
- **Negative**: Requires ffmpeg installed in all worker containers. This is already the case (Dockerfiles include ffmpeg for video processing).
