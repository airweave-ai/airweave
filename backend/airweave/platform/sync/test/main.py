"""Manual test for EntityPipeline.process() with print output.

Run with: pytest airweave/platform/sync/test/main.py -s -v

The -s flag shows print statements (entity JSON dumps).
Run specific source: pytest airweave/platform/sync/test/main.py::test_pipeline_process_asana -s -v
"""

from unittest.mock import patch
from uuid import UUID

import pytest

from airweave.platform.sync.entity_pipeline import EntityPipeline
from airweave.platform.sync.test.entities.asana import asana_examples
from airweave.platform.sync.test.entities.gcal import gcal_examples
from airweave.platform.sync.test.entities.gdrive import gdrive_examples
from airweave.platform.sync.test.entities.github import github_examples
from airweave.platform.sync.test.entities.gmail import gmail_examples
from airweave.platform.sync.test.entities.notion import notion_examples
from airweave.platform.sync.test.entities.stripe import stripe_examples
from airweave.platform.sync.test.entities.teams import teams_examples
from airweave.platform.sync.test.mock_context import create_mock_sync_context


# Mock CRUD entity to avoid database connections in these tests
class MockEntityStore:
    """Mock crud.entity that returns empty results (all entities are INSERTs)."""

    def __init__(self):
        """Initialize empty store."""
        self.sync_id = UUID("12345678-1234-5678-1234-567812345678")

    async def bulk_get_by_entity_sync_and_definition(self, db, *, sync_id, entity_requests):
        """Return empty dict (no entities in store = all are INSERTs)."""
        return {}


@pytest.mark.asyncio
async def test_pipeline_process_asana():
    """Test EntityPipeline.process() with Asana entities."""
    pipeline = EntityPipeline()
    sync_context = create_mock_sync_context()

    print("\n" + "=" * 80)
    print("Testing EntityPipeline.process() with Asana entities")
    print(f"Entity count: {len(asana_examples)}")
    print("=" * 80 + "\n")

    mock_store = MockEntityStore()

    with patch("airweave.platform.sync.entity_pipeline.crud.entity", mock_store):
        await pipeline.process(entities=asana_examples, sync_context=sync_context)

    print("\n✅ Asana entities processed successfully\n")


@pytest.mark.asyncio
async def test_pipeline_process_gcal():
    """Test EntityPipeline.process() with Google Calendar entities."""
    pipeline = EntityPipeline()
    sync_context = create_mock_sync_context(source_name="google_calendar")

    print("\n" + "=" * 80)
    print("Testing EntityPipeline.process() with Google Calendar entities")
    print(f"Entity count: {len(gcal_examples)}")
    print("=" * 80 + "\n")

    mock_store = MockEntityStore()

    with patch("airweave.platform.sync.entity_pipeline.crud.entity", mock_store):
        await pipeline.process(entities=gcal_examples, sync_context=sync_context)

    print("\n✅ Google Calendar entities processed successfully\n")


@pytest.mark.asyncio
async def test_pipeline_process_gdrive():
    """Test EntityPipeline.process() with Google Drive entities."""
    pipeline = EntityPipeline()
    sync_context = create_mock_sync_context(source_name="google_drive")

    print("\n" + "=" * 80)
    print("Testing EntityPipeline.process() with Google Drive entities")
    print(f"Entity count: {len(gdrive_examples)}")
    print("=" * 80 + "\n")

    mock_store = MockEntityStore()

    with patch("airweave.platform.sync.entity_pipeline.crud.entity", mock_store):
        await pipeline.process(entities=gdrive_examples, sync_context=sync_context)

    print("\n✅ Google Drive entities processed successfully\n")


