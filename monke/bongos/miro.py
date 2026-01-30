"""Miro bongo implementation.

Creates, updates, and deletes test entities via the real Miro API.
Supports all major entity types: boards, sticky notes, cards, text, frames, tags, images, documents.

Test structure:
- Board 1: Frame A (sticky notes, cards) + Frame B (texts, images) + Tags (board-level)
- Board 2: Frame C (documents) + Cards (outside frame, tests no-frame-parent)
"""

import asyncio
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

import httpx
from monke.bongos.base_bongo import BaseBongo
from monke.utils.logging import get_logger


class MiroBongo(BaseBongo):
    """Bongo for Miro that creates board items for end-to-end testing.

    Creates multiple boards and frames to test hierarchy and breadcrumbs:
    - Board 1: Primary board with multiple frames
    - Board 2: Secondary board to test board isolation
    - Some items in frames (test frame breadcrumbs)
    - Some items outside frames (test board-only breadcrumbs)
    """

    connector_type = "miro"

    API_BASE = "https://api.miro.com/v2"

    def __init__(self, credentials: Dict[str, Any], **kwargs):
        """Initialize the Miro bongo.

        Args:
            credentials: Dict with at least "access_token" (Miro OAuth token)
            **kwargs: Configuration from config file
        """
        super().__init__(credentials)
        self.access_token: str = credentials["access_token"]
        self.entity_count: int = int(kwargs.get("entity_count", 3))
        self.openai_model: str = kwargs.get("openai_model", "gpt-4.1-mini")
        self.max_concurrency: int = int(kwargs.get("max_concurrency", 3))

        # Rate limiting - Miro has rate limits
        rate_limit_ms = int(kwargs.get("rate_limit_delay_ms", 300))
        self.rate_limit_delay: float = rate_limit_ms / 1000.0

        # Runtime state - track multiple boards
        self._boards: List[Dict[str, Any]] = []  # List of {id, name, token}
        self._frames: List[Dict[str, Any]] = []  # List of {id, board_id, name, token}

        # Track all created entities by type
        self._sticky_notes: List[Dict[str, Any]] = []
        self._cards: List[Dict[str, Any]] = []
        self._texts: List[Dict[str, Any]] = []
        self._tags: List[Dict[str, Any]] = []
        self._images: List[Dict[str, Any]] = []
        self._documents: List[Dict[str, Any]] = []

        self.last_request_time = 0.0
        self.logger = get_logger("miro_bongo")

    async def create_entities(self) -> List[Dict[str, Any]]:
        """Create all types of test entities across multiple Miro boards.

        Structure:
        - Board 1: Frame A (sticky notes, cards) + Frame B (texts, images) + Tags
        - Board 2: Frame C (documents) + Cards (no frame parent)

        Returns a list of created entity descriptors used by the test flow.
        """
        self.logger.info(f"🥁 Creating Miro test entities (count={self.entity_count})")

        from monke.generation.miro import (
            generate_sticky_note,
            generate_card,
            generate_text,
            generate_frame,
            generate_tag,
            generate_document_content,
            generate_image_metadata,
            generate_simple_png_diagram,
        )

        all_entities: List[Dict[str, Any]] = []

        async with httpx.AsyncClient(timeout=60.0) as client:
            # ============================================
            # BOARD 1: Primary board with multiple frames
            # ============================================
            board1_id, board1_token = await self._create_board(client, "Primary Board")

            # Frame A: Sticky notes and cards
            frame_a_id, frame_a_token = await self._create_frame(
                client, board1_id, generate_frame, "Frame A", x=0, y=0
            )
            all_entities.append(self._make_frame_entity(frame_a_id, frame_a_token, board1_id))

            # Frame B: Texts and images
            frame_b_id, frame_b_token = await self._create_frame(
                client, board1_id, generate_frame, "Frame B", x=1800, y=0
            )
            all_entities.append(self._make_frame_entity(frame_b_id, frame_b_token, board1_id))

            # Use semaphore for concurrent entity creation
            semaphore = asyncio.Semaphore(self.max_concurrency)

            async def create_with_semaphore(coro):
                async with semaphore:
                    return await coro

            # Tags (board-level, not in frames)
            self.logger.info("🏷️  Creating tags on Board 1...")
            tag_tasks = [
                create_with_semaphore(self._create_tag(client, board1_id, generate_tag))
                for _ in range(min(2, self.entity_count))
            ]
            tag_results = await asyncio.gather(*tag_tasks, return_exceptions=True)
            for result in tag_results:
                if isinstance(result, Exception):
                    self.logger.warning(f"⚠️  Tag creation failed: {result}")
                elif result:
                    all_entities.append(result)

            # Sticky notes in Frame A
            self.logger.info(f"📝 Creating {self.entity_count} sticky notes in Frame A...")
            sticky_tasks = [
                create_with_semaphore(
                    self._create_sticky_note(
                        client, board1_id, frame_a_id, generate_sticky_note,
                        x=100 + (i * 300), y=100
                    )
                )
                for i in range(self.entity_count)
            ]
            sticky_results = await asyncio.gather(*sticky_tasks, return_exceptions=True)
            for result in sticky_results:
                if isinstance(result, Exception):
                    self.logger.error(f"❌ Sticky note creation failed: {result}")
                elif result:
                    all_entities.append(result)

            # Cards in Frame A
            self.logger.info(f"🃏 Creating {self.entity_count} cards in Frame A...")
            card_tasks = [
                create_with_semaphore(
                    self._create_card(
                        client, board1_id, frame_a_id, generate_card,
                        x=100 + (i * 300), y=400
                    )
                )
                for i in range(self.entity_count)
            ]
            card_results = await asyncio.gather(*card_tasks, return_exceptions=True)
            for result in card_results:
                if isinstance(result, Exception):
                    self.logger.error(f"❌ Card creation failed: {result}")
                elif result:
                    all_entities.append(result)

            # Text items in Frame B
            self.logger.info(f"📄 Creating {self.entity_count} text items in Frame B...")
            text_tasks = [
                create_with_semaphore(
                    self._create_text(
                        client, board1_id, frame_b_id, generate_text,
                        x=100 + (i * 300), y=100
                    )
                )
                for i in range(self.entity_count)
            ]
            text_results = await asyncio.gather(*text_tasks, return_exceptions=True)
            for result in text_results:
                if isinstance(result, Exception):
                    self.logger.error(f"❌ Text creation failed: {result}")
                elif result:
                    all_entities.append(result)

            # Images in Frame B
            self.logger.info("🖼️  Creating images in Frame B...")
            image_tasks = [
                create_with_semaphore(
                    self._create_image(
                        client, board1_id, frame_b_id,
                        generate_image_metadata, generate_simple_png_diagram,
                        x=100 + (i * 250), y=400, index=i
                    )
                )
                for i in range(min(2, self.entity_count))
            ]
            image_results = await asyncio.gather(*image_tasks, return_exceptions=True)
            for result in image_results:
                if isinstance(result, Exception):
                    self.logger.warning(f"⚠️  Image creation failed: {result}")
                elif result:
                    all_entities.append(result)

            # ============================================
            # BOARD 2: Secondary board (tests board isolation)
            # ============================================
            board2_id, board2_token = await self._create_board(client, "Secondary Board")

            # Frame C: Documents
            frame_c_id, frame_c_token = await self._create_frame(
                client, board2_id, generate_frame, "Frame C", x=0, y=0
            )
            all_entities.append(self._make_frame_entity(frame_c_id, frame_c_token, board2_id))

            # Documents in Frame C
            self.logger.info("📎 Creating documents in Frame C on Board 2...")
            doc_tasks = [
                create_with_semaphore(
                    self._create_document(
                        client, board2_id, frame_c_id, generate_document_content,
                        x=100 + (i * 250), y=100
                    )
                )
                for i in range(min(2, self.entity_count))
            ]
            doc_results = await asyncio.gather(*doc_tasks, return_exceptions=True)
            for result in doc_results:
                if isinstance(result, Exception):
                    self.logger.warning(f"⚠️  Document creation failed: {result}")
                elif result:
                    all_entities.append(result)

            # Cards outside any frame (tests no-frame-parent breadcrumbs)
            self.logger.info("🃏 Creating cards outside frames on Board 2...")
            card2_tasks = [
                create_with_semaphore(
                    self._create_card(
                        client, board2_id, None, generate_card,  # No frame parent
                        x=100 + (i * 300), y=600
                    )
                )
                for i in range(min(2, self.entity_count))
            ]
            card2_results = await asyncio.gather(*card2_tasks, return_exceptions=True)
            for result in card2_results:
                if isinstance(result, Exception):
                    self.logger.error(f"❌ Card creation failed: {result}")
                elif result:
                    all_entities.append(result)

        # Log summary
        self.logger.info(
            f"✅ Created entities across {len(self._boards)} boards: "
            f"{len(self._frames)} frames, "
            f"{len(self._sticky_notes)} sticky notes, "
            f"{len(self._cards)} cards, "
            f"{len(self._texts)} texts, "
            f"{len(self._tags)} tags, "
            f"{len(self._images)} images, "
            f"{len(self._documents)} documents"
        )

        self.created_entities = all_entities
        return all_entities

    # ============================================
    # Entity Creation Helpers
    # ============================================

    async def _create_board(self, client: httpx.AsyncClient, label: str) -> Tuple[str, str]:
        """Create a test board and return (board_id, token)."""
        board_token = str(uuid.uuid4())[:8]
        board_name = f"monke-miro-test-{board_token}"

        await self._rate_limit()
        resp = await client.post(
            f"{self.API_BASE}/boards",
            headers=self._headers(),
            json={
                "name": board_name,
                "description": f"Automated test board ({label}) created by Monke. Token: {board_token}",
            },
        )

        if resp.status_code not in (200, 201):
            self.logger.error(f"❌ Failed to create board: {resp.status_code} - {resp.text}")
            resp.raise_for_status()

        board = resp.json()
        board_id = board["id"]

        self._boards.append({"id": board_id, "name": board_name, "token": board_token})
        self.logger.info(f"✅ Created board: {board_name} ({board_id})")

        return board_id, board_token

    async def _create_frame(
        self, client: httpx.AsyncClient, board_id: str, generate_fn, label: str, x: int, y: int
    ) -> Tuple[str, str]:
        """Create a frame and return (frame_id, token)."""
        frame_token = str(uuid.uuid4())[:8]
        frame_title, _ = await generate_fn(self.openai_model, frame_token)

        await self._rate_limit()
        resp = await client.post(
            f"{self.API_BASE}/boards/{board_id}/frames",
            headers=self._headers(),
            json={
                "data": {"title": frame_title, "format": "custom"},
                "position": {"x": x, "y": y},
                "geometry": {"width": 1600, "height": 1000},
            },
        )

        if resp.status_code not in (200, 201):
            self.logger.error(f"❌ Failed to create frame: {resp.status_code} - {resp.text}")
            resp.raise_for_status()

        frame = resp.json()
        frame_id = frame["id"]

        self._frames.append({
            "id": frame_id, "board_id": board_id, "name": frame_title, "token": frame_token
        })
        self.logger.info(f"🖼️  Created frame ({label}): {frame_title[:40]}...")

        return frame_id, frame_token

    def _make_frame_entity(self, frame_id: str, token: str, board_id: str) -> Dict[str, Any]:
        """Create frame entity descriptor."""
        return {
            "type": "frame",
            "id": frame_id,
            "board_id": board_id,
            "token": token,
            "expected_content": token,
            "path": f"miro/frame/{frame_id}",
        }

    async def _create_tag(self, client: httpx.AsyncClient, board_id: str, generate_fn) -> Optional[Dict[str, Any]]:
        """Create a tag on a board."""
        tag_token = str(uuid.uuid4())[:8]
        tag_title = await generate_fn(self.openai_model, tag_token)

        await self._rate_limit()
        resp = await client.post(
            f"{self.API_BASE}/boards/{board_id}/tags",
            headers=self._headers(),
            json={"title": tag_title, "fillColor": "yellow"},
        )

        if resp.status_code not in (200, 201):
            self.logger.warning(f"⚠️  Failed to create tag: {resp.status_code} - {resp.text}")
            return None

        tag = resp.json()
        entity = {
            "type": "tag",
            "id": tag["id"],
            "board_id": board_id,
            "name": tag_title,
            "token": tag_token,
            "expected_content": tag_token,
            "path": f"miro/tag/{tag['id']}",
        }
        self._tags.append(entity)
        self.logger.info(f"🏷️  Created tag: {tag_title[:30]}...")
        return entity

    async def _create_sticky_note(
        self, client: httpx.AsyncClient, board_id: str, frame_id: Optional[str],
        generate_fn, x: int, y: int
    ) -> Optional[Dict[str, Any]]:
        """Create a sticky note."""
        token = str(uuid.uuid4())[:8]
        content, color = await generate_fn(self.openai_model, token)

        payload = {
            "data": {"content": content, "shape": "square"},
            "style": {"fillColor": color},
            "position": {"x": x, "y": y},
        }
        if frame_id:
            payload["parent"] = {"id": frame_id}

        await self._rate_limit()
        resp = await client.post(
            f"{self.API_BASE}/boards/{board_id}/sticky_notes",
            headers=self._headers(),
            json=payload,
        )

        if resp.status_code not in (200, 201):
            self.logger.error(f"❌ Failed to create sticky note: {resp.status_code} - {resp.text}")
            return None

        sticky = resp.json()
        entity = {
            "type": "sticky_note",
            "id": sticky["id"],
            "board_id": board_id,
            "frame_id": frame_id,
            "name": content[:50],
            "token": token,
            "expected_content": token,
            "path": f"miro/sticky_note/{sticky['id']}",
        }
        self._sticky_notes.append(entity)
        return entity

    async def _create_card(
        self, client: httpx.AsyncClient, board_id: str, frame_id: Optional[str],
        generate_fn, x: int, y: int
    ) -> Optional[Dict[str, Any]]:
        """Create a card."""
        token = str(uuid.uuid4())[:8]
        title, description, due_date = await generate_fn(self.openai_model, token)

        payload = {
            "data": {"title": title, "description": description},
            "position": {"x": x, "y": y},
        }
        if frame_id:
            payload["parent"] = {"id": frame_id}
        if due_date:
            payload["data"]["dueDate"] = due_date

        await self._rate_limit()
        resp = await client.post(
            f"{self.API_BASE}/boards/{board_id}/cards",
            headers=self._headers(),
            json=payload,
        )

        if resp.status_code not in (200, 201):
            self.logger.error(f"❌ Failed to create card: {resp.status_code} - {resp.text}")
            return None

        card = resp.json()
        entity = {
            "type": "card",
            "id": card["id"],
            "board_id": board_id,
            "frame_id": frame_id,
            "name": title[:50],
            "token": token,
            "expected_content": token,
            "path": f"miro/card/{card['id']}",
        }
        self._cards.append(entity)
        return entity

    async def _create_text(
        self, client: httpx.AsyncClient, board_id: str, frame_id: Optional[str],
        generate_fn, x: int, y: int
    ) -> Optional[Dict[str, Any]]:
        """Create a text item."""
        token = str(uuid.uuid4())[:8]
        content = await generate_fn(self.openai_model, token)

        payload = {
            "data": {"content": content},
            "position": {"x": x, "y": y},
        }
        if frame_id:
            payload["parent"] = {"id": frame_id}

        await self._rate_limit()
        resp = await client.post(
            f"{self.API_BASE}/boards/{board_id}/texts",
            headers=self._headers(),
            json=payload,
        )

        if resp.status_code not in (200, 201):
            self.logger.error(f"❌ Failed to create text: {resp.status_code} - {resp.text}")
            return None

        text = resp.json()
        entity = {
            "type": "text",
            "id": text["id"],
            "board_id": board_id,
            "frame_id": frame_id,
            "name": content[:50],
            "token": token,
            "expected_content": token,
            "path": f"miro/text/{text['id']}",
        }
        self._texts.append(entity)
        return entity

    async def _create_image(
        self, client: httpx.AsyncClient, board_id: str, frame_id: Optional[str],
        generate_metadata_fn, generate_png_fn, x: int, y: int, index: int
    ) -> Optional[Dict[str, Any]]:
        """Create an image (upload PNG with OCR-readable token)."""
        token = str(uuid.uuid4())[:8]
        filename, alt_text = await generate_metadata_fn(self.openai_model, token)
        png_content = generate_png_fn(token, f"Test Diagram {index + 1}")

        await self._rate_limit()
        files = {"resource": (filename, png_content, "image/png")}
        data = {"title": alt_text}

        resp = await client.post(
            f"{self.API_BASE}/boards/{board_id}/images",
            headers={"Authorization": f"Bearer {self.access_token}"},
            files=files,
            data=data,
        )

        if resp.status_code not in (200, 201):
            self.logger.warning(f"⚠️  Failed to upload image: {resp.status_code} - {resp.text}")
            return None

        image = resp.json()

        # Update position to be inside frame if specified
        if frame_id:
            await self._rate_limit()
            await client.patch(
                f"{self.API_BASE}/boards/{board_id}/images/{image['id']}",
                headers=self._headers(),
                json={"position": {"x": x, "y": y}, "parent": {"id": frame_id}},
            )

        entity = {
            "type": "image",
            "id": image["id"],
            "board_id": board_id,
            "frame_id": frame_id,
            "name": filename,
            "token": token,
            "expected_content": token,
            "path": f"miro/image/{image['id']}",
        }
        self._images.append(entity)
        self.logger.info(f"🖼️  Created image: {filename}")
        return entity

    async def _create_document(
        self, client: httpx.AsyncClient, board_id: str, frame_id: Optional[str],
        generate_fn, x: int, y: int
    ) -> Optional[Dict[str, Any]]:
        """Create a document (upload CSV file)."""
        token = str(uuid.uuid4())[:8]
        filename, content = await generate_fn(self.openai_model, token)
        content_bytes = content.encode("utf-8")

        await self._rate_limit()
        files = {"resource": (filename, content_bytes, "text/csv")}
        data = {"title": filename}

        resp = await client.post(
            f"{self.API_BASE}/boards/{board_id}/documents",
            headers={"Authorization": f"Bearer {self.access_token}"},
            files=files,
            data=data,
        )

        if resp.status_code not in (200, 201):
            self.logger.warning(f"⚠️  Failed to upload document: {resp.status_code} - {resp.text}")
            return None

        doc = resp.json()

        # Update position to be inside frame if specified
        if frame_id:
            await self._rate_limit()
            await client.patch(
                f"{self.API_BASE}/boards/{board_id}/documents/{doc['id']}",
                headers=self._headers(),
                json={"position": {"x": x, "y": y}, "parent": {"id": frame_id}},
            )

        entity = {
            "type": "document",
            "id": doc["id"],
            "board_id": board_id,
            "frame_id": frame_id,
            "name": filename,
            "token": token,
            "expected_content": token,
            "path": f"miro/document/{doc['id']}",
        }
        self._documents.append(entity)
        self.logger.info(f"📎 Created document: {filename}")
        return entity

    # ============================================
    # Update / Delete / Cleanup
    # ============================================

    async def update_entities(self) -> List[Dict[str, Any]]:
        """Update a subset of entities to test incremental sync."""
        self.logger.info("🥁 Updating some Miro entities...")

        from monke.generation.miro import generate_sticky_note, generate_card

        updated_entities: List[Dict[str, Any]] = []

        async with httpx.AsyncClient(timeout=60.0) as client:
            # Update first 2 sticky notes
            for i in range(min(2, len(self._sticky_notes))):
                entity = self._sticky_notes[i]
                new_content, color = await generate_sticky_note(self.openai_model, entity["token"])

                await self._rate_limit()
                resp = await client.patch(
                    f"{self.API_BASE}/boards/{entity['board_id']}/sticky_notes/{entity['id']}",
                    headers=self._headers(),
                    json={"data": {"content": new_content}},
                )

                if resp.status_code == 200:
                    updated_entities.append({**entity, "name": new_content[:50]})
                    self.logger.info(f"✅ Updated sticky note: {entity['id']}")
                else:
                    self.logger.warning(f"⚠️  Failed to update sticky note: {resp.status_code}")

            # Update first 2 cards
            for i in range(min(2, len(self._cards))):
                entity = self._cards[i]
                title, description, _ = await generate_card(self.openai_model, entity["token"])

                await self._rate_limit()
                resp = await client.patch(
                    f"{self.API_BASE}/boards/{entity['board_id']}/cards/{entity['id']}",
                    headers=self._headers(),
                    json={"data": {"title": title, "description": description}},
                )

                if resp.status_code == 200:
                    updated_entities.append({**entity, "name": title[:50]})
                    self.logger.info(f"✅ Updated card: {entity['id']}")
                else:
                    self.logger.warning(f"⚠️  Failed to update card: {resp.status_code}")

        return updated_entities

    async def delete_entities(self) -> List[str]:
        """Delete all created entities and test boards."""
        self.logger.info("🗑️  Deleting all Miro test entities...")
        deleted_ids = await self.delete_specific_entities(self.created_entities)

        # Delete all test boards
        for board in self._boards:
            await self._delete_board_by_id(board["id"])

        self._boards = []
        return deleted_ids

    async def delete_specific_entities(self, entities: List[Dict[str, Any]]) -> List[str]:
        """Delete provided list of entities by id."""
        self.logger.info(f"🗑️  Deleting {len(entities)} Miro entities...")
        deleted: List[str] = []

        type_to_endpoint = {
            "sticky_note": "sticky_notes",
            "card": "cards",
            "text": "texts",
            "frame": "frames",
            "tag": "tags",
            "image": "images",
            "document": "documents",
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            for entity in entities:
                entity_type = entity.get("type")
                entity_id = entity.get("id")
                board_id = entity.get("board_id")

                # If no board_id stored, try to find it
                if not board_id and self._boards:
                    board_id = self._boards[0]["id"]

                if entity_type not in type_to_endpoint or not board_id:
                    self.logger.warning(f"⚠️  Cannot delete {entity_type}: missing info")
                    continue

                endpoint = type_to_endpoint[entity_type]

                try:
                    await self._rate_limit()
                    url = f"{self.API_BASE}/boards/{board_id}/{endpoint}/{entity_id}"
                    resp = await client.delete(url, headers=self._headers())

                    if resp.status_code in (200, 204, 404):
                        deleted.append(entity_id)
                        self.logger.debug(f"🗑️  Deleted {entity_type}: {entity_id}")
                    else:
                        self.logger.warning(
                            f"⚠️  Failed to delete {entity_type} {entity_id}: {resp.status_code}"
                        )
                except Exception as e:
                    self.logger.warning(f"⚠️  Error deleting {entity_type} {entity_id}: {e}")

        return deleted

    async def cleanup(self):
        """Comprehensive cleanup of all monke test data."""
        self.logger.info("🧹 Starting comprehensive Miro cleanup...")

        cleanup_stats = {"boards_deleted": 0, "items_deleted": 0, "errors": 0}

        try:
            # Clean up current session entities first
            if self.created_entities:
                self.logger.info(f"🗑️  Cleaning up {len(self.created_entities)} current session entities")
                deleted = await self.delete_specific_entities(self.created_entities)
                cleanup_stats["items_deleted"] += len(deleted)

            # Delete all tracked boards
            for board in self._boards:
                try:
                    await self._delete_board_by_id(board["id"])
                    cleanup_stats["boards_deleted"] += 1
                except Exception as e:
                    cleanup_stats["errors"] += 1
                    self.logger.warning(f"⚠️  Failed to delete board {board['id']}: {e}")

            self._boards = []

            # Find and clean up orphaned monke test boards
            orphaned_boards = await self._find_monke_test_boards()
            if orphaned_boards:
                self.logger.info(f"🔍 Found {len(orphaned_boards)} orphaned monke test boards")
                for board in orphaned_boards:
                    try:
                        await self._delete_board_by_id(board["id"])
                        cleanup_stats["boards_deleted"] += 1
                        self.logger.info(f"✅ Deleted orphaned board: {board['name']}")
                    except Exception as e:
                        cleanup_stats["errors"] += 1
                        self.logger.warning(f"⚠️  Failed to delete board {board['id']}: {e}")

            self.logger.info(
                f"🧹 Cleanup completed: {cleanup_stats['boards_deleted']} boards, "
                f"{cleanup_stats['items_deleted']} items deleted, "
                f"{cleanup_stats['errors']} errors"
            )

        except Exception as e:
            self.logger.error(f"❌ Error during cleanup: {e}")

    async def _delete_board_by_id(self, board_id: str):
        """Delete a board by ID."""
        async with httpx.AsyncClient(timeout=60.0) as client:
            await self._rate_limit()
            resp = await client.delete(
                f"{self.API_BASE}/boards/{board_id}",
                headers=self._headers(),
            )

            if resp.status_code in (200, 204):
                self.logger.debug(f"🗑️  Deleted board: {board_id}")
            elif resp.status_code == 404:
                self.logger.debug(f"ℹ️  Board already deleted: {board_id}")
            else:
                self.logger.warning(f"⚠️  Failed to delete board {board_id}: {resp.status_code}")

    async def _find_monke_test_boards(self) -> List[Dict[str, Any]]:
        """Find all monke test boards."""
        monke_boards = []

        async with httpx.AsyncClient(timeout=60.0) as client:
            await self._rate_limit()
            resp = await client.get(
                f"{self.API_BASE}/boards",
                headers=self._headers(),
                params={"limit": 50},
            )

            if resp.status_code != 200:
                self.logger.warning(f"⚠️  Failed to list boards: {resp.status_code}")
                return []

            boards = resp.json().get("data", [])
            for board in boards:
                name = board.get("name", "")
                if name.startswith("monke-miro-test-") or "monke" in name.lower():
                    monke_boards.append(board)

        return monke_boards

    def _headers(self) -> Dict[str, str]:
        """Return auth headers for API requests."""
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    async def _rate_limit(self):
        """Simple rate limiting."""
        now = time.time()
        delta = now - self.last_request_time
        if delta < self.rate_limit_delay:
            await asyncio.sleep(self.rate_limit_delay - delta)
        self.last_request_time = time.time()
