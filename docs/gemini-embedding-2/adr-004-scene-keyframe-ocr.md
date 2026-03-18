# ADR-004: Scene-Based Keyframe OCR for Video Text Extraction

## Status
Accepted

## Context
Video files often contain valuable text content -- slide titles in presentations, code in screen recordings, chat messages in meeting recordings, UI labels in product demos. This text needs to be extracted into `textual_representation` for BM25 sparse scoring and answer generation.

The `VideoConverter` needs a strategy to extract this text that is:
1. Efficient (does not process every frame of a 2-minute video)
2. Cost-effective (minimizes API calls)
3. Comprehensive (captures text that changes throughout the video)
4. Resilient (degrades gracefully when OCR providers are unavailable)

## Decision
Use **scene-based keyframe extraction** via ffmpeg's scene detection filter, followed by OCR of each keyframe:

```python
# 1. Extract keyframes at scene changes (not fixed intervals)
cmd = ["ffmpeg", "-y", "-i", video_path,
       "-vf", f"select='gt(scene\\,{threshold})',showinfo",
       "-vsync", "vfr",
       "-frames:v", str(max_frames),  # Cap at 30
       "-q:v", "2",                    # High-quality JPEG
       output_pattern]

# 2. OCR each keyframe via Docling/Mistral (existing provider)
# 3. Fallback to Gemini vision if OCR provider unavailable
# 4. Deduplicate consecutive frames >80% similar
# 5. Combine with audio transcription
```

The approach is two-pronged:
- **Visual OCR**: Scene keyframes capture text visible on screen
- **Audio transcription**: ffmpeg audio extraction + `AudioConverter` captures spoken content

Both are combined into `textual_representation`:
```
## Visual Content (OCR)
<deduplicated OCR text from keyframes>

## Audio Transcript
<transcription from audio track>
```

### Configuration
- `MULTIMODAL_VIDEO_SCENE_THRESHOLD`: 0.3 default (0.0-1.0 scale). Lower = more sensitive, more frames. 0.3 works well for screen recordings; 0.1 is better for slide decks with subtle transitions.
- `MULTIMODAL_VIDEO_MAX_KEYFRAMES`: 30 default. Hard cap on extracted frames to limit OCR cost.

## Alternatives Considered

### A. Fixed-interval keyframe extraction (e.g., 1 frame every 5 seconds)
**Rejected.** A 2-minute video at 1 frame/5s = 24 frames, but most would contain identical content in a typical screen recording. Meanwhile, rapid screen changes (switching tabs, scrolling) would be missed between intervals. Scene detection naturally adapts to content -- static slides produce few frames, fast-changing content produces more.

### B. Gemini vision API for video understanding
**Rejected.** Using `generate_content` with the full video to ask "what text is visible?" would work but:
- Costs significantly more per API call (video tokens >> image tokens)
- Less reliable for precise text extraction (vision models summarize; we need exact text)
- Cannot be parallelized per-frame
- Would require sending the video to the Gemini API twice (once for text extraction, once for embedding)

The existing Docling/Mistral OCR infrastructure is free (already deployed) and purpose-built for text extraction. Gemini vision is only used as a fallback when the OCR provider is unavailable.

### C. Audio-only transcription (no visual OCR)
**Rejected (was the initial implementation).** This misses the majority of information in screen recordings and presentations, where the most important content is on-screen text, not narration. Cross-validation R1 identified this as a gap.

### D. Every-frame OCR with deduplication
**Rejected.** Extracting every frame and relying solely on deduplication is wasteful. A 30fps 2-minute video = 3,600 frames. Even at 1fps = 120 frames. Scene detection typically produces 5-20 frames for a screen recording, which is the right order of magnitude for OCR cost.

### E. Gemini Embedding 2 native video understanding
**Investigated but not viable.** While Gemini Embedding 2 natively embeds video content, the embedding captures semantic similarity, not extractable text. BM25 sparse scoring requires actual text tokens. The dense vector from `embed_file()` handles semantic search; the OCR text handles keyword search. Both are needed.

## Deduplication Strategy

Consecutive keyframes often contain nearly identical text (e.g., a presenter pausing on a slide). The converter uses a simple character-overlap similarity metric:

```python
@staticmethod
def _deduplicate_texts(texts: list[str]) -> list[str]:
    for text in texts:
        if prev:
            common = sum(1 for a, b in zip(prev, text) if a == b)
            similarity = common / min(len(prev), len(text))
            if similarity > 0.8:
                continue  # Too similar, skip
        deduped.append(text)
```

The 80% threshold was chosen empirically. Lower thresholds (e.g., 60%) would over-deduplicate frames where a single line changed. Higher thresholds (e.g., 95%) would retain too many near-duplicates.

## OCR Provider Cascade

1. **Docling/Mistral OCR** (primary): Uses the existing `img_converter` registered in `platform/converters/__init__.py`. Free, already deployed, optimized for text extraction.
2. **Gemini vision** (fallback): Per-frame `generate_content` call with the prompt "Extract ALL text visible in this screenshot." Used only when the primary OCR provider is unavailable or not configured.

## Consequences
- **Positive**: Captures on-screen text that audio-only transcription misses entirely.
- **Positive**: Scene detection is content-adaptive -- efficient for static presentations, comprehensive for dynamic screen recordings.
- **Positive**: Max keyframe cap (30) bounds OCR cost regardless of video length.
- **Positive**: Reuses existing Docling/Mistral OCR infrastructure (no new dependencies for the primary path).
- **Positive**: Graceful degradation: if OCR fails, the audio transcript still provides BM25 text.
- **Negative**: Scene detection may miss subtle changes (e.g., a single character typed in an IDE). Threshold is configurable to tune sensitivity.
- **Negative**: OCR quality depends on video resolution and compression. Low-quality video may produce poor OCR results.
- **Negative**: Temporary keyframe files (JPEG) are written to disk and cleaned up in a `finally` block. Abnormal termination could leave orphan files in the system temp directory.
