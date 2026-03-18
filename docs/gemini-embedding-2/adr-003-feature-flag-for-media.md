# ADR-003: Feature Flag for Audio/Video Media Sync

## Status
Accepted

## Context
Audio and video embedding adds three operational dependencies:
1. `ffmpeg` must be installed in all Docker images (API, worker, Temporal)
2. `pydub` Python library (fallback only; primary path uses ffmpeg)
3. Gemini API costs for transcription (via `generate_content`) and embedding

PDF and image multimodal embedding has no new dependencies -- PyMuPDF is already in `pyproject.toml`, and the Gemini embedding API handles images/PDFs without transcription.

## Decision
Introduce `ENABLE_MEDIA_SYNC: bool = False` in `settings.py`.

### Pipeline-Level Enforcement

The flag is enforced **at the top of `process()`** via `_filter_disabled_media()`, before either pipeline processes the entities. This means audio/video entities are **dropped entirely** — they never reach `text_builder`, `AudioConverter`, or `VideoConverter`:

```python
# In ChunkEmbedProcessor.process()
entities = self._filter_disabled_media(entities, sync_context)

# In _filter_disabled_media()
_MEDIA_MIME_TYPES = {"audio/mpeg", "audio/wav", "video/mp4"}

if not settings.ENABLE_MEDIA_SYNC:
    # Drop audio/video entities entirely
    filtered = [e for e in entities if e.mime_type not in _MEDIA_MIME_TYPES]
```

`_partition_by_embedding_mode()` provides a **secondary routing safeguard** that also checks the flag when routing between native and text pipelines (defense in depth).

When `False` (default):
- Audio/video entities from ANY source are dropped before processing
- No ffmpeg/Gemini transcription cost is incurred
- The `MediaChunker`, `AudioConverter`, and `VideoConverter` exist in code but are never invoked

When `True`:
- Audio/video entities route through `MediaChunker` for segmentation and native embedding
- `VideoConverter` extracts keyframe OCR + audio transcription for BM25 text
- `AudioConverter` transcribes audio for BM25 text

**PDF and image multimodal embedding is always active** when the Gemini embedder is configured. No feature flag needed -- it's a strict improvement over text extraction.

## Alternatives Considered

### A. No feature flag, always enable
Users without ffmpeg would hit runtime errors. Users on pay-per-use Gemini API would see unexpected cost increases from transcription calls.

### B. Separate flags for audio vs video
Over-engineering. Audio and video share the same ffmpeg dependency and the same MediaChunker. If you want one, you want both.

### C. Auto-detect ffmpeg at startup
Would silently degrade if ffmpeg is missing. Explicit opt-in is clearer for operators.

### D. Gate only at the source (e.g., Google Drive)
This was the initial implementation but was found insufficient during cross-validation. If a future source (Slack, Dropbox) emits audio/video entities without its own gate, they would bypass the flag. Pipeline-level enforcement is the correct end-to-end gate. The Google Drive source-level check is retained as defense in depth.

## Consequences
- **Positive**: Zero operational impact for existing deployments. Default behavior unchanged.
- **Positive**: Operators explicitly opt into media processing and its costs.
- **Positive**: ffmpeg is installed in Dockerfiles regardless (for future use), so enabling is a single env var.
- **Positive**: Pipeline-level enforcement means new sources that emit audio/video are automatically gated without needing source-specific flag checks.
- **Negative**: The Google Drive source also checks the flag, creating redundant gating. This is intentional defense-in-depth but could confuse future developers.
