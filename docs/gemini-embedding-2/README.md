# Gemini Embedding 2: Full Multimodal Embedding Pipeline

> Native PDF, image, audio, and video embedding through Airweave's Vespa + Temporal pipeline, powered by Google's Gemini Embedding 2 model.

## What This Adds

Airweave's embedding pipeline previously extracted text from every file before computing vectors.
This feature extends that pipeline so the Gemini Embedding 2 provider can **embed raw files directly** -- PDFs, images, audio, and video -- through the native multimodal API, producing a single unified vector space where text queries retrieve documents, screenshots, recordings, and clips.

### Pipeline Decision Flow

```mermaid
flowchart TD
    A[Incoming Entity] --> B{isinstance\nMultimodalDenseEmbedderProtocol?}

    B -- No --> T[Text Pipeline]
    B -- Yes --> C{FileEntity?\nsupported MIME?\nlocal_path?}

    C -- No --> T
    C -- Yes --> M{ENABLE_MEDIA_SYNC\nchecked at pipeline level}

    M -- "audio/video MIME\n+ flag OFF" --> T
    M -- "image/PDF\nOR flag ON" --> D{MIME type?}

    D -- image/png\nimage/jpeg --> E1[embed_file\n1 chunk per file]
    D -- application/pdf\n6 pages or fewer --> E2[embed_file\n1 chunk per file]
    D -- "application/pdf\n>6 pages" --> P[PDF Chunker\n6-page chunks\n1-page overlap]
    D -- audio/mpeg\naudio/wav --> F1[MediaChunker\nffmpeg stream-copy\nsize-aware segments]
    D -- video/mp4 --> F2[MediaChunker\nffmpeg split]

    P --> P1[embed_file per chunk]
    F1 --> G1[embed_file per segment]
    F2 --> G2[embed_file per segment]

    F2 -.-> VT[VideoConverter:\nScene keyframe OCR\n+ audio transcription]

    T --> H[TextBuilder\nExtract text]
    H --> I[SemanticChunker\nor CodeChunker]
    I --> J[embed_many\nN chunks per entity]

    E1 --> K[Sparse BM25 Embed\nfrom textual_representation]
    E2 --> K
    P1 --> K
    G1 --> K
    G2 --> K
    J --> K

    K --> L[(Vespa / Qdrant)]

    style A fill:#4a90d9,color:#fff
    style B fill:#f5a623,color:#fff
    style C fill:#f5a623,color:#fff
    style M fill:#f5a623,color:#fff
    style D fill:#f5a623,color:#fff
    style E1 fill:#7ed321,color:#fff
    style E2 fill:#7ed321,color:#fff
    style P fill:#7ed321,color:#fff
    style P1 fill:#7ed321,color:#fff
    style F1 fill:#7ed321,color:#fff
    style F2 fill:#7ed321,color:#fff
    style G1 fill:#7ed321,color:#fff
    style G2 fill:#7ed321,color:#fff
    style VT fill:#50e3c2,color:#000
    style T fill:#9b59b6,color:#fff
    style H fill:#9b59b6,color:#fff
    style I fill:#9b59b6,color:#fff
    style J fill:#9b59b6,color:#fff
    style K fill:#e74c3c,color:#fff
    style L fill:#2c3e50,color:#fff
```

### Video Pipeline Detail

