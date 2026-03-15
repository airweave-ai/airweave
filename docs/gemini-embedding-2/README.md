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
    C -- Yes --> D{MIME type?}

    D -- image/png\nimage/jpeg\napplication/pdf --> E[embed_file\n1 chunk per file]
    D -- audio/mpeg\naudio/wav\nvideo/mp4 --> F[MediaChunker\nN segments]

    F --> G[embed_file per segment\nN chunks per file]

    T --> H[TextBuilder\nExtract text]
    H --> I[SemanticChunker\nor CodeChunker]
    I --> J[embed_many\nN chunks per entity]

    E --> K[Sparse BM25 Embed\nfrom textual_representation]
    G --> K
    J --> K

    K --> L[(Vespa / Qdrant)]

    style A fill:#4a90d9,color:#fff
    style B fill:#f5a623,color:#fff
    style C fill:#f5a623,color:#fff
    style D fill:#f5a623,color:#fff
    style E fill:#7ed321,color:#fff
    style F fill:#7ed321,color:#fff
    style G fill:#7ed321,color:#fff
    style T fill:#9b59b6,color:#fff
    style H fill:#9b59b6,color:#fff
    style I fill:#9b59b6,color:#fff
    style J fill:#9b59b6,color:#fff
    style K fill:#e74c3c,color:#fff
    style L fill:#2c3e50,color:#fff
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
    Rel(airweave, gemini, "Embeds text + files, transcribes audio")
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
    Component(part, "Partitioner", "Python", "isinstance(MultimodalDenseEmbedderProtocol)")
    Component(native, "Native Pipeline", "Python", "embed_file() for img/PDF, MediaChunker for audio/video")
    Component(text, "Text Pipeline", "Python", "SemanticChunker + embed_many()")
    Component(tb, "TextBuilder", "Python", "Routes files to converters")
    Component(mc, "MediaChunker", "pydub + ffmpeg", "Splits audio/video into segments")
    Component(ge, "GeminiDenseEmbedder", "google-genai", "embed_many() + embed_file()")
    Component(se, "BM25 Sparse Embedder", "FastEmbed", "Keyword scoring vectors")
    Component(ac, "AudioConverter", "Gemini generate_content", "Audio transcription")
    Component(vc, "VideoConverter", "ffmpeg + AudioConverter", "Video transcription")

    System_Ext(gapi, "Gemini API", "")
    System_Ext(vdb, "Vespa", "")

    Rel(proc, part, "Classifies entities")
    Rel(part, native, "FileEntity + supported MIME")
    Rel(part, text, "BaseEntity / unsupported")
    Rel(native, tb, "Extract text for BM25")
    Rel(native, ge, "embed_file(path, mime)")
    Rel(native, mc, "Audio/video segmentation")
    Rel(native, se, "BM25 from text")
    Rel(text, tb, "Extract text")
    Rel(text, ge, "embed_many(texts)")
    Rel(text, se, "BM25 from JSON")
    Rel(tb, ac, ".mp3, .wav")
    Rel(tb, vc, ".mp4")
    Rel(ge, gapi, "embed_content")
    Rel(ac, gapi, "generate_content")
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
    Note over CE: isinstance(GeminiDenseEmbedder,<br/>MultimodalDenseEmbedderProtocol) = True<br/>mime=application/pdf, local_path exists

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
    AC->>API: generate_content("Transcribe...", audio_blob)
    API-->>AC: "Welcome to the show..."
    AC-->>TB: {path: "Welcome to the show..."}
    TB-->>CE: entity.textual_representation = transcript

    CE->>CE: mime=audio/mpeg -> _embed_media_entity()
    CE->>MC: chunk_audio("/data/podcast.mp3")
    Note over MC: 180s / 75s segments = 3 chunks<br/>with 5s overlap

    MC-->>CE: [seg_0(0-75s), seg_1(70-145s), seg_2(140-180s)]

    loop Each segment
        CE->>GE: embed_file(seg.file_path, "audio/mpeg")
        GE->>API: embed_content(Part(inline_data=Blob(audio)))
        API-->>GE: embedding vector
        GE-->>CE: DenseEmbedding
    end

    Note over CE: Produces 3 chunk entities:<br/>podcast__chunk_0, __chunk_1, __chunk_2
```

### Fallback: PDF Too Large

```mermaid
sequenceDiagram
    participant CE as ChunkEmbedProcessor
    participant GE as GeminiDenseEmbedder
    participant TP as Text Pipeline

    CE->>GE: embed_file("/data/big.pdf", "application/pdf")
    GE->>GE: _validate_pdf_pages() -> 12 pages
    GE--xCE: EmbedderInputError("PDF has 12 pages, limit 6")

    Note over CE: Caught EmbedderInputError<br/>Log warning, add to fallback list

    CE->>TP: _text_pipeline([big_pdf_entity])
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
| **Pipeline** | `ChunkEmbedProcessor._partition_by_embedding_mode()` | Routes FileEntity to native or text path |
| **Pipeline** | `ChunkEmbedProcessor._native_multimodal_pipeline()` | 1-chunk-per-file for images/PDFs, N-chunks for media |
| **Chunker** | `MediaChunker` | Splits audio (pydub) and video (ffmpeg) into embeddable segments |
| **Converter** | `AudioConverter` / `VideoConverter` | Gemini-based transcription for BM25 sparse scoring |
| **Config** | `ENABLE_MEDIA_SYNC` | Feature flag gating audio/video support |

