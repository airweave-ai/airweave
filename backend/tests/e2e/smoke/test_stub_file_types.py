"""
E2E smoke tests for the file_stub document conversion pipeline.

Architecture: **sync once, assert many times**.

A module-scoped fixture creates a single file_stub source connection,
syncs it (generating born-digital PDF, scanned PDF, PPTX, DOCX), does
a broad search for the tracking string, and caches the results. Each
test then filters from that cache -- no additional API calls per test.

This keeps the suite fast (~1 sync instead of N) while still giving
clear per-file-type failure signals.

Requires:
- A running Airweave backend with converters configured
- Mistral API key for the scanned-PDF OCR test
"""

import asyncio
import random
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import httpx
import pytest
import pytest_asyncio
from pydantic import BaseModel, Field, ValidationError


# ── Lightweight response models (mirrors API shape, no backend import) ──


class _SystemMetadata(BaseModel):
    entity_type: str
    source_name: Optional[str] = None
    sync_id: Optional[str] = None
    sync_job_id: Optional[str] = None
    original_entity_id: Optional[str] = None
    chunk_index: Optional[int] = None


class AirweaveSearchResult(BaseModel):
    """Minimal mirror of the API search-result payload for E2E assertions."""

    id: str
    score: float
    entity_id: str
    name: str
    textual_representation: str
    system_metadata: _SystemMetadata
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    breadcrumbs: list = Field(default_factory=list)
    access: Optional[dict] = None
    source_fields: dict = Field(default_factory=dict)

# OCR-friendly word list for tracking tokens (common, unambiguous words)
_TRACKING_WORDS = [
    "alpha", "basket", "cherry", "delta", "ember", "falcon", "garden",
    "harbor", "ivory", "jungle", "kettle", "lemon", "marble", "noble",
    "orange", "planet", "quiver", "river", "silver", "timber", "umbrella",
    "violet", "walnut", "yellow", "zenith", "bridge", "candle", "forest",
    "meadow", "sunset", "copper", "velvet", "crystal", "thunder", "willow",
]
SEARCH_LIMIT = 50


def _generate_tracking_string() -> str:
    """Generate an OCR-friendly tracking string using hyphenated real words.

    Produces tokens like ``file-stub-cherry-falcon-river-marble`` which OCR
    models handle far better than hex strings like ``FILE_STUB_E2E_a1b2c3d4``.
    """
    words = random.sample(_TRACKING_WORDS, 4)
    return "file-stub-" + "-".join(words)


# =========================================================================
# Context dataclass & helpers
# =========================================================================


@dataclass
class SyncedFileStubContext:
    """Shared state produced by the module fixture, consumed by all tests."""

    client: httpx.AsyncClient
    collection_readable_id: str
    connection_id: str
    tracking_string: str
    sync_job: Dict  # raw job dict from the jobs endpoint
    sync_status: str  # "completed" | "error" | "failed" | "cancelled"
    search_results: List[AirweaveSearchResult] = field(default_factory=list)

    # ── convenience helpers ───────────────────────────────────────────

    def results_of_type(self, entity_type: str) -> List[AirweaveSearchResult]:
        """Return results matching a specific entity type."""
        return [
            r for r in self.search_results
            if r.system_metadata.entity_type == entity_type
        ]

    def results_with_tracking(
        self, entity_type: str
    ) -> List[AirweaveSearchResult]:
        """Return results of *entity_type* whose textual_representation
        contains the tracking string."""
        return [
            r for r in self.results_of_type(entity_type)
            if self.tracking_string in r.textual_representation
        ]

    @property
    def entity_types_found(self) -> set[str]:
        return {r.system_metadata.entity_type for r in self.search_results}


# =========================================================================
# Module-scoped fixture: sync once, cache results
# =========================================================================