@pytest.mark.asyncio
async def test_pipeline_process_github():
    """Test EntityPipeline.process() with GitHub entities."""
    pipeline = EntityPipeline()
    sync_context = create_mock_sync_context(source_name="github")

    print("\n" + "=" * 80)
    print("Testing EntityPipeline.process() with GitHub code files")
    print(f"Entity count: {len(github_examples)}")
    print("  - 2 Python code files (supported)")
    print("  - 1 Text file (.txt as CodeFileEntity - tests unsupported language filtering)")
    print("  - 2 non-file entities (repo, directory)")
    print("=" * 80 + "\n")

    mock_store = MockEntityStore()

    with patch("airweave.platform.sync.entity_pipeline.crud.entity", mock_store):
        await pipeline.process(entities=github_examples, sync_context=sync_context)

    print("\n✅ GitHub entities processed successfully\n")


@pytest.mark.asyncio
async def test_pipeline_process_gmail():
    """Test EntityPipeline.process() with Gmail entities."""
    pipeline = EntityPipeline()
    sync_context = create_mock_sync_context(source_name="gmail")

    print("\n" + "=" * 80)
    print("Testing EntityPipeline.process() with Gmail entities")
    print(f"Entity count: {len(gmail_examples)}")
    print("=" * 80 + "\n")

    mock_store = MockEntityStore()

    with patch("airweave.platform.sync.entity_pipeline.crud.entity", mock_store):
        await pipeline.process(entities=gmail_examples, sync_context=sync_context)

    print("\n✅ Gmail entities processed successfully\n")


@pytest.mark.asyncio
async def test_pipeline_process_notion():
    """Test EntityPipeline.process() with Notion entities."""
    pipeline = EntityPipeline()
    sync_context = create_mock_sync_context(source_name="notion")

    print("\n" + "=" * 80)
    print("Testing EntityPipeline.process() with Notion entities")
    print(f"Entity count: {len(notion_examples)}")
    print("=" * 80 + "\n")

    mock_store = MockEntityStore()

    with patch("airweave.platform.sync.entity_pipeline.crud.entity", mock_store):
        await pipeline.process(entities=notion_examples, sync_context=sync_context)

    print("\n✅ Notion entities processed successfully\n")


@pytest.mark.asyncio
async def test_pipeline_process_stripe():
    """Test EntityPipeline.process() with Stripe entities."""
    pipeline = EntityPipeline()
    sync_context = create_mock_sync_context(source_name="stripe")

    print("\n" + "=" * 80)
    print("Testing EntityPipeline.process() with Stripe entities")
    print(f"Entity count: {len(stripe_examples)}")
    print("=" * 80 + "\n")

    mock_store = MockEntityStore()

    with patch("airweave.platform.sync.entity_pipeline.crud.entity", mock_store):
        await pipeline.process(entities=stripe_examples, sync_context=sync_context)

    print("\n✅ Stripe entities processed successfully\n")


@pytest.mark.asyncio
async def test_pipeline_process_teams():
    """Test EntityPipeline.process() with Microsoft Teams entities."""
    pipeline = EntityPipeline()
    sync_context = create_mock_sync_context(source_name="teams")

    print("\n" + "=" * 80)
    print("Testing EntityPipeline.process() with Microsoft Teams entities")
    print(f"Entity count: {len(teams_examples)}")
    print("=" * 80 + "\n")

    mock_store = MockEntityStore()

    with patch("airweave.platform.sync.entity_pipeline.crud.entity", mock_store):
        await pipeline.process(entities=teams_examples, sync_context=sync_context)

    print("\n✅ Microsoft Teams entities processed successfully\n")


