# ADR-003: Feature Flag for Audio/Video Media Sync

## Status
Accepted

## Context
Audio and video embedding adds three operational dependencies:
1. `ffmpeg` must be installed in all Docker images (API, worker, Temporal)
2. `pydub` Python library for audio manipulation
3. Gemini API costs for transcription (via `generate_content`) and embedding

PDF and image multimodal embedding has no new dependencies -- PyMuPDF is already in `pyproject.toml`, and the Gemini embedding API handles images/PDFs without transcription.

## Decision
Introduce `ENABLE_MEDIA_SYNC: bool = False` in `settings.py`. When `False` (default):

- Google Drive connector skips video files (preserving existing behavior)
- Audio/video file extensions (`.mp3`, `.wav`, `.mp4`) are in `SUPPORTED_FILE_EXTENSIONS` but sources gate ingestion
- The `MediaChunker`, `AudioConverter`, and `VideoConverter` exist in code but are never invoked

When `True`:
- Google Drive allows video files through
- Audio/video entities route through `MediaChunker` for segmentation
- Transcription runs via `AudioConverter`/`VideoConverter` for BM25 text

**PDF and image multimodal embedding is always active** when the Gemini embedder is configured. No feature flag needed -- it's a strict improvement over text extraction.

## Alternatives Considered

### A. No feature flag, always enable
Users without ffmpeg would hit runtime errors. Users on pay-per-use Gemini API would see unexpected cost increases from transcription calls.

### B. Separate flags for audio vs video
Over-engineering. Audio and video share the same ffmpeg dependency and the same MediaChunker. If you want one, you want both.

### C. Auto-detect ffmpeg at startup
Would silently degrade if ffmpeg is missing. Explicit opt-in is clearer for operators.

## Consequences
- **Positive**: Zero operational impact for existing deployments. Default behavior unchanged.
- **Positive**: Operators explicitly opt into media processing and its costs.
- **Positive**: ffmpeg is installed in Dockerfiles regardless (for future use), so enabling is a single env var.
- **Negative**: Sources must check the flag individually. Currently only Google Drive is gated; other sources that might yield audio/video would need similar guards.