async def _wait_for_sync(
    client: httpx.AsyncClient,
    connection_id: str,
    max_wait: int = 300,
    poll: int = 5,
) -> Dict:
    """Poll the sync job until it reaches a terminal state."""
    terminal = {"completed", "error", "failed", "cancelled"}
    elapsed = 0
    while elapsed < max_wait:
        await asyncio.sleep(poll)
        elapsed += poll
        resp = await client.get(
            f"/source-connections/{connection_id}/jobs?limit=1"
        )
        if resp.status_code != 200:
            continue
        jobs = resp.json()
        if not jobs:
            continue
        job = jobs[0]
        status = job.get("status", "").lower()
        print(
            f"  [sync] job {job.get('id', '?')}: "
            f"status={status} ({elapsed}s)"
        )
        if status in terminal:
            return job
    raise TimeoutError(f"Sync not done after {max_wait}s")


async def _do_search(
    client: httpx.AsyncClient,
    readable_id: str,
    query: str,
    limit: int = SEARCH_LIMIT,
) -> List[AirweaveSearchResult]:
    """Keyword search, deserialise into Pydantic models."""
    payload = {
        "query": query,
        "retrieval_strategy": "keyword",
        "expand_query": False,
        "interpret_filters": False,
        "rerank": False,
        "generate_answer": False,
        "limit": limit,
    }
    resp = await client.post(
        f"/collections/{readable_id}/search",
        json=payload,
        timeout=60,
    )
    if resp.status_code != 200:
        pytest.fail(f"Search failed ({resp.status_code}): {resp.text}")

    results: List[AirweaveSearchResult] = []
    for raw in resp.json().get("results", []):
        try:
            results.append(AirweaveSearchResult.model_validate(raw))
        except ValidationError as e:
            pytest.fail(f"Result deserialisation error: {e}\nRaw: {raw}")
    return results


@pytest_asyncio.fixture(scope="module")
async def synced_file_stub() -> SyncedFileStubContext:
    """Create one file_stub sync, wait, search, cache everything.

    Yields a :class:`SyncedFileStubContext` that every test in this module
    reads from.  Tears down the connection + collection afterwards.
    """
    from config import settings

    tracking_string = _generate_tracking_string()
    seed = int(time.time()) % 100_000  # different seed each run

    print("\n" + "=" * 70)
    print("FIXTURE: synced_file_stub")
    print(f"  tracking_string = {tracking_string}")
    print(f"  seed            = {seed}")
    print("=" * 70)

    async with httpx.AsyncClient(
        base_url=settings.api_url,
        headers=settings.api_headers,
        timeout=httpx.Timeout(120),
        follow_redirects=True,
    ) as client:
        # ── create collection ─────────────────────────────────────────
        coll_resp = await client.post(
            "/collections/",
            json={"name": f"File Stub E2E {int(time.time())}"},
        )
        assert coll_resp.status_code == 200, (
            f"Collection creation failed: {coll_resp.text}"
        )
        collection_readable_id = coll_resp.json()["readable_id"]

        # ── create file_stub source connection ────────────────────────
        conn_resp = await client.post(
            "/source-connections",
            json={
                "name": f"File Stub {int(time.time())}",
                "short_name": "file_stub",
                "readable_collection_id": collection_readable_id,
                "authentication": {"credentials": {"stub_key": "file-stub"}},
                "config": {
                    "seed": seed,
                    "custom_content_prefix": tracking_string,
                },
                "sync_immediately": True,
            },
        )
        assert conn_resp.status_code == 200, (
            f"Source connection creation failed: {conn_resp.text}"
        )
        connection_id = conn_resp.json()["id"]

        # ── wait for sync ─────────────────────────────────────────────
        print("Waiting for file_stub sync to complete...")
        try:
            job = await _wait_for_sync(client, connection_id, max_wait=300)
        except TimeoutError as e:
            pytest.fail(str(e))

        sync_status = job.get("status", "").lower()
        print(f"Sync finished: status={sync_status}")

        # ── wait for indexing and search for tracking string ─────────
        # OCR entities (ScannedPdfFileStubEntity) can take longer to
        # process and index, especially under parallel test load.
        # Retry the search until all 4 expected entity types appear,
        # or we exhaust retries (fall through with whatever we have).
        expected_types = {
            "PdfFileStubEntity",
            "ScannedPdfFileStubEntity",
            "PptxFileStubEntity",
            "DocxFileStubEntity",
        }
        results: List[AirweaveSearchResult] = []
        print(f"Searching for: {tracking_string}")

        for attempt in range(15):  # up to ~90s for indexing lag
            wait_secs = 3 if attempt < 5 else 5 if attempt < 10 else 8
            await asyncio.sleep(wait_secs)
            results = await _do_search(
                client, collection_readable_id, tracking_string
            )
            found_types = {r.system_metadata.entity_type for r in results}
            missing = expected_types - found_types
            if not missing:
                print(
                    f"Search returned {len(results)} results  "
                    f"(types: {', '.join(sorted(found_types))}) — all types found (attempt {attempt + 1})"
                )
                break
            print(
                f"  [search] attempt {attempt + 1}: {len(results)} results, "
                f"missing types: {missing}, retrying..."
            )
        else:
            found_types = {r.system_metadata.entity_type for r in results}
            print(
                f"Search returned {len(results)} results  "
                f"(types: {', '.join(sorted(found_types))}) — some types still missing after retries"
            )

        ctx = SyncedFileStubContext(
            client=client,
            collection_readable_id=collection_readable_id,
            connection_id=connection_id,
            tracking_string=tracking_string,
            sync_job=job,
            sync_status=sync_status,
            search_results=results,
        )

        # ── yield to tests ────────────────────────────────────────────
        yield ctx

        # ── teardown ──────────────────────────────────────────────────
        print("\nTearing down file_stub resources...")
        try:
            await client.delete(f"/source-connections/{connection_id}")
        except Exception:
            pass
        try:
            await client.delete(f"/collections/{collection_readable_id}")
        except Exception:
            pass