```mermaid
flowchart TD
    V[video/mp4 entity] --> MC[MediaChunker\nffmpeg -ss/-t -c copy]
    MC --> S1[Segment 0: 0-120s]
    MC --> S2[Segment 1: 115-240s]
    MC --> SN[...]

    V --> VC[VideoConverter\ntextual_representation]

    VC --> KF[Scene Keyframe OCR]
    VC --> AT[Audio Transcription]

    KF --> SD["ffmpeg scene detection\n(threshold=0.3)"]
    SD --> FR[Extract keyframes\nmax 30 frames]
    FR --> OCR[Docling/Mistral OCR\nor Gemini vision fallback]
    OCR --> DD[Deduplicate consecutive\n>80% similar text]

    AT --> HA{Has audio track?}
    HA -- Yes --> EX[ffmpeg extract audio\npcm_s16le 16kHz mono]
    EX --> TR[AudioConverter\nGemini transcription]
    HA -- No --> SKIP[Skip]

    DD --> COMBINE["## Visual Content (OCR)\n...\n## Audio Transcript\n..."]
    TR --> COMBINE

    S1 --> EMB[embed_file per segment]
    S2 --> EMB
    SN --> EMB

    COMBINE --> TEXT["Segment-specific text:\n[Segment N: Xs - Ys] parent_text"]
    TEXT --> BM25[BM25 sparse embed]

    style V fill:#4a90d9,color:#fff
    style VC fill:#50e3c2,color:#000
    style KF fill:#50e3c2,color:#000
    style AT fill:#50e3c2,color:#000
    style MC fill:#7ed321,color:#fff
```

### System Context

```mermaid
C4Context
    title System Context: Airweave with Gemini Embedding 2

    Person(dev, "Developer", "Configures sources and queries collections")

    System(airweave, "Airweave", "Make any app searchable with multimodal embeddings")

    System_Ext(gemini, "Google Gemini API", "embed_content + generate_content")
    System_Ext(vespa, "Vespa", "Hybrid dense + BM25 sparse search")
    System_Ext(sources, "Source APIs", "Google Drive, Slack, GitHub, etc.")

    Rel(dev, airweave, "Configures sources, queries data")
    Rel(airweave, gemini, "Embeds text + files, transcribes audio, OCRs keyframes")
    Rel(airweave, vespa, "Stores and queries vectors")
    Rel(airweave, sources, "Fetches entities and files")

    UpdateRelStyle(dev, airweave, $offsetY="-40")
    UpdateRelStyle(airweave, gemini, $offsetX="-80")
```

### Component Detail: Embedding Pipeline

```mermaid
C4Component
    title Component: ChunkEmbedProcessor (Temporal Worker)

    Component(proc, "ChunkEmbedProcessor", "Python", "Entry point: process(entities)")
    Component(part, "Partitioner", "Python", "isinstance(MultimodalDenseEmbedderProtocol)\n+ ENABLE_MEDIA_SYNC gate")
    Component(native, "Native Pipeline", "Python", "embed_file() for img/PDF, MediaChunker for audio/video")
    Component(pdf, "PDF Chunker", "PyMuPDF", "Splits >6-page PDFs with overlap")
    Component(text, "Text Pipeline", "Python", "SemanticChunker + embed_many()")
    Component(tb, "TextBuilder", "Python", "Routes files to converters")
    Component(mc, "MediaChunker", "ffmpeg stream-copy", "Splits audio/video into segments\nSize-aware segment sizing")
    Component(ge, "GeminiDenseEmbedder", "google-genai", "embed_many() + embed_file()")
    Component(se, "BM25 Sparse Embedder", "FastEmbed", "Keyword scoring vectors")
    Component(ac, "AudioConverter", "Gemini generate_content", "Audio transcription\nChunked for >19MB files")
    Component(vc, "VideoConverter", "ffmpeg + Docling/Mistral OCR", "Scene keyframe OCR + audio transcription")

    System_Ext(gapi, "Gemini API", "")
    System_Ext(vdb, "Vespa", "")

    Rel(proc, part, "Classifies entities")
    Rel(part, native, "FileEntity + supported MIME + flag check")
    Rel(part, text, "BaseEntity / unsupported / media without flag")
    Rel(native, tb, "Extract text for BM25")
    Rel(native, ge, "embed_file(path, mime)")
    Rel(native, mc, "Audio/video segmentation")
    Rel(native, pdf, "Oversized PDF splitting")
    Rel(native, se, "BM25 from text")
    Rel(text, tb, "Extract text")
    Rel(text, ge, "embed_many(texts)")
    Rel(text, se, "BM25 from JSON")
    Rel(tb, ac, ".mp3, .wav")
    Rel(tb, vc, ".mp4")
    Rel(vc, ac, "Delegates audio track transcription")
    Rel(ge, gapi, "embed_content")
    Rel(ac, gapi, "generate_content")
    Rel(vc, gapi, "generate_content (vision OCR fallback)")
    Rel(proc, vdb, "Upsert chunks")
```