## Key Design Decisions

1. **Protocol, not class hierarchy** -- `MultimodalDenseEmbedderProtocol` is `@runtime_checkable`. The pipeline detects capability via `isinstance()`, so OpenAI/Mistral/Local embedders are unaffected. ([ADR-001](./adr-001-protocol-over-inheritance.md))

2. **File path, not bytes** -- `embed_file()` takes a path string, reads from disk inside the embedder, and discards bytes after the API call. This prevents the `model_copy(deep=True)` memory amplification at chunk_embed.py:203. ([ADR-002](./adr-002-file-path-over-bytes.md))

3. **Text always extracted** -- Even for natively-embedded files, `textual_representation` is populated via existing converters. BM25 sparse scoring, answer generation, and reranking all depend on text.

4. **Graceful fallback** -- If `embed_file()` raises `EmbedderInputError` (too many pages, oversized), the entity silently falls back to the text pipeline with a warning log.

5. **Audio/video behind feature flag** -- `ENABLE_MEDIA_SYNC=false` by default. When disabled, Google Drive skips video files (existing behavior). When enabled, `MediaChunker` splits into segments within Gemini's duration limits. ([ADR-003](./adr-003-feature-flag-for-media.md))

## File Inventory

### New Files (7)
| File | Lines | Purpose |
|------|-------|---------|
| `domains/embedders/dense/tests/test_gemini_multimodal.py` | ~360 | 24 tests: file validation, embed_file, API errors, protocol compliance |
| `platform/chunkers/media.py` | ~200 | MediaChunker + MediaSegment for audio/video splitting |
| `platform/converters/audio_converter.py` | ~95 | Gemini-based audio transcription |
| `platform/converters/video_converter.py` | ~110 | Audio extraction + transcription for video |
| `tests/unit/platform/chunkers/test_media.py` | ~200 | 8 tests for audio/video chunking |
| `tests/unit/platform/converters/test_audio_converter.py` | ~80 | 5 tests for audio transcription |
| `tests/unit/platform/sync/processors/test_chunk_embed_multimodal.py` | ~200 | 10 tests for pipeline routing and fallback |

### Modified Files (11)
| File | Change |
|------|--------|
| `domains/embedders/protocols.py` | +`MultimodalDenseEmbedderProtocol` |
| `domains/embedders/dense/gemini.py` | +`embed_file()`, multimodal validation, error refactor |
| `domains/embedders/fakes/embedder.py` | +`FakeMultimodalDenseEmbedder` |
| `platform/sync/processors/chunk_embed.py` | Refactored into text + native pipelines |
| `platform/converters/__init__.py` | Registered audio/video converters |
| `platform/sync/pipeline/text_builder.py` | Audio/video converter routing |
| `platform/sync/file_types.py` | +`.mp3`, `.wav`, `.mp4` |
| `platform/sources/google_drive.py` | Video skip gated behind `ENABLE_MEDIA_SYNC` |
| `core/config/settings.py` | +`ENABLE_MEDIA_SYNC` |
| `Dockerfile`, `Dockerfile.dev`, `temporal/Dockerfile` | +`ffmpeg` |
| `pyproject.toml` | +`pydub` |

## Test Results

```
88 passed, 0 skipped, 0 failed (10.62s)
```

- 25 Phase 1 tests (text-only, pre-existing) -- all pass unchanged
- 24 Phase 2 tests (multimodal embedder + protocol)
- 10 Phase 2B tests (pipeline routing + fallback)
- 8 Phase 3 tests (media chunking)
- 5 Phase 3 tests (audio transcription)
- 1 Phase 1 test (query purpose)
- 15 pre-existing chunk_embed tests -- all pass unchanged

## Gemini Embedding 2 Limits

| Input Type | Limit | Our Conservative Limit |
|-----------|-------|----------------------|
| Text | 8,192 tokens | 40,000 chars (~10K tokens) |
| PDF | 6 pages | 6 pages |
| Image | 6 per request | 1 per request (native embed) |
| Audio | 80 seconds | 75 seconds (with 5s overlap) |
| Video (with audio) | 80 seconds | 75 seconds (with 5s overlap) |
| Video (no audio) | 120 seconds | 115 seconds (with 5s overlap) |
| File size | 20 MB | 20 MB |
| Output dimensions | Up to 3,072 (Matryoshka) | Configurable via `EMBEDDING_DIMENSIONS` |

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
- [C4 Structurizr DSL](./c4-architecture.dsl)
- [C4 PlantUML](./c4-component.puml)
