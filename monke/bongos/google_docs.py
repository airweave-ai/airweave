"""Google Docs bongo implementation.

Creates, updates, and deletes test entities via the real Google Docs API.
Documents are created directly using the Google Docs API and content is inserted via batchUpdate.
"""

import asyncio
import time
import uuid
from typing import Any, Dict, List

import httpx
from monke.bongos.base_bongo import BaseBongo
from monke.generation.google_docs import generate_documents
from monke.utils.logging import get_logger

# No longer need python-docx since we use Google Docs API directly

DRIVE_API = "https://www.googleapis.com/drive/v3"
DOCS_API = "https://docs.googleapis.com/v1"


class GoogleDocsBongo(BaseBongo):
    """Bongo for Google Docs that creates test entities for E2E testing.

    Key responsibilities:
    - Create test Google Docs by uploading DOCX files with content
    - Update documents to test incremental sync via Docs API
    - Delete documents to test deletion detection
    - Clean up all test data

    Note: Creates documents by uploading DOCX files to Drive, which Google automatically
    converts to Docs format. This ensures content is immediately available.
    """

    connector_type = "google_docs"

    def __init__(self, credentials: Dict[str, Any], **kwargs):
        super().__init__(credentials)
        self.access_token: str = credentials["access_token"]
        self.entity_count: int = int(kwargs.get("entity_count", 3))
        self.openai_model: str = kwargs.get("openai_model", "gpt-4.1-mini")
        self.rate_limit_delay = float(kwargs.get("rate_limit_delay_ms", 500)) / 1000.0
        self.logger = get_logger("google_docs_bongo")

        # Track created resources for cleanup
        self._test_docs: List[Dict[str, Any]] = []
        self._last_req = 0.0

        # No longer need python-docx dependency

    async def create_entities(self) -> List[Dict[str, Any]]:
        """Create test Google Docs documents using the Google Docs API."""
        self.logger.info(f"🥁 Creating {self.entity_count} Google Docs test documents")
        out: List[Dict[str, Any]] = []

        # Generate tokens for each document
        tokens = [uuid.uuid4().hex[:8] for _ in range(self.entity_count)]

        # Generate document content
        test_name = f"Monke_TestDoc_{uuid.uuid4().hex[:8]}"
        documents = await generate_documents(self.openai_model, tokens, test_name)

        self.logger.info(f"📝 Generated {len(documents)} documents")

        async with httpx.AsyncClient(timeout=60) as client:
            for doc_data, token in zip(documents, tokens):
                await self._pace()
                self.logger.info(f"📤 Creating Google Doc: {doc_data.title}")

                # Step 1: Create document directly via Google Docs API
                create_response = await client.post(
                    f"{DOCS_API}/documents",
                    headers={
                        "Authorization": f"Bearer {self.access_token}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "title": doc_data.title,
                    },
                )

                if create_response.status_code not in (200, 201):
                    self.logger.error(
                        f"Create failed {create_response.status_code}: {create_response.text}"
                    )
                    create_response.raise_for_status()

                doc_file = create_response.json()
                doc_id = doc_file["documentId"]
                self.logger.info(f"✅ Created document: {doc_id} - {doc_data.title}")

                # Step 2: Insert content using Docs API
                await self._pace()

                # Insert text at index 1 (beginning of document)
                requests_payload = [
                    {
                        "insertText": {
                            "location": {"index": 1},
                            "text": doc_data.content,
                        }
                    }
                ]

                content_response = await client.post(
                    f"{DOCS_API}/documents/{doc_id}:batchUpdate",
                    headers={
                        "Authorization": f"Bearer {self.access_token}",
                        "Content-Type": "application/json",
                    },
                    json={"requests": requests_payload},
                )

                if content_response.status_code not in (200, 201):
                    self.logger.error(
                        f"Content insert failed {content_response.status_code}: {content_response.text[:200]}"
                    )
                    # Continue anyway - document exists even if content failed
                else:
                    self.logger.info(
                        f"📄 Inserted {len(doc_data.content)} chars into document: {doc_data.title}"
                    )

                # Store entity info
                ent = {
                    "type": "document",
                    "id": doc_id,
                    "name": doc_data.title,
                    "token": token,
                    "expected_content": token,
                }
                out.append(ent)
                self._test_docs.append(ent)
                self.created_entities.append({"id": doc_id, "name": doc_data.title})

                # Brief delay between creates
                await asyncio.sleep(0.5)

        self.logger.info(f"✅ Created {len(self._test_docs)} Google Docs documents")
        return out

    async def update_entities(self) -> List[Dict[str, Any]]:
        """Update documents by appending new content with same tokens."""
        if not self._test_docs:
            return []

        self.logger.info(
            f"🥁 Updating {min(2, len(self._test_docs))} Google Docs documents"
        )
        updated = []

        async with httpx.AsyncClient(timeout=60) as client:
            for ent in self._test_docs[: min(2, len(self._test_docs))]:
                await self._pace()

                # Get document to find insertion point
                doc_response = await client.get(
                    f"{DOCS_API}/documents/{ent['id']}",
                    headers={
                        "Authorization": f"Bearer {self.access_token}",
                    },
                )

                if doc_response.status_code != 200:
                    self.logger.warning(
                        f"Could not get document for update: {doc_response.status_code}"
                    )
                    continue

                doc_info = doc_response.json()
                # Get the end index to append
                content_list = doc_info.get("body", {}).get("content", [])
                if content_list:
                    insert_index = content_list[-1].get("endIndex", 2) - 1
                else:
                    insert_index = 1

                # Append update text with token to the document
                update_text = (
                    f"\n\nUpdate: This document was updated. Token: {ent['token']}"
                )

                await self._pace()

                requests = [
                    {
                        "insertText": {
                            "location": {"index": insert_index},
                            "text": update_text,
                        }
                    }
                ]

                r = await client.post(
                    f"{DOCS_API}/documents/{ent['id']}:batchUpdate",
                    headers={
                        "Authorization": f"Bearer {self.access_token}",
                        "Content-Type": "application/json",
                    },
                    json={"requests": requests},
                )

                if r.status_code in (200, 201):
                    updated.append({**ent, "updated": True})
                    self.logger.info(
                        f"📝 Updated document '{ent['name']}' with token: {ent['token']}"
                    )
                else:
                    self.logger.warning(
                        f"Failed to update document: {r.status_code} - {r.text[:200]}"
                    )

                # Brief delay between updates
                await asyncio.sleep(0.5)

        return updated

    async def delete_entities(self) -> List[str]:
        """Delete all test documents."""
        return await self.delete_specific_entities(self._test_docs)

    async def delete_specific_entities(
        self, entities: List[Dict[str, Any]]
    ) -> List[str]:
        """Delete specific test documents."""
        if not entities:
            # Delete all if no specific entities provided
            entities = self._test_docs

        if not entities:
            return []

        self.logger.info(f"🥁 Deleting {len(entities)} Google Docs documents")
        deleted: List[str] = []

        async with httpx.AsyncClient(timeout=30) as client:
            for ent in entities:
                try:
                    await self._pace()

                    # Delete the document from Drive
                    r = await client.delete(
                        f"{DRIVE_API}/files/{ent['id']}",
                        headers={"Authorization": f"Bearer {self.access_token}"},
                    )

                    if r.status_code == 204:
                        deleted.append(ent["id"])
                        self.logger.info(f"✅ Deleted document: {ent['name']}")
                        # Remove from tracking
                        if ent in self._test_docs:
                            self._test_docs.remove(ent)
                    else:
                        self.logger.warning(
                            f"Delete failed: {r.status_code} - {r.text[:200]}"
                        )

                except Exception as e:
                    self.logger.warning(f"Delete error for {ent['id']}: {e}")

        return deleted

    async def cleanup(self):
        """Comprehensive cleanup of all test resources."""
        self.logger.info("🧹 Starting comprehensive Google Docs cleanup")

        cleanup_stats = {
            "documents_deleted": 0,
            "errors": 0,
        }

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                # Delete current test documents
                if self._test_docs:
                    self.logger.info(
                        f"🗑️ Deleting {len(self._test_docs)} test documents"
                    )
                    deleted = await self.delete_specific_entities(self._test_docs[:])
                    cleanup_stats["documents_deleted"] += len(deleted)

                # Search for and cleanup any orphaned test documents
                await self._cleanup_orphaned_documents(client, cleanup_stats)

            self.logger.info(
                f"🧹 Cleanup completed: {cleanup_stats['documents_deleted']} "
                f"documents deleted, {cleanup_stats['errors']} errors"
            )
        except Exception as e:
            self.logger.error(f"❌ Error during comprehensive cleanup: {e}")

    async def _cleanup_orphaned_documents(
        self, client: httpx.AsyncClient, stats: Dict[str, Any]
    ):
        """Find and delete orphaned test documents from previous runs."""
        try:
            await self._pace()

            # Search for documents starting with "Monke_TestDoc_"
            r = await client.get(
                f"{DRIVE_API}/files",
                headers={"Authorization": f"Bearer {self.access_token}"},
                params={
                    "q": "name contains 'Monke_TestDoc_' and mimeType='application/vnd.google-apps.document'",
                    "fields": "files(id, name)",
                },
            )

            if r.status_code == 200:
                files = r.json().get("files", [])

                if files:
                    self.logger.info(f"🔍 Found {len(files)} orphaned test documents")
                    for doc in files:
                        try:
                            await self._pace()
                            del_r = await client.delete(
                                f"{DRIVE_API}/files/{doc['id']}",
                                headers={
                                    "Authorization": f"Bearer {self.access_token}"
                                },
                            )
                            if del_r.status_code == 204:
                                stats["documents_deleted"] += 1
                                self.logger.info(
                                    f"✅ Deleted orphaned document: {doc.get('name', 'Unknown')}"
                                )
                            else:
                                stats["errors"] += 1
                        except Exception as e:
                            stats["errors"] += 1
                            self.logger.warning(
                                f"⚠️ Failed to delete document {doc['id']}: {e}"
                            )
        except Exception as e:
            self.logger.warning(f"⚠️ Could not search for orphaned documents: {e}")

    async def _pace(self):
        """Rate limiting helper."""
        now = time.time()
        if (delta := now - self._last_req) < self.rate_limit_delay:
            await asyncio.sleep(self.rate_limit_delay - delta)
        self._last_req = time.time()