@pytest.mark.asyncio
async def test_pipeline_process_all_sources():
    """Test EntityPipeline.process() with ALL source entities combined."""
    pipeline = EntityPipeline()
    sync_context = create_mock_sync_context()

    # Combine all examples
    all_entities = (
        asana_examples
        + gcal_examples
        + gdrive_examples
        + github_examples
        + gmail_examples
        + notion_examples
        + stripe_examples
        + teams_examples
    )

    print("\n" + "=" * 80)
    print("Testing EntityPipeline.process() with ALL sources combined")
    print(f"Total entity count: {len(all_entities)}")
    print(f"  - Asana: {len(asana_examples)}")
    print(f"  - Google Calendar: {len(gcal_examples)}")
    print(f"  - Google Drive: {len(gdrive_examples)}")
    print(f"  - GitHub: {len(github_examples)}")
    print(f"  - Gmail: {len(gmail_examples)}")
    print(f"  - Notion: {len(notion_examples)}")
    print(f"  - Stripe: {len(stripe_examples)}")
    print(f"  - Teams: {len(teams_examples)}")
    print("=" * 80 + "\n")

    mock_store = MockEntityStore()

    with patch("airweave.platform.sync.entity_pipeline.crud.entity", mock_store):
        await pipeline.process(entities=all_entities, sync_context=sync_context)

    print("\n✅ All source entities processed successfully\n")


@pytest.mark.asyncio
async def test_pipeline_process_gdrive_pdf_only():
    """Test EntityPipeline.process() with Google Drive PDF file only."""
    pipeline = EntityPipeline()
    sync_context = create_mock_sync_context(source_name="google_drive")

    # Import PDF file from gdrive examples
    from airweave.platform.sync.test.entities.gdrive import pdf_file

    # Create batch with just the PDF
    pdf_examples = [pdf_file]

    print("\n" + "=" * 80)
    print("Testing EntityPipeline.process() with Google Drive PDF")
    print(f"File: {pdf_file.name}")
    print(f"Size: {pdf_file.size / 1_000_000:.2f}MB")
    print("=" * 80 + "\n")

    mock_store = MockEntityStore()

    with patch("airweave.platform.sync.entity_pipeline.crud.entity", mock_store):
        await pipeline.process(entities=pdf_examples, sync_context=sync_context)

    print("\n✅ Google Drive PDF processed successfully\n")


@pytest.mark.asyncio
async def test_pipeline_process_amazon_pdfs():
    """Test EntityPipeline.process() with Amazon Annual Report PDFs."""
    pipeline = EntityPipeline()
    sync_context = create_mock_sync_context(source_name="google_drive")

    # Import Amazon PDF files from gdrive examples
    from airweave.platform.sync.test.entities.gdrive import amazon_pdf_examples

    print("\n" + "=" * 80)
    print("Testing EntityPipeline.process() with Amazon Annual Report PDFs")
    print(f"Entity count: {len(amazon_pdf_examples)}")
    for pdf in amazon_pdf_examples:
        print(f"  - {pdf.name} ({pdf.size / 1_000_000:.2f}MB)")
    print("=" * 80 + "\n")

    mock_store = MockEntityStore()

    with patch("airweave.platform.sync.entity_pipeline.crud.entity", mock_store):
        await pipeline.process(entities=amazon_pdf_examples, sync_context=sync_context)

    print("\n✅ Amazon PDFs processed successfully\n")


@pytest.mark.asyncio
async def test_pipeline_process_mistral_documents():
    """Test unified document converter with PDF, DOCX, PPTX (Mistral OCR formats)."""
    pipeline = EntityPipeline()
    sync_context = create_mock_sync_context(source_name="google_drive")

    # Import Mistral-supported document types from gdrive examples
    from airweave.platform.sync.test.entities.gdrive import (
        amazon_2024_pdf,  # DDIA.pdf (25MB)
        pptx_file,  # Rewire Model.pptx (1.7MB)
        word_file,  # Tips and tops.docx (277KB)
    )

    # All Mistral OCR document types in ONE batch
    document_entities = [amazon_2024_pdf, word_file, pptx_file]

    print("\n" + "=" * 80)
    print("Testing UNIFIED Document Converter (PDF + DOCX + PPTX via Mistral OCR)")
    print(f"Total documents: {len(document_entities)}")
    print(f"  - PDF: {amazon_2024_pdf.name} ({amazon_2024_pdf.size / 1_000_000:.2f}MB)")
    print(f"  - DOCX: {word_file.name} ({word_file.size / 1_000:.0f}KB)")
    print(f"  - PPTX: {pptx_file.name} ({pptx_file.size / 1_000_000:.2f}MB)")
    print("=" * 80 + "\n")

    mock_store = MockEntityStore()

    with patch("airweave.platform.sync.entity_pipeline.crud.entity", mock_store):
        await pipeline.process(entities=document_entities, sync_context=sync_context)

    print("\n✅ All Mistral document types processed in ONE unified batch!\n")


