"""PowerPoint bongo implementation.

Creates, updates, and deletes test PowerPoint presentations via the Microsoft Graph API.
"""

import asyncio
import io
import uuid
from typing import Any, Dict, List

import httpx
from monke.bongos._microsoft_graph_base import GRAPH, MicrosoftGraphBongo
from monke.generation.powerpoint import generate_presentations_content

# Try to import python-pptx for PowerPoint presentation creation
try:
    from pptx import Presentation
    from pptx.util import Inches

    HAS_PYTHON_PPTX = True
except ImportError:
    HAS_PYTHON_PPTX = False


class PowerPointBongo(MicrosoftGraphBongo):
    """Bongo for PowerPoint that creates test entities for E2E testing.

    Key responsibilities:
    - Create test PowerPoint presentations in OneDrive
    - Add slides with content containing verification tokens
    - Update presentations to test incremental sync
    - Delete presentations to test deletion detection
    - Clean up all test data
    """

    connector_type = "powerpoint"

    def __init__(self, credentials: Dict[str, Any], **kwargs):
        super().__init__(credentials, **kwargs)

        # Track created resources for cleanup
        self._test_presentations: List[Dict[str, Any]] = []

        if not HAS_PYTHON_PPTX:
            raise ImportError(
                "python-pptx is required for PowerPoint bongo. Install with: pip install python-pptx"
            )

    async def create_entities(self) -> List[Dict[str, Any]]:
        """Create test PowerPoint presentations in OneDrive."""
        self.logger.info(
            f"🥁 Creating {self.entity_count} PowerPoint test presentations"
        )
        out: List[Dict[str, Any]] = []

        # Generate tokens for each presentation
        tokens = [uuid.uuid4().hex[:8] for _ in range(self.entity_count)]

        # Generate presentation content
        test_name = f"TestPresentation_{uuid.uuid4().hex[:8]}"
        filenames, presentation_content = await generate_presentations_content(
            self.openai_model, tokens, test_name
        )

        self.logger.info(f"📊 Generated {len(presentation_content)} presentations")

        async with httpx.AsyncClient(base_url=GRAPH, timeout=60) as client:
            for i, (filename, pres_content, token) in enumerate(
                zip(filenames, presentation_content, tokens)
            ):
                await self._pace()

                # Sanitize filename for OneDrive (remove illegal characters)
                safe_filename = self._sanitize_filename(filename)

                # Create PowerPoint presentation file
                pres_bytes = self._create_powerpoint_file(pres_content)

                # Upload to OneDrive
                self.logger.info(
                    f"📤 Uploading PowerPoint presentation: {safe_filename}"
                )
                upload_url = f"/me/drive/root:/{safe_filename}:/content"

                r = await client.put(
                    upload_url,
                    headers={
                        "Authorization": f"Bearer {self.access_token}",
                        "Content-Type": (
                            "application/vnd.openxmlformats-officedocument."
                            "presentationml.presentation"
                        ),
                    },
                    content=pres_bytes,
                )

                if r.status_code not in (200, 201):
                    self.logger.error(f"Upload failed {r.status_code}: {r.text}")
                    r.raise_for_status()

                pres_file = r.json()
                pres_id = pres_file["id"]

                self.logger.info(
                    f"✅ Uploaded presentation: {pres_id} - {safe_filename}"
                )

                ent = {
                    "type": "presentation",
                    "id": pres_id,
                    "filename": safe_filename,
                    "title": pres_content.title,
                    "token": token,
                    "expected_content": token,
                }
                out.append(ent)
                self._test_presentations.append(ent)
                self.created_entities.append({"id": pres_id, "name": safe_filename})

                self.logger.info(
                    f"📝 Presentation '{safe_filename}' created with token: {token}"
                )

        self.logger.info(
            f"✅ Created {len(self._test_presentations)} PowerPoint presentations"
        )
        return out

    def _create_powerpoint_file(self, pres_content: Any) -> bytes:
        """Create a PowerPoint presentation file with the given content.

        Args:
            pres_content: PowerPointPresentationContent object

        Returns:
            Bytes of the PowerPoint presentation
        """
        prs = Presentation()
        prs.slide_width = Inches(10)
        prs.slide_height = Inches(7.5)

        # Slide 1: Title slide
        title_slide_layout = prs.slide_layouts[0]
        slide = prs.slides.add_slide(title_slide_layout)
        title = slide.shapes.title
        subtitle = slide.placeholders[1]

        title.text = pres_content.title
        subtitle.text = pres_content.subtitle

        # Add content slides
        for slide_content in pres_content.slides:
            # Use bullet layout
            bullet_slide_layout = prs.slide_layouts[1]
            slide = prs.slides.add_slide(bullet_slide_layout)

            # Set title
            title_shape = slide.shapes.title
            title_shape.text = slide_content.title

            # Add content
            content_shape = slide.placeholders[1]
            text_frame = content_shape.text_frame
            text_frame.clear()

            for i, bullet_text in enumerate(slide_content.content):
                if i == 0:
                    p = text_frame.paragraphs[0]
                else:
                    p = text_frame.add_paragraph()
                p.text = bullet_text
                p.level = 0

        # Save to bytes
        buffer = io.BytesIO()
        prs.save(buffer)
        buffer.seek(0)
        return buffer.getvalue()

    async def update_entities(self) -> List[Dict[str, Any]]:
        """Update PowerPoint presentations by adding a new slide with same tokens."""
        if not self._test_presentations:
            return []

        self.logger.info(
            f"🥁 Updating {min(2, len(self._test_presentations))} PowerPoint presentations"
        )
        updated = []

        async with httpx.AsyncClient(base_url=GRAPH, timeout=60) as client:
            for ent in self._test_presentations[
                : min(2, len(self._test_presentations))
            ]:
                await self._pace()

                # Download current presentation
                download_url = f"/me/drive/items/{ent['id']}/content"
                r = await client.get(download_url, headers=self._hdrs())

                if r.status_code != 200:
                    self.logger.warning(
                        f"Failed to download presentation: {r.status_code} - {r.text[:200]}"
                    )
                    continue

                # Load existing presentation
                prs = Presentation(io.BytesIO(r.content))

                # Add new slide with update information
                bullet_slide_layout = prs.slide_layouts[1]
                new_slide = prs.slides.add_slide(bullet_slide_layout)

                # Set title
                title_shape = new_slide.shapes.title
                title_shape.text = "Update Section"

                # Add content with token
                content_shape = new_slide.placeholders[1]
                text_frame = content_shape.text_frame
                text_frame.clear()

                update_content = [
                    "This presentation has been updated",
                    f"Update token: {ent['token']}",
                    "Updated to verify incremental sync functionality",
                ]

                for i, bullet_text in enumerate(update_content):
                    if i == 0:
                        p = text_frame.paragraphs[0]
                    else:
                        p = text_frame.add_paragraph()
                    p.text = bullet_text
                    p.level = 0

                # Save updated presentation
                buffer = io.BytesIO()
                prs.save(buffer)
                buffer.seek(0)
                updated_bytes = buffer.getvalue()

                # Upload updated presentation
                upload_url = f"/me/drive/items/{ent['id']}/content"
                r = await client.put(
                    upload_url,
                    headers={
                        "Authorization": f"Bearer {self.access_token}",
                        "Content-Type": (
                            "application/vnd.openxmlformats-officedocument."
                            "presentationml.presentation"
                        ),
                    },
                    content=updated_bytes,
                )

                if r.status_code in (200, 201):
                    updated.append({**ent, "updated": True})
                    self.logger.info(
                        f"📝 Updated presentation '{ent['filename']}' with token: {ent['token']}"
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
        """Delete specific PowerPoint presentations with retry for locked files."""
        if not entities:
            # If no specific entities provided, delete all tracked presentations
            entities = self._test_presentations

        if not entities:
            return []

        self.logger.info(f"🥁 Deleting {len(entities)} PowerPoint presentations")
        deleted: List[str] = []

        async with httpx.AsyncClient(base_url=GRAPH, timeout=30) as client:
            # Iterate over a copy to avoid mutation issues when entities == self._test_presentations
            for ent in list(entities):
                success = await self._delete_with_retry(
                    client, ent["id"], ent.get("filename", ent["id"])
                )

                if success:
                    deleted.append(ent["id"])
                    self.logger.info(
                        f"✅ Deleted presentation: {ent.get('filename', ent['id'])}"
                    )

                    # Remove from tracking
                    if ent in self._test_presentations:
                        self._test_presentations.remove(ent)

        return deleted

    async def cleanup(self):
        """Comprehensive cleanup of all test resources."""
        self.logger.info("🧹 Starting comprehensive PowerPoint cleanup")

        cleanup_stats = {
            "presentations_deleted": 0,
            "files_deleted": 0,
            "errors": 0,
        }

        try:
            async with httpx.AsyncClient(base_url=GRAPH, timeout=30) as client:
                # Delete tracked test presentations
                if self._test_presentations:
                    self.logger.info(
                        f"🗑️  Deleting {len(self._test_presentations)} tracked presentations"
                    )
                    deleted = await self.delete_specific_entities(
                        self._test_presentations.copy()
                    )
                    cleanup_stats["presentations_deleted"] += len(deleted)

                # Search for and cleanup any orphaned test presentations
                await self._cleanup_orphaned_files(
                    client, cleanup_stats, "Monke_", [".pptx"]
                )

            self.logger.info(
                f"🧹 Cleanup completed: {cleanup_stats['presentations_deleted']} "
                f"presentations deleted, {cleanup_stats['files_deleted']} orphaned files deleted, "
                f"{cleanup_stats['errors']} errors"
            )
        except Exception as e:
            self.logger.error(f"❌ Error during comprehensive cleanup: {e}")