# =========================================================================
# Tests
# =========================================================================


class TestFileStubSync:
    """Tests that share a single synced file_stub collection."""

    # ── 1. sync health ────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_sync_completes_successfully(
        self, synced_file_stub: SyncedFileStubContext
    ):
        """The file_stub sync job must finish with status 'completed'."""
        ctx = synced_file_stub
        assert ctx.sync_status == "completed", (
            f"Expected sync status 'completed', got '{ctx.sync_status}'. "
            f"Job: {ctx.sync_job}"
        )

    # ── 2. born-digital PDF (text extraction, no OCR) ─────────────────

    @pytest.mark.asyncio
    async def test_born_digital_pdf_text_extracted(
        self, synced_file_stub: SyncedFileStubContext
    ):
        """Born-digital PDF content is searchable via text extraction.

        PdfConverter should extract the text layer directly with PyMuPDF.
        No Mistral API call needed.
        """
        ctx = synced_file_stub
        matches = ctx.results_with_tracking("PdfFileStubEntity")

        assert len(matches) > 0, (
            f"No PdfFileStubEntity results contain the tracking string "
            f"'{ctx.tracking_string}'. "
            f"Entity types found: {ctx.entity_types_found}. "
            f"This means PDF text extraction failed to capture the embedded text."
        )

    # ── 3. scanned PDF (image-only, requires OCR) ─────────────────────

    @pytest.mark.asyncio
    async def test_scanned_pdf_ocr_extracted(
        self, synced_file_stub: SyncedFileStubContext
    ):
        """Scanned (image-only) PDF content is searchable via OCR.

        The scanned PDF has no text layer -- text is rendered as JPEG images.
        PdfConverter should detect this and delegate to MistralOCR.
        """
        ctx = synced_file_stub
        matches = ctx.results_with_tracking("ScannedPdfFileStubEntity")

        assert len(matches) > 0, (
            f"No ScannedPdfFileStubEntity results contain the tracking string "
            f"'{ctx.tracking_string}'. "
            f"Entity types found: {ctx.entity_types_found}. "
            f"This means OCR failed to extract the burned-in text from the "
            f"image-only pages. Check that MISTRAL_API_KEY is set."
        )

    # ── 4. PPTX (text extraction) ────────────────────────────────────

    @pytest.mark.asyncio
    async def test_pptx_text_extracted(
        self, synced_file_stub: SyncedFileStubContext
    ):
        """PPTX slide content is searchable via python-pptx extraction.

        PptxConverter should extract slide text directly without OCR.
        """
        ctx = synced_file_stub
        matches = ctx.results_with_tracking("PptxFileStubEntity")

        assert len(matches) > 0, (
            f"No PptxFileStubEntity results contain the tracking string "
            f"'{ctx.tracking_string}'. "
            f"Entity types found: {ctx.entity_types_found}. "
            f"This means PPTX text extraction failed."
        )

    # ── 5. DOCX (text extraction) ────────────────────────────────────

    @pytest.mark.asyncio
    async def test_docx_text_extracted(
        self, synced_file_stub: SyncedFileStubContext
    ):
        """DOCX paragraph content is searchable via python-docx extraction.

        DocxConverter should extract paragraph text directly without OCR.
        """
        ctx = synced_file_stub
        matches = ctx.results_with_tracking("DocxFileStubEntity")

        assert len(matches) > 0, (
            f"No DocxFileStubEntity results contain the tracking string "
            f"'{ctx.tracking_string}'. "
            f"Entity types found: {ctx.entity_types_found}. "
            f"This means DOCX text extraction failed."
        )

    # ── 6. all file types indexed ─────────────────────────────────────

    @pytest.mark.asyncio
    async def test_all_four_file_types_indexed(
        self, synced_file_stub: SyncedFileStubContext
    ):
        """All four file entity types should appear in search results.

        The file_stub source generates exactly one born-digital PDF,
        one scanned PDF, one PPTX, and one DOCX.  After sync, all four
        should be indexed and returned when searching for the tracking string.
        """
        ctx = synced_file_stub
        expected = {
            "PdfFileStubEntity",
            "ScannedPdfFileStubEntity",
            "PptxFileStubEntity",
            "DocxFileStubEntity",
        }
        found = ctx.entity_types_found & expected
        missing = expected - found

        assert not missing, (
            f"Missing entity types in search results: {missing}. "
            f"Found: {found}. "
            f"This means some file types were not extracted or indexed. "
            f"Total results: {len(ctx.search_results)}."
        )

    # ── 7. entity metadata is valid ───────────────────────────────────

    @pytest.mark.asyncio
    async def test_entity_metadata_valid(
        self, synced_file_stub: SyncedFileStubContext
    ):
        """Every search result should have valid metadata fields.

        Checks that basic fields are present and well-formed on every
        result returned by the broad search.
        """
        ctx = synced_file_stub

        assert len(ctx.search_results) > 0, "No search results to validate"

        for result in ctx.search_results:
            # entity_type is non-empty
            assert result.system_metadata.entity_type, (
                f"Result {result.id} has empty entity_type"
            )

            # source_name is set to file_stub
            assert result.system_metadata.source_name == "file_stub", (
                f"Result {result.id} has source_name="
                f"'{result.system_metadata.source_name}', expected 'file_stub'"
            )

            # textual_representation is non-empty
            assert result.textual_representation.strip(), (
                f"Result {result.id} ({result.system_metadata.entity_type}) "
                f"has empty textual_representation"
            )

            # entity_id is present
            assert result.entity_id, (
                f"Result {result.id} has empty entity_id"
            )

            # name is present
            assert result.name, (
                f"Result {result.id} has empty name"
            )

            # score is non-negative
            assert result.score >= 0, (
                f"Result {result.id} has negative score: {result.score}"
            )