@pytest.mark.asyncio
async def test_pipeline_process_xlsx():
    """Test XLSX converter with local openpyxl extraction."""
    pipeline = EntityPipeline()
    sync_context = create_mock_sync_context(source_name="google_drive")

    # Import XLSX file from gdrive examples
    from airweave.platform.sync.test.entities.gdrive import excel_file

    xlsx_entities = [excel_file]

    print("\n" + "=" * 80)
    print("Testing XLSX Converter (Local openpyxl extraction)")
    print(f"Total documents: {len(xlsx_entities)}")
    print(f"  - XLSX: {excel_file.name} ({excel_file.size / 1_000:.0f}KB)")
    print("=" * 80 + "\n")

    mock_store = MockEntityStore()

    with patch("airweave.platform.sync.entity_pipeline.crud.entity", mock_store):
        await pipeline.process(entities=xlsx_entities, sync_context=sync_context)

    print("\n✅ XLSX processed successfully with local extraction!\n")


@pytest.mark.asyncio
async def test_pipeline_process_images():
    """Test Mistral OCR with images from Google Drive and Notion."""
    pipeline = EntityPipeline()
    sync_context = create_mock_sync_context(source_name="google_drive")

    # Import image files from gdrive and notion examples
    from airweave.platform.sync.test.entities.gdrive import jpeg_file
    from airweave.platform.sync.test.entities.notion import file_entity as notion_image

    image_entities = [jpeg_file, notion_image]

    print("\n" + "=" * 80)
    print("Testing Mistral OCR with Images (JPG, PNG)")
    print(f"Total images: {len(image_entities)}")
    print(f"  - JPG (GDrive): {jpeg_file.name} ({jpeg_file.size / 1_000_000:.2f}MB)")
    print(f"  - PNG (Notion): {notion_image.name} ({notion_image.size / 1_000:.0f}KB)")
    print("=" * 80 + "\n")

    mock_store = MockEntityStore()

    with patch("airweave.platform.sync.entity_pipeline.crud.entity", mock_store):
        await pipeline.process(entities=image_entities, sync_context=sync_context)

    print("\n✅ Images processed successfully with Mistral OCR!\n")


@pytest.mark.asyncio
async def test_pipeline_process_code_files():
    """Test CodeConverter with AI summarization for GitHub code files."""
    pipeline = EntityPipeline()
    sync_context = create_mock_sync_context(source_name="github")

    # Import code files from github examples
    from airweave.platform.sync.test.entities.github import code_file_large, code_file_largest

    code_entities = [code_file_largest, code_file_large]

    print("\n" + "=" * 80)
    print("Testing Code Converter with AI Summarization (OpenAI Batch API)")
    print(f"Total code files: {len(code_entities)}")
    print(
        f"  - {code_file_largest.name}: {code_file_largest.size / 1_000:.1f}KB "
        f"({code_file_largest.line_count} lines)"
    )
    print(
        f"  - {code_file_large.name}: {code_file_large.size / 1_000:.1f}KB "
        f"({code_file_large.line_count} lines)"
    )
    print("=" * 80 + "\n")

    mock_store = MockEntityStore()

    with patch("airweave.platform.sync.entity_pipeline.crud.entity", mock_store):
        await pipeline.process(entities=code_entities, sync_context=sync_context)

    print("\n✅ Code files processed with AI summaries!\n")
