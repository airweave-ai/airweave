/*
 * Gemini Embedding 2 Multimodal Pipeline - C4 Model (Structurizr DSL)
 *
 * Render: https://structurizr.com/dsl or `structurizr-cli export -w c4-architecture.dsl -f plantuml`
 *
 * Level 1: System Context
 * Level 2: Container (Airweave internals)
 * Level 3: Component (Embedding pipeline detail)
 */

workspace "Airweave Gemini Embedding 2" "Multimodal embedding pipeline for PDF, image, audio, and video" {

    model {
        # --- People ---
        user = person "Developer" "Configures sources and queries collections"

        # --- External Systems ---
        geminiApi = softwareSystem "Google Gemini API" "Embedding + generation endpoints" "External"
        vespa = softwareSystem "Vespa" "Hybrid search (dense + BM25 sparse)" "External"
        sourceApis = softwareSystem "Source APIs" "Google Drive, Slack, GitHub, etc." "External"

        # --- Airweave System ---
        airweave = softwareSystem "Airweave" "Make any app searchable" {

            api = container "API Server" "FastAPI" "Python 3.13" {
                searchEndpoint = component "Search API" "Queries Vespa with dense+sparse"
                syncEndpoint = component "Sync API" "Triggers Temporal workflows"
            }

            temporal = container "Temporal Worker" "Executes sync workflows" "Python 3.13 + ffmpeg" {
                syncWorkflow = component "SyncWorkflow" "Orchestrates entity pipeline"

                textBuilder = component "TextBuilder" "Routes files to converters"
                pdfConverter = component "PdfConverter" "Text extraction + OCR fallback"
                audioConverter = component "AudioConverter" "Gemini transcription; auto-chunks >19MB files"
                videoConverter = component "VideoConverter" "Scene keyframe OCR (ffmpeg scene detect + Docling/Mistral OCR + dedup) + audio transcription"

                chunkEmbed = component "ChunkEmbedProcessor" "Partition -> Embed -> Store" {
                    description "Routes entities to text or native multimodal pipeline. Enforces ENABLE_MEDIA_SYNC for audio/video at pipeline level."
                }
                partitioner = component "_partition_by_embedding_mode" "isinstance(MultimodalDenseEmbedderProtocol) + ENABLE_MEDIA_SYNC gate"
                nativePipeline = component "_native_multimodal_pipeline" "embed_file() for images/PDFs, MediaChunker for audio/video. Catches EmbedderInputError + EmbedderProviderError."
                pdfChunker = component "_embed_oversized_pdf" "PyMuPDF: splits >6-page PDFs with configurable overlap"
                textPipeline = component "_text_pipeline" "SemanticChunker + embed_many()"

                mediaChunker = component "MediaChunker" "ffmpeg stream-copy segmentation. Size-aware segment sizing for oversized audio."
                geminiEmbedder = component "GeminiDenseEmbedder" "embed_many() + embed_file(). Separate vectors (no aggregation)."
                sparseEmbedder = component "BM25 Sparse Embedder" "FastEmbed Qdrant/BM25"
            }

            postgres = container "PostgreSQL" "Metadata, connections, sync state" "PostgreSQL"
        }

        # --- Relationships: System Context ---
        user -> airweave "Configures sources, queries data"
        airweave -> geminiApi "Embeds text + files, transcribes audio, OCRs keyframes (fallback)"
        airweave -> vespa "Stores/queries vectors + BM25"
        airweave -> sourceApis "Fetches entities + files"

        # --- Relationships: Container ---
        api -> temporal "Triggers sync via Temporal"
        api -> vespa "Search queries"
        api -> postgres "CRUD"
        temporal -> geminiApi "embed_content, generate_content"
        temporal -> vespa "Upsert chunks"
        temporal -> sourceApis "Download files"
        temporal -> postgres "Sync state"

        # --- Relationships: Component ---
        syncWorkflow -> chunkEmbed "Processes entity batches"
        chunkEmbed -> partitioner "Classifies entities"
        partitioner -> nativePipeline "FileEntity + supported MIME + media flag"
        partitioner -> textPipeline "Everything else (or media with flag OFF)"

        nativePipeline -> textBuilder "Extract text for BM25"
        nativePipeline -> geminiEmbedder "embed_file(path, mime)"
        nativePipeline -> mediaChunker "chunk_audio() / chunk_video()"
        nativePipeline -> pdfChunker "Oversized PDFs (>6 pages)"
        nativePipeline -> sparseEmbedder "BM25 from textual_representation"

        pdfChunker -> geminiEmbedder "embed_file() per page chunk"

        textPipeline -> textBuilder "Extract text"
        textPipeline -> geminiEmbedder "embed_many(texts)"
        textPipeline -> sparseEmbedder "BM25 from entity JSON"

        textBuilder -> pdfConverter ".pdf"
        textBuilder -> audioConverter ".mp3, .wav"
        textBuilder -> videoConverter ".mp4"

        audioConverter -> geminiApi "generate_content (transcription)"
        videoConverter -> audioConverter "Delegates audio track transcription"
        videoConverter -> pdfConverter "Keyframe OCR via Docling/Mistral (primary)"
        videoConverter -> geminiApi "generate_content (vision OCR fallback)"
        geminiEmbedder -> geminiApi "embed_content (text + files)"
    }

    views {
        systemContext airweave "SystemContext" {
            include *
            autoLayout
        }

        container airweave "Containers" {
            include *
            autoLayout
        }

        component temporal "EmbeddingPipeline" {
            include *
            autoLayout
        }

        styles {
            element "Software System" {
                background #1168bd
                color #ffffff
            }
            element "External" {
                background #999999
                color #ffffff
            }
            element "Container" {
                background #438dd5
                color #ffffff
            }
            element "Component" {
                background #85bbf0
                color #000000
            }
            element "Person" {
                shape person
                background #08427b
                color #ffffff
            }
        }
    }

}