## Interaction Diagrams

### Image/PDF Native Embedding (Happy Path)

```mermaid
sequenceDiagram
    participant W as SyncWorkflow
    participant CE as ChunkEmbedProcessor
    participant TB as TextBuilder
    participant GE as GeminiDenseEmbedder
    participant SE as BM25 Sparse
    participant API as Gemini API
    participant V as Vespa

    W->>CE: process([FileEntity(pdf, 3 pages)])
    CE->>CE: _partition_by_embedding_mode()
    Note over CE: isinstance(GeminiDenseEmbedder,<br/>MultimodalDenseEmbedderProtocol) = True<br/>mime=application/pdf, local_path exists<br/>ENABLE_MEDIA_SYNC check (N/A for PDF)

    CE->>TB: build_for_batch([entity])
    TB-->>CE: entity.textual_representation = "extracted text..."

    CE->>GE: embed_file("/data/doc.pdf", "application/pdf")
    GE->>GE: _validate_file_input()<br/>check MIME, size, pages <= 6
    GE->>GE: _read_file_bytes() via aiofiles
    GE->>API: embed_content(Part(inline_data=Blob(bytes, pdf)))
    API-->>GE: embeddings[0].values = [0.12, ...]
    GE->>GE: L2 normalize (if dims < 3072)
    GE-->>CE: DenseEmbedding(vector=[...])

    CE->>SE: embed_many(["entity JSON..."])
    SE-->>CE: SparseEmbedding(indices, values)

    CE->>V: upsert(entity__chunk_0, dense + sparse)
```

### Oversized PDF Chunking

```mermaid
sequenceDiagram
    participant CE as ChunkEmbedProcessor
    participant GE as GeminiDenseEmbedder
    participant FM as PyMuPDF (fitz)
    participant API as Gemini API

    CE->>GE: embed_file("/data/big.pdf", "application/pdf")
    GE->>GE: _validate_pdf_pages() -> 12 pages
    GE--xCE: EmbedderInputError("PDF has 12 pages, limit 6")

    Note over CE: Caught EmbedderInputError<br/>Try _embed_oversized_pdf()

    CE->>FM: open("/data/big.pdf")
    FM-->>CE: 12 pages total

    Note over CE: Split: pages 0-5, 5-10, 10-11<br/>(max_pages=6, overlap=1)

    loop Each 6-page chunk
        CE->>FM: insert_pdf(from_page, to_page)
        FM-->>CE: chunk_N.pdf (temp file)
        CE->>GE: embed_file(chunk_N.pdf, "application/pdf")
        GE->>API: embed_content(Part(inline_data=Blob(...)))
        API-->>GE: embedding vector
        GE-->>CE: DenseEmbedding
    end

    Note over CE: Produces 3 chunks:<br/>big__chunk_0 (p0-5), __chunk_1 (p5-10), __chunk_2 (p10-11)

    CE->>CE: Cleanup temp files
```

### Audio Chunking + Embedding

```mermaid
sequenceDiagram
    participant CE as ChunkEmbedProcessor
    participant TB as TextBuilder
    participant AC as AudioConverter
    participant MC as MediaChunker
    participant GE as GeminiDenseEmbedder
    participant API as Gemini API

    CE->>TB: build_for_batch([FileEntity(mp3, 3min)])
    TB->>AC: convert_batch(["/data/podcast.mp3"])
    Note over AC: File size check:<br/>< 19MB -> direct transcribe<br/>>= 19MB -> chunk first via MediaChunker
    AC->>API: generate_content("Transcribe...", audio_blob)
    API-->>AC: "Welcome to the show..."
    AC-->>TB: {path: "Welcome to the show..."}
    TB-->>CE: entity.textual_representation = transcript

    CE->>CE: mime=audio/mpeg -> _embed_media_entity()
    CE->>MC: chunk_audio("/data/podcast.mp3")
    Note over MC: ffprobe duration -> 180s<br/>os.path.getsize -> check < 19MB<br/>75s segments via ffmpeg -c copy<br/>(stream-copy, no RAM decode)

    MC-->>CE: [seg_0(0-75s), seg_1(70-145s), seg_2(140-180s)]

    loop Each segment
        CE->>GE: embed_file(seg.file_path, "audio/mpeg")
        GE->>API: embed_content(Part(inline_data=Blob(audio)))
        API-->>GE: embedding vector
        GE-->>CE: DenseEmbedding
    end

    Note over CE: Each chunk gets segment-specific text:<br/>"[Segment 0: 0.0s - 75.0s] Welcome to..."<br/>"[Segment 1: 70.0s - 145.0s] Welcome to..."
```

