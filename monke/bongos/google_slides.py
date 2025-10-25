"""Google Slides bongo implementation.

Creates, updates, and deletes test entities via the real Google Slides API.
Presentations are created directly using the Google Slides API and content is inserted via batchUpdate.
"""

import asyncio
import time
import uuid
from typing import Any, Dict, List

import httpx
from monke.bongos.base_bongo import BaseBongo
from monke.generation.google_slides import generate_presentations
from monke.utils.logging import get_logger

DRIVE_API = "https://www.googleapis.com/drive/v3"
SLIDES_API = "https://slides.googleapis.com/v1"


class GoogleSlidesBongo(BaseBongo):
    """Bongo for Google Slides that creates test entities for E2E testing.

    Key responsibilities:
    - Create test Google Slides presentations using the Slides API
    - Update presentations to test incremental sync via Slides API
    - Delete presentations to test deletion detection
    - Clean up all test data

    Note: Creates presentations directly via Google Slides API, which ensures
    content is immediately available for sync.
    """

    connector_type = "google_slides"

    def __init__(self, credentials: Dict[str, Any], **kwargs):
        super().__init__(credentials)
        self.access_token: str = credentials["access_token"]
        self.entity_count: int = int(kwargs.get("entity_count", 3))
        self.openai_model: str = kwargs.get("openai_model", "gpt-4.1-mini")
        self.rate_limit_delay = float(kwargs.get("rate_limit_delay_ms", 500)) / 1000.0
        self.logger = get_logger("google_slides_bongo")

        # Track created resources for cleanup
        self._test_presentations: List[Dict[str, Any]] = []
        self._last_req = 0.0

    async def create_entities(self) -> List[Dict[str, Any]]:
        """Create test Google Slides presentations using the Google Slides API."""
        self.logger.info(
            f"🥁 Creating {self.entity_count} Google Slides test presentations"
        )
        out: List[Dict[str, Any]] = []

        # Generate tokens for each presentation
        tokens = [uuid.uuid4().hex[:8] for _ in range(self.entity_count)]

        # Generate presentation content
        test_name = f"Monke_TestSlides_{uuid.uuid4().hex[:8]}"
        presentations = await generate_presentations(
            self.openai_model, tokens, test_name
        )

        self.logger.info(f"📝 Generated {len(presentations)} presentations")

        async with httpx.AsyncClient(timeout=60) as client:
            for pres_data, token in zip(presentations, tokens):
                await self._pace()
                self.logger.info(
                    f"📤 Creating Google Slides presentation: {pres_data.title}"
                )

                # Step 1: Create presentation directly via Google Slides API
                create_response = await client.post(
                    f"{SLIDES_API}/presentations",
                    headers={
                        "Authorization": f"Bearer {self.access_token}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "title": pres_data.title,
                    },
                )

                if create_response.status_code not in (200, 201):
                    self.logger.error(
                        f"Create failed {create_response.status_code}: {create_response.text}"
                    )
                    create_response.raise_for_status()

                pres_file = create_response.json()
                pres_id = pres_file["presentationId"]
                self.logger.info(
                    f"✅ Created presentation: {pres_id} - {pres_data.title}"
                )

                # Step 2: Create multiple slides and distribute content
                await self._pace()

                # Get the first slide to insert content
                slides = pres_file.get("slides", [])
                if not slides:
                    self.logger.warning(f"No slides found in presentation {pres_id}")
                    continue

                # Parse content into slides (split by "---" separator)
                slide_contents = pres_data.content.split("---")
                slide_contents = [
                    content.strip() for content in slide_contents if content.strip()
                ]

                # If no separators found, treat as single slide
                if len(slide_contents) == 1:
                    slide_contents = [pres_data.content]

                # Create additional slides if needed
                requests_payload = []
                current_slide_id = slides[0]["objectId"]
                slide_ids = [current_slide_id]  # Start with existing first slide

                # Add slides for additional content (if more than 1 slide worth of content)
                for i in range(1, len(slide_contents)):
                    slide_id = f"slide_{i}_{uuid.uuid4().hex[:8]}"
                    slide_ids.append(slide_id)  # Store the slide ID for later use
                    requests_payload.append(
                        {
                            "createSlide": {
                                "objectId": slide_id,
                                "insertionIndex": i,
                                "slideLayoutReference": {"predefinedLayout": "BLANK"},
                            }
                        }
                    )

                # Add content to each slide
                for i, slide_content in enumerate(slide_contents):
                    slide_id = slide_ids[i]  # Use the stored slide ID
                    textbox_id = f"textbox_{i}_{uuid.uuid4().hex[:8]}"

                    # Create text box for this slide
                    requests_payload.append(
                        {
                            "createShape": {
                                "objectId": textbox_id,
                                "shapeType": "TEXT_BOX",
                                "elementProperties": {
                                    "pageObjectId": slide_id,
                                    "size": {
                                        "height": {"magnitude": 300, "unit": "PT"},
                                        "width": {"magnitude": 600, "unit": "PT"},
                                    },
                                    "transform": {
                                        "scaleX": 1.0,
                                        "scaleY": 1.0,
                                        "translateX": 50.0,
                                        "translateY": 50.0,
                                        "unit": "PT",
                                    },
                                },
                            }
                        }
                    )

                    # Insert text into this slide's text box
                    requests_payload.append(
                        {
                            "insertText": {
                                "objectId": textbox_id,
                                "text": slide_content,
                            }
                        }
                    )

                content_response = await client.post(
                    f"{SLIDES_API}/presentations/{pres_id}:batchUpdate",
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
                    # Continue anyway - presentation exists even if content failed
                else:
                    self.logger.info(
                        f"📄 Inserted {len(pres_data.content)} chars into presentation: {pres_data.title}"
                    )

                # Store entity info
                ent = {
                    "type": "presentation",
                    "id": pres_id,
                    "name": pres_data.title,
                    "token": token,
                    "expected_content": token,
                }
                out.append(ent)
                self._test_presentations.append(ent)
                self.created_entities.append({"id": pres_id, "name": pres_data.title})

                # Brief delay between creates
                await asyncio.sleep(0.5)

        self.logger.info(
            f"✅ Created {len(self._test_presentations)} Google Slides presentations"
        )
        return out

    async def update_entities(self) -> List[Dict[str, Any]]:
        """Update presentations by appending new content with same tokens."""
        if not self._test_presentations:
            return []

        self.logger.info(
            f"🥁 Updating {min(2, len(self._test_presentations))} Google Slides presentations"
        )
        updated = []

        async with httpx.AsyncClient(timeout=60) as client:
            for ent in self._test_presentations[
                : min(2, len(self._test_presentations))
            ]:
                await self._pace()

                # Get presentation to find insertion point
                pres_response = await client.get(
                    f"{SLIDES_API}/presentations/{ent['id']}",
                    headers={
                        "Authorization": f"Bearer {self.access_token}",
                    },
                )

                if pres_response.status_code != 200:
                    self.logger.warning(
                        f"Could not get presentation for update: {pres_response.status_code}"
                    )
                    continue

                pres_info = pres_response.json()
                slides = pres_info.get("slides", [])
                if not slides:
                    self.logger.warning(f"No slides found in presentation {ent['id']}")
                    continue

                first_slide_id = slides[0]["objectId"]

                # Create a new text box for the update
                textbox_id = f"update_textbox_{uuid.uuid4().hex[:8]}"
                update_text = (
                    f"Update: This presentation was updated. Token: {ent['token']}"
                )

                await self._pace()

                requests = [
                    {
                        "createShape": {
                            "objectId": textbox_id,
                            "shapeType": "TEXT_BOX",
                            "elementProperties": {
                                "pageObjectId": first_slide_id,
                                "size": {
                                    "height": {"magnitude": 100, "unit": "PT"},
                                    "width": {"magnitude": 400, "unit": "PT"},
                                },
                                "transform": {
                                    "scaleX": 1.0,
                                    "scaleY": 1.0,
                                    "translateX": 50.0,
                                    "translateY": 300.0,
                                    "unit": "PT",
                                },
                            },
                        }
                    },
                    {
                        "insertText": {
                            "objectId": textbox_id,
                            "text": update_text,
                        }
                    },
                ]

                r = await client.post(
                    f"{SLIDES_API}/presentations/{ent['id']}:batchUpdate",
                    headers={
                        "Authorization": f"Bearer {self.access_token}",
                        "Content-Type": "application/json",
                    },
                    json={"requests": requests},
                )

                if r.status_code in (200, 201):
                    updated.append({**ent, "updated": True})
                    self.logger.info(
                        f"📝 Updated presentation '{ent['name']}' with token: {ent['token']}"
                    )
                else:
                    self.logger.warning(
                        f"Failed to update presentation: {r.status_code} - {r.text[:200]}"
                    )

                # Brief delay between updates
                await asyncio.sleep(0.5)

        return updated

    async def delete_entities(self) -> List[str]:
        """Delete all test presentations."""
        return await self.delete_specific_entities(self._test_presentations)

    async def delete_specific_entities(
        self, entities: List[Dict[str, Any]]
    ) -> List[str]:
        """Delete specific test presentations."""
        if not entities:
            # Delete all if no specific entities provided
            entities = self._test_presentations

        if not entities:
            return []

        self.logger.info(f"🥁 Deleting {len(entities)} Google Slides presentations")
        deleted: List[str] = []

        async with httpx.AsyncClient(timeout=30) as client:
            for ent in entities:
                try:
                    await self._pace()

                    # Delete the presentation from Drive
                    r = await client.delete(
                        f"{DRIVE_API}/files/{ent['id']}",
                        headers={"Authorization": f"Bearer {self.access_token}"},
                    )

                    if r.status_code == 204:
                        deleted.append(ent["id"])
                        self.logger.info(f"✅ Deleted presentation: {ent['name']}")
                        # Remove from tracking
                        if ent in self._test_presentations:
                            self._test_presentations.remove(ent)
                    else:
                        self.logger.warning(
                            f"Delete failed: {r.status_code} - {r.text[:200]}"
                        )

                except Exception as e:
                    self.logger.warning(f"Delete error for {ent['id']}: {e}")

        return deleted

    async def cleanup(self):
        """Comprehensive cleanup of all test resources."""
        self.logger.info("🧹 Starting comprehensive Google Slides cleanup")

        cleanup_stats = {
            "presentations_deleted": 0,
            "errors": 0,
        }

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                # Delete current test presentations
                if self._test_presentations:
                    self.logger.info(
                        f"🗑️ Deleting {len(self._test_presentations)} test presentations"
                    )
                    deleted = await self.delete_specific_entities(
                        self._test_presentations[:]
                    )
                    cleanup_stats["presentations_deleted"] += len(deleted)

                # Search for and cleanup any orphaned test presentations
                await self._cleanup_orphaned_presentations(client, cleanup_stats)

            self.logger.info(
                f"🧹 Cleanup completed: {cleanup_stats['presentations_deleted']} "
                f"presentations deleted, {cleanup_stats['errors']} errors"
            )
        except Exception as e:
            self.logger.error(f"❌ Error during comprehensive cleanup: {e}")

    async def _cleanup_orphaned_presentations(
        self, client: httpx.AsyncClient, stats: Dict[str, Any]
    ):
        """Find and delete orphaned test presentations from previous runs."""
        try:
            await self._pace()

            # Search for presentations starting with "Monke_TestSlides_"
            r = await client.get(
                f"{DRIVE_API}/files",
                headers={"Authorization": f"Bearer {self.access_token}"},
                params={
                    "q": "name contains 'Monke_TestSlides_' and mimeType='application/vnd.google-apps.presentation'",
                    "fields": "files(id, name)",
                },
            )

            if r.status_code == 200:
                files = r.json().get("files", [])

                if files:
                    self.logger.info(
                        f"🔍 Found {len(files)} orphaned test presentations"
                    )
                    for pres in files:
                        try:
                            await self._pace()
                            del_r = await client.delete(
                                f"{DRIVE_API}/files/{pres['id']}",
                                headers={
                                    "Authorization": f"Bearer {self.access_token}"
                                },
                            )
                            if del_r.status_code == 204:
                                stats["presentations_deleted"] += 1
                                self.logger.info(
                                    f"✅ Deleted orphaned presentation: {pres.get('name', 'Unknown')}"
                                )
                            else:
                                stats["errors"] += 1
                        except Exception as e:
                            stats["errors"] += 1
                            self.logger.warning(
                                f"⚠️ Failed to delete presentation {pres['id']}: {e}"
                            )
        except Exception as e:
            self.logger.warning(f"⚠️ Could not search for orphaned presentations: {e}")

    async def _pace(self):
        """Rate limiting helper."""
        now = time.time()
        if (delta := now - self._last_req) < self.rate_limit_delay:
            await asyncio.sleep(self.rate_limit_delay - delta)
        self._last_req = time.time()
