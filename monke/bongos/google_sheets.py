"""Google Sheets bongo implementation.

Creates, updates, and deletes test entities via the real Google Sheets API.
Spreadsheets are created using the Sheets API and content is populated via batchUpdate.
"""

import asyncio
import time
import uuid
from typing import Any, Dict, List

import httpx
from monke.bongos.base_bongo import BaseBongo
from monke.generation.google_sheets import generate_spreadsheets
from monke.utils.logging import get_logger

DRIVE_API = "https://www.googleapis.com/drive/v3"
SHEETS_API = "https://sheets.googleapis.com/v4"


class GoogleSheetsBongo(BaseBongo):
    """Bongo for Google Sheets that creates test entities for E2E testing.

    Key responsibilities:
    - Create test Google Sheets spreadsheets with data
    - Update spreadsheets to test incremental sync
    - Delete spreadsheets to test deletion detection
    - Clean up all test data

    Note: Creates spreadsheets using the Sheets API and populates data
    using the spreadsheets.values.batchUpdate endpoint.
    """

    connector_type = "google_sheets"

    def __init__(self, credentials: Dict[str, Any], **kwargs):
        super().__init__(credentials)
        self.access_token: str = credentials["access_token"]
        self.entity_count: int = int(kwargs.get("entity_count", 3))
        self.openai_model: str = kwargs.get("openai_model", "gpt-4.1-mini")
        self.rate_limit_delay = float(kwargs.get("rate_limit_delay_ms", 500)) / 1000.0
        self.logger = get_logger("google_sheets_bongo")

        # Track created resources for cleanup
        self._test_spreadsheets: List[Dict[str, Any]] = []
        self._last_req = 0.0

    async def create_entities(self) -> List[Dict[str, Any]]:
        """Create test Google Sheets spreadsheets using the Sheets API."""
        self.logger.info(f"🥁 Creating {self.entity_count} Google Sheets test spreadsheets")
        out: List[Dict[str, Any]] = []

        # Generate tokens for each spreadsheet
        tokens = [uuid.uuid4().hex[:8] for _ in range(self.entity_count)]

        # Generate spreadsheet content
        test_name = f"Monke_TestSheet_{uuid.uuid4().hex[:8]}"
        spreadsheets = await generate_spreadsheets(self.openai_model, tokens, test_name)

        self.logger.info(f"📝 Generated {len(spreadsheets)} spreadsheets")

        async with httpx.AsyncClient(timeout=60) as client:
            for sheet_data, token in zip(spreadsheets, tokens):
                await self._pace()
                self.logger.info(f"📤 Creating Google Sheet: {sheet_data.title}")

                # Step 1: Create spreadsheet via Sheets API
                create_payload = {
                    "properties": {"title": sheet_data.title},
                    "sheets": [
                        {
                            "properties": {
                                "title": "Data",
                                "gridProperties": {
                                    "rowCount": len(sheet_data.rows) + 1,
                                    "columnCount": len(sheet_data.headers),
                                },
                            }
                        }
                    ],
                }

                create_response = await client.post(
                    f"{SHEETS_API}/spreadsheets",
                    headers={
                        "Authorization": f"Bearer {self.access_token}",
                        "Content-Type": "application/json",
                    },
                    json=create_payload,
                )

                if create_response.status_code not in (200, 201):
                    self.logger.error(
                        f"Create failed {create_response.status_code}: "
                        f"{create_response.text}"
                    )
                    create_response.raise_for_status()

                spreadsheet = create_response.json()
                spreadsheet_id = spreadsheet["spreadsheetId"]
                self.logger.info(
                    f"✅ Created spreadsheet: {spreadsheet_id} - {sheet_data.title}"
                )

                # Step 2: Populate data using values batchUpdate
                await self._pace()

                # Prepare all values (headers + data rows)
                all_values = [sheet_data.headers] + sheet_data.rows

                values_response = await client.put(
                    f"{SHEETS_API}/spreadsheets/{spreadsheet_id}/values/Data!A1",
                    headers={
                        "Authorization": f"Bearer {self.access_token}",
                        "Content-Type": "application/json",
                    },
                    params={"valueInputOption": "USER_ENTERED"},
                    json={"values": all_values},
                )

                if values_response.status_code not in (200, 201):
                    self.logger.error(
                        f"Values update failed {values_response.status_code}: "
                        f"{values_response.text[:200]}"
                    )
                else:
                    self.logger.info(
                        f"📊 Inserted {len(all_values)} rows into spreadsheet: "
                        f"{sheet_data.title}"
                    )

                # Store entity info
                ent = {
                    "type": "spreadsheet",
                    "id": spreadsheet_id,
                    "name": sheet_data.title,
                    "token": token,
                    "expected_content": token,
                }
                out.append(ent)
                self._test_spreadsheets.append(ent)
                self.created_entities.append({"id": spreadsheet_id, "name": sheet_data.title})

                # Brief delay between creates
                await asyncio.sleep(0.5)

        self.logger.info(f"✅ Created {len(self._test_spreadsheets)} Google Sheets spreadsheets")
        return out

    async def update_entities(self) -> List[Dict[str, Any]]:
        """Update spreadsheets by adding new rows with same tokens."""
        if not self._test_spreadsheets:
            return []

        self.logger.info(
            f"🥁 Updating {min(2, len(self._test_spreadsheets))} Google Sheets spreadsheets"
        )
        updated = []

        async with httpx.AsyncClient(timeout=60) as client:
            for ent in self._test_spreadsheets[: min(2, len(self._test_spreadsheets))]:
                await self._pace()

                # Append new row with the token
                new_row = [
                    f"Updated Row - Token: {ent['token']}",
                    "Update Value 1",
                    "Update Value 2",
                ]

                append_response = await client.post(
                    f"{SHEETS_API}/spreadsheets/{ent['id']}/values/Data!A1:append",
                    headers={
                        "Authorization": f"Bearer {self.access_token}",
                        "Content-Type": "application/json",
                    },
                    params={
                        "valueInputOption": "USER_ENTERED",
                        "insertDataOption": "INSERT_ROWS",
                    },
                    json={"values": [new_row]},
                )

                if append_response.status_code in (200, 201):
                    updated.append({**ent, "updated": True})
                    self.logger.info(
                        f"📝 Updated spreadsheet '{ent['name']}' with token: {ent['token']}"
                    )
                else:
                    self.logger.warning(
                        f"Failed to update spreadsheet: {append_response.status_code} - "
                        f"{append_response.text[:200]}"
                    )

                # Brief delay between updates
                await asyncio.sleep(0.5)

        return updated

    async def delete_entities(self) -> List[str]:
        """Delete all test spreadsheets."""
        return await self.delete_specific_entities(self._test_spreadsheets[:])

    async def delete_specific_entities(
        self, entities: List[Dict[str, Any]]
    ) -> List[str]:
        """Delete specific test spreadsheets."""
        if not entities:
            entities = self._test_spreadsheets

        if not entities:
            return []

        self.logger.info(f"🥁 Deleting {len(entities)} Google Sheets spreadsheets")
        deleted: List[str] = []

        async with httpx.AsyncClient(timeout=30) as client:
            for ent in entities:
                try:
                    await self._pace()

                    # Delete the spreadsheet from Drive
                    r = await client.delete(
                        f"{DRIVE_API}/files/{ent['id']}",
                        headers={"Authorization": f"Bearer {self.access_token}"},
                    )

                    if r.status_code == 204:
                        deleted.append(ent["id"])
                        self.logger.info(f"✅ Deleted spreadsheet: {ent['name']}")
                        # Remove from tracking
                        if ent in self._test_spreadsheets:
                            self._test_spreadsheets.remove(ent)
                    else:
                        self.logger.warning(
                            f"Delete failed: {r.status_code} - {r.text[:200]}"
                        )

                except Exception as e:
                    self.logger.warning(f"Delete error for {ent['id']}: {e}")

        return deleted

    async def cleanup(self):
        """Comprehensive cleanup of all test resources."""
        self.logger.info("🧹 Starting comprehensive Google Sheets cleanup")

        cleanup_stats = {
            "spreadsheets_deleted": 0,
            "errors": 0,
        }

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                # Delete current test spreadsheets
                if self._test_spreadsheets:
                    self.logger.info(
                        f"🗑️ Deleting {len(self._test_spreadsheets)} test spreadsheets"
                    )
                    deleted = await self.delete_specific_entities(
                        self._test_spreadsheets[:]
                    )
                    cleanup_stats["spreadsheets_deleted"] += len(deleted)

                # Search for and cleanup any orphaned test spreadsheets
                await self._cleanup_orphaned_spreadsheets(client, cleanup_stats)

            self.logger.info(
                f"🧹 Cleanup completed: {cleanup_stats['spreadsheets_deleted']} "
                f"spreadsheets deleted, {cleanup_stats['errors']} errors"
            )
        except Exception as e:
            self.logger.error(f"❌ Error during comprehensive cleanup: {e}")

    async def _cleanup_orphaned_spreadsheets(
        self, client: httpx.AsyncClient, stats: Dict[str, Any]
    ):
        """Find and delete orphaned test spreadsheets from previous runs."""
        try:
            await self._pace()

            # Search for spreadsheets starting with "Monke_TestSheet_"
            r = await client.get(
                f"{DRIVE_API}/files",
                headers={"Authorization": f"Bearer {self.access_token}"},
                params={
                    "q": (
                        "name contains 'Monke_TestSheet_' and "
                        "mimeType='application/vnd.google-apps.spreadsheet'"
                    ),
                    "fields": "files(id, name)",
                },
            )

            if r.status_code == 200:
                files = r.json().get("files", [])

                if files:
                    self.logger.info(f"🔍 Found {len(files)} orphaned test spreadsheets")
                    for sheet in files:
                        try:
                            await self._pace()
                            del_r = await client.delete(
                                f"{DRIVE_API}/files/{sheet['id']}",
                                headers={
                                    "Authorization": f"Bearer {self.access_token}"
                                },
                            )
                            if del_r.status_code == 204:
                                stats["spreadsheets_deleted"] += 1
                                self.logger.info(
                                    f"✅ Deleted orphaned spreadsheet: "
                                    f"{sheet.get('name', 'Unknown')}"
                                )
                            else:
                                stats["errors"] += 1
                        except Exception as e:
                            stats["errors"] += 1
                            self.logger.warning(
                                f"⚠️ Failed to delete spreadsheet {sheet['id']}: {e}"
                            )
        except Exception as e:
            self.logger.warning(f"⚠️ Could not search for orphaned spreadsheets: {e}")

    async def _pace(self):
        """Rate limiting helper."""
        now = time.time()
        if (delta := now - self._last_req) < self.rate_limit_delay:
            await asyncio.sleep(self.rate_limit_delay - delta)
        self._last_req = time.time()