### Video: Scene Keyframe OCR + Audio Transcription

```mermaid
sequenceDiagram
    participant CE as ChunkEmbedProcessor
    participant TB as TextBuilder
    participant VC as VideoConverter
    participant FF as ffmpeg
    participant OCR as Docling/Mistral OCR
    participant AC as AudioConverter
    participant API as Gemini API
    participant MC as MediaChunker
    participant GE as GeminiDenseEmbedder

    CE->>TB: build_for_batch([FileEntity(mp4, 2min)])
    TB->>VC: convert_batch(["/data/recording.mp4"])

    Note over VC: Two-pronged approach:<br/>1. Scene keyframe OCR<br/>2. Audio transcription

    VC->>FF: ffmpeg -vf "select='gt(scene,0.3)'" -frames:v 30
    FF-->>VC: frame_0001.jpg, frame_0002.jpg, ... frame_0012.jpg

    VC->>OCR: convert_batch([frame_0001.jpg, ...])
    OCR-->>VC: ["slide title text...", "code snippet...", ...]

    VC->>VC: _deduplicate_texts()<br/>Remove >80% similar consecutive frames

    VC->>FF: ffprobe -select_streams a (has audio?)
    FF-->>VC: "audio" (yes)
    VC->>FF: ffmpeg -vn -acodec pcm_s16le -ar 16000 -ac 1 audio.wav
    VC->>AC: convert_batch([audio.wav])
    AC->>API: generate_content("Transcribe...", audio_blob)
    API-->>AC: "So today we're going to..."
    AC-->>VC: transcript text

    VC-->>TB: "## Visual Content (OCR)\nslide title...\n\n## Audio Transcript\nSo today..."
    TB-->>CE: entity.textual_representation = combined text

    CE->>MC: chunk_video("/data/recording.mp4")
    Note over MC: 120s max per segment (Gemini 128s hard limit)
    MC-->>CE: [seg_0(0-120s)]

    CE->>GE: embed_file(seg.file_path, "video/mp4")
    GE->>API: embed_content(Part(inline_data=Blob(video)))
    API-->>GE: embedding vector

    Note over CE: Chunk text:<br/>"[Segment 0: 0.0s - 120.0s] ## Visual Content..."
```

### Fallback: Embed Failure

```mermaid
sequenceDiagram
    participant CE as ChunkEmbedProcessor
    participant GE as GeminiDenseEmbedder
    participant TP as Text Pipeline

    CE->>GE: embed_file("/data/corrupt.pdf", "application/pdf")
    GE--xCE: EmbedderProviderError("API 500: internal error")

    Note over CE: Caught EmbedderInputError<br/>OR EmbedderProviderError<br/>Log warning, add to fallback list

    CE->>TP: _text_pipeline([corrupt_pdf_entity])
    Note over TP: TextBuilder -> PdfConverter<br/>SemanticChunker -> embed_many()<br/>Standard text path
    TP-->>CE: chunk entities (text-embedded)
```

### Protocol Detection (Non-Multimodal Embedder)

```mermaid
sequenceDiagram
    participant CE as ChunkEmbedProcessor
    participant OAI as OpenAIDenseEmbedder
    participant TP as Text Pipeline

    CE->>CE: _partition_by_embedding_mode(entities)
    CE->>CE: isinstance(OpenAIDenseEmbedder,<br/>MultimodalDenseEmbedderProtocol)?
    Note over CE: False -- OpenAI embedder has no<br/>supports_multimodal / embed_file()

    CE->>TP: _text_pipeline(ALL entities)
    Note over TP: 100% of entities go through<br/>existing text extraction path.<br/>Zero behavior change.
```

## Architecture at a Glance

| Layer | Component | What it does |
|-------|-----------|-------------|
| **Protocol** | `MultimodalDenseEmbedderProtocol` | Runtime-checkable interface for `embed_file()` |
| **Embedder** | `GeminiDenseEmbedder.embed_file()` | Validates, reads, sends `Part(inline_data=Blob(...))` to Gemini |
| **Pipeline** | `ChunkEmbedProcessor._partition_by_embedding_mode()` | Routes FileEntity to native or text path; enforces `ENABLE_MEDIA_SYNC` for audio/video MIMEs |
| **Pipeline** | `ChunkEmbedProcessor._native_multimodal_pipeline()` | 1-chunk-per-file for images, N-chunks for oversized PDFs and media |
| **Pipeline** | `ChunkEmbedProcessor._embed_oversized_pdf()` | Splits >6-page PDFs into chunks with configurable overlap via PyMuPDF |
| **Pipeline** | `ChunkEmbedProcessor._embed_media_entity()` | Chunks audio/video, embeds per segment, assigns segment-specific text |
| **Chunker** | `MediaChunker` | Splits audio (ffmpeg stream-copy) and video (ffmpeg) into embeddable segments; size-aware segment sizing for oversized files |
| **Converter** | `AudioConverter` | Gemini-based transcription; auto-chunks files >19MB via MediaChunker |
| **Converter** | `VideoConverter` | Scene-based keyframe OCR (ffmpeg scene detection + Docling/Mistral OCR + deduplication) + audio transcription |
| **Config** | `ENABLE_MEDIA_SYNC` | Feature flag gating audio/video at the **pipeline level** (not source-specific) |

## Key Design Decisions

1. **Protocol, not class hierarchy** -- `MultimodalDenseEmbedderProtocol` is `@runtime_checkable`. The pipeline detects capability via `isinstance()`, so OpenAI/Mistral/Local embedders are unaffected. ([ADR-001](./adr-001-protocol-over-inheritance.md))

2. **File path, not bytes** -- `embed_file()` takes a path string, reads from disk inside the embedder, and discards bytes after the API call. This prevents the `model_copy(deep=True)` memory amplification at chunk_embed.py:203. Audio chunking also uses ffmpeg stream-copy instead of pydub RAM decode to avoid OOM on large files. ([ADR-002](./adr-002-file-path-over-bytes.md))

3. **Text always extracted** -- Even for natively-embedded files, `textual_representation` is populated via existing converters. BM25 sparse scoring, answer generation, and reranking all depend on text.

4. **Graceful fallback** -- If `embed_file()` raises `EmbedderInputError` or `EmbedderProviderError`, the entity falls back to the text pipeline with a warning log. For oversized PDFs, the pipeline first attempts 6-page chunking before falling back to text.

5. **Audio/video behind feature flag** -- `ENABLE_MEDIA_SYNC=false` by default. The flag is enforced at the **pipeline level** in `_partition_by_embedding_mode()` -- any source emitting audio/video MIME types is gated, not just Google Drive. ([ADR-003](./adr-003-feature-flag-for-media.md))

6. **Scene-based keyframe OCR for video** -- VideoConverter uses ffmpeg scene detection to extract keyframes only when screen content changes, then OCRs each via Docling/Mistral (or Gemini vision fallback). Consecutive frames >80% similar are deduplicated. This captures slide text and UI content without fixed-interval waste. ([ADR-004](./adr-004-scene-keyframe-ocr.md))

7. **Segment-specific textual_representation** -- Media chunks get `[Segment N: Xs - Ys] parent_text` as their textual_representation, not the full parent transcript duplicated across all chunks. This gives each chunk its own sparse embedding and answer context.

8. **No mean-pooling or aggregation** -- Gemini limits document parts to 1 per `embed_content` call. Each chunk/segment is embedded independently, producing separate vectors in Vespa. This matches the existing text chunking model. The `MULTIMODAL_AGGREGATION` setting exists but only `"separate"` is the supported mode.

## File Inventory

### New Files (11)
| File | Lines | Purpose |
|------|-------|---------|
| `domains/embedders/dense/tests/test_gemini_multimodal.py` | ~356 | 24 tests: file validation, embed_file, API errors, protocol compliance |
| `platform/chunkers/media.py` | ~327 | MediaChunker + MediaSegment: ffmpeg stream-copy splitting with size-aware segment sizing |
| `platform/converters/audio_converter.py` | ~118 | Gemini-based audio transcription with auto-chunking for >19MB files |
| `platform/converters/video_converter.py` | ~341 | Scene-based keyframe OCR + audio transcription for video |
| `tests/unit/platform/chunkers/test_media.py` | ~216 | 9 tests for audio/video chunking including size-aware splitting |
| `tests/unit/platform/converters/test_audio_converter.py` | ~81 | 5 tests for audio transcription |
| `tests/unit/platform/converters/test_video_converter.py` | ~62 | 4 tests for video keyframe OCR + transcription |
| `tests/unit/platform/sync/processors/test_chunk_embed_multimodal.py` | ~321 | 12 tests for pipeline routing, fallback, and PDF chunking |
| `tests/unit/platform/sync/processors/test_multimodal_e2e.py` | ~416 | 10 E2E tests with synthetic media (PyMuPDF, wave, ffmpeg) |
| `tests/live_integration/test_gemini_multimodal_live.py` | ~327 | 9 live integration tests hitting real Gemini API |
| `tests/unit/search/operations/test_embed_query_purpose.py` | ~48 | 1 test for EmbeddingPurpose.QUERY in search |

### Modified Files (11)
| File | Change |
|------|--------|
| `domains/embedders/protocols.py` | +`MultimodalDenseEmbedderProtocol` |
| `domains/embedders/dense/gemini.py` | +`embed_file()`, multimodal validation, error refactor |
| `domains/embedders/fakes/embedder.py` | +`FakeMultimodalDenseEmbedder` |
| `platform/sync/processors/chunk_embed.py` | Refactored into text + native pipelines; catches both `EmbedderInputError` and `EmbedderProviderError` |
| `platform/converters/__init__.py` | Registered audio/video converters |
| `platform/sync/pipeline/text_builder.py` | Audio/video converter routing |
| `platform/sync/file_types.py` | +`.mp3`, `.wav`, `.mp4` |
| `platform/sources/google_drive.py` | Video skip gated behind `ENABLE_MEDIA_SYNC` |
| `core/config/settings.py` | +`ENABLE_MEDIA_SYNC` + all `MULTIMODAL_*` settings |
| `Dockerfile`, `Dockerfile.dev`, `temporal/Dockerfile` | +`ffmpeg` |
| `pyproject.toml` | +`pydub` (fallback only; primary path uses ffmpeg) |

## Test Results

```
113 tests total across 3 test tiers
```

### Unit Tests (79 tests)
- 25 Phase 1 tests (text-only Gemini embedder, pre-existing) -- all pass unchanged
- 24 Phase 2 tests (multimodal embedder + protocol)
- 12 Phase 2B tests (pipeline routing, fallback, and PDF chunking)
- 9 Phase 3 tests (media chunking with ffmpeg stream-copy)
- 5 Phase 3 tests (audio transcription)
- 4 Phase 3 tests (video keyframe OCR + transcription)

### E2E Tests (10 tests)
- Generate real media with PyMuPDF, `wave` stdlib, and ffmpeg
- No AI API cost -- all Gemini calls mocked
- Verify full pipeline routing, chunking, and fallback with real file I/O

### Live Integration Tests (9 tests)
- Hit the REAL Gemini API with real generated media
- Verify actual embedding dimensions, L2 normalization, and cross-modal similarity
- Require `GEMINI_API_KEY` env var and network access
- Run via: `pytest tests/live_integration/ -v -m live_integration`

### Pre-Existing Tests (14 + 1)
- 14 pre-existing chunk_embed tests -- all pass unchanged
- 1 query purpose test (EmbeddingPurpose.QUERY in search)

## Configuration Reference

All settings are via environment variables with sensible defaults. Only active when `DENSE_EMBEDDER=gemini-embedding-2-preview`.

| Variable | Default | Description |
|----------|---------|-------------|
| `ENABLE_MEDIA_SYNC` | `false` | Gate audio/video embedding. Enforced at pipeline level for ALL sources. |
| `MULTIMODAL_PDF_MAX_PAGES` | `6` | Max pages per native PDF embed call (Gemini limit = 6) |
| `MULTIMODAL_PDF_OVERLAP_PAGES` | `1` | Overlap pages when splitting oversized PDFs |
| `MULTIMODAL_MAX_FILE_SIZE_MB` | `20` | Max file size for any single native embed call |
| `MULTIMODAL_AUDIO_MAX_SECONDS` | `75` | Max seconds per audio segment (Gemini hard limit = 80s) |
| `MULTIMODAL_VIDEO_AUDIO_MAX_SECONDS` | `120` | Max seconds per video segment with audio (Gemini hard limit = 128s) |
| `MULTIMODAL_VIDEO_NOAUDIO_MAX_SECONDS` | `120` | Max seconds per video segment without audio (Gemini hard limit = 128s) |
| `MULTIMODAL_MEDIA_OVERLAP_SECONDS` | `5` | Overlap between consecutive audio/video segments |
| `MULTIMODAL_VIDEO_SCENE_THRESHOLD` | `0.3` | ffmpeg scene detection sensitivity (0.0-1.0). Lower = more frames. |
| `MULTIMODAL_VIDEO_MAX_KEYFRAMES` | `30` | Cap on keyframes extracted per video (limits OCR cost) |
| `MULTIMODAL_AGGREGATION` | `separate` | Aggregation mode. Only `"separate"` is supported (separate vectors in Vespa). Gemini limits PDFs to 1 per content entry. |

## Gemini Embedding 2 Limits

| Input Type | Gemini Hard Limit | Our Conservative Limit | Notes |
|-----------|-------------------|----------------------|-------|
| Text | 8,192 tokens | 40,000 chars (~10K tokens) | |
| PDF | 6 pages | 6 pages per chunk | >6 pages auto-split with overlap |
| Image | 6 per request | 1 per request (native embed) | |
| Audio | 80 seconds | 75 seconds per segment | With 5s overlap between segments |
| Video (with audio) | 128 seconds | 120 seconds per segment | With 5s overlap between segments |
| Video (no audio) | 128 seconds | 120 seconds per segment | With 5s overlap between segments |
| File size | 20 MB | 20 MB (19 MB internal threshold) | Size-aware segment sizing for oversized audio |
| Output dimensions | Up to 3,072 (Matryoshka) | Configurable via `EMBEDDING_DIMENSIONS` | |

## Cross-Validation History

Six rounds of cross-validation across Codex, Gemini, and Amp Oracle:

- **R1**: Identified 10 issues (audio OOM on large files, missing EmbedderProviderError catch, source-only media flag, TOCTOU in temp files, container overhead in size calculations, duplicated parent transcript in media chunks)
- **R2-R5**: Iterative fixes addressing each finding
- **R6**: Final signoff from all 3 models -- all issues resolved

## Quick Start

No configuration change needed for PDF/image multimodal -- it activates automatically when `DENSE_EMBEDDER=gemini-embedding-2-preview` is set.

For audio/video:
```env
ENABLE_MEDIA_SYNC=true
GEMINI_API_KEY=your-key
```

## Related

- [ADR-001: Protocol over inheritance](./adr-001-protocol-over-inheritance.md)
- [ADR-002: File path over bytes](./adr-002-file-path-over-bytes.md)
- [ADR-003: Feature flag for media](./adr-003-feature-flag-for-media.md)
- [ADR-004: Scene-based keyframe OCR for video](./adr-004-scene-keyframe-ocr.md)
- [C4 Structurizr DSL](./c4-architecture.dsl)
- [C4 PlantUML](./c4-component.puml)
