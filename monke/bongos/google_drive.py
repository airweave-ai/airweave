"""Google Drive-specific bongo implementation."""

import asyncio
import time
import uuid
from typing import Any, Dict, List

import httpx
from monke.bongos.base_bongo import BaseBongo
from monke.generation.google_drive import get_media_content_type
from monke.utils.logging import get_logger


class GoogleDriveBongo(BaseBongo):
    """Google Drive-specific bongo implementation.

    Creates, updates, and deletes test files via the real Google Drive API.
    """

    connector_type = "google_drive"

    def __init__(self, credentials: Dict[str, Any], **kwargs):
        """Initialize the Google Drive bongo.

        Args:
            credentials: Google Drive credentials with access_token
            **kwargs: Additional configuration (e.g., entity_count, file_types)
        """
        super().__init__(credentials)
        self.access_token = credentials["access_token"]

        # Configuration from kwargs
        self.entity_count = kwargs.get("entity_count", 10)
        self.file_types = kwargs.get("file_types", ["document", "spreadsheet", "pdf"])
        self.llm_model = kwargs.get("llm_model", None)

        # Test data tracking
        self.test_files = []
        self.test_folder_id = None

        # Rate limiting (Google Drive: 1000 requests per 100 seconds)
        self.last_request_time = 0
        self.rate_limit_delay = 0.5  # 0.5 second between requests (conservative)

        # Logger
        self.logger = get_logger("google_drive_bongo")

    async def create_entities(self) -> List[Dict[str, Any]]:
        """Create test files in Google Drive."""
        self.logger.info(f"🥁 Creating {self.entity_count} test files in Google Drive")
        entities = []

        # First, create a test folder
        await self._ensure_test_folder()

        # Create files based on configuration
        from monke.generation.google_drive import generate_google_drive_artifact

        for i in range(self.entity_count):
            file_type = self.file_types[i % len(self.file_types)]
            # Short unique token used in filename and content for verification
            token = str(uuid.uuid4())[:8]

            title, content, mime_type = await generate_google_drive_artifact(
                file_type, self.llm_model, token
            )

            filename = self._filename_with_extension(f"{title}-{token}", file_type)

            # Create file
            file_data = await self._create_test_file(
                self.test_folder_id, filename, content, mime_type
            )

            entities.append(
                {
                    "type": "file",
                    "id": file_data["id"],
                    "name": file_data["name"],
                    "folder_id": self.test_folder_id,
                    "file_type": file_type,
                    "mime_type": mime_type,
                    "token": token,
                    "expected_content": token,
                }
            )

            self.logger.info(f"📄 Created test file: {file_data['name']}")

            # Rate limiting
            if self.entity_count > 10:
                await asyncio.sleep(0.5)

        self.test_files = entities  # Store for later operations
        return entities

    async def update_entities(self) -> List[Dict[str, Any]]:
        """Update test entities in Google Drive."""
        self.logger.info("🥁 Updating test files in Google Drive")
        updated_entities = []

        # Update a subset of files based on configuration
        from monke.generation.google_drive import generate_google_drive_artifact

        files_to_update = min(3, self.entity_count)  # Update max 3 files for any test size

        for i in range(files_to_update):
            if i < len(self.test_files):
                file_info = self.test_files[i]
                file_type = file_info.get("file_type", "document")
                token = file_info.get("token") or str(uuid.uuid4())[:8]

                # Generate new content with same token
                title, content, mime_type = await generate_google_drive_artifact(
                    file_type, self.llm_model, token, is_update=True
                )

                # Update file content
                updated_file = await self._update_test_file(file_info["id"], content, mime_type)

                updated_entities.append(
                    {
                        "type": "file",
                        "id": file_info["id"],
                        "name": updated_file["name"],
                        "folder_id": self.test_folder_id,
                        "file_type": file_type,
                        "mime_type": mime_type,
                        "token": token,
                        "expected_content": token,
                        "updated": True,
                    }
                )

                self.logger.info(f"📝 Updated test file: {updated_file['name']}")

                # Rate limiting
                if self.entity_count > 10:
                    await asyncio.sleep(0.5)

        return updated_entities

    async def delete_entities(self) -> List[str]:
        """Delete all test entities from Google Drive."""
        self.logger.info("🥁 Deleting all test files from Google Drive")

        # Use the specific deletion method to delete all entities
        return await self.delete_specific_entities(self.created_entities)

    async def delete_specific_entities(self, entities: List[Dict[str, Any]]) -> List[str]:
        """Delete specific entities from Google Drive."""
        self.logger.info(f"🥁 Deleting {len(entities)} specific files from Google Drive")

        deleted_ids = []

        for entity in entities:
            try:
                # Find the corresponding test file
                test_file = next((tf for tf in self.test_files if tf["id"] == entity["id"]), None)

                if test_file:
                    await self._delete_test_file(test_file["id"])
                    deleted_ids.append(test_file["id"])
                    self.logger.info(f"🗑️ Deleted test file: {test_file['name']}")
                else:
                    self.logger.warning(
                        f"⚠️ Could not find test file for entity: {entity.get('id')}"
                    )

                # Rate limiting
                if len(entities) > 10:
                    await asyncio.sleep(0.5)

            except Exception as e:
                self.logger.warning(f"⚠️ Could not delete entity {entity.get('id')}: {e}")

        # VERIFICATION: Check if files are actually deleted
        self.logger.info("🔍 VERIFYING: Checking if files are actually deleted from Google Drive")
        for entity in entities:
            if entity["id"] in deleted_ids:
                is_deleted = await self._verify_file_deleted(entity["id"])
                if is_deleted:
                    self.logger.info(f"✅ File {entity['id']} confirmed deleted from Google Drive")
                else:
                    self.logger.warning(f"⚠️ File {entity['id']} still exists in Google Drive!")

        return deleted_ids

    async def cleanup(self):
        """Clean up any remaining test data."""
        self.logger.info("🧹 Cleaning up remaining test files in Google Drive")

        # Force delete any remaining test files
        for test_file in self.test_files:
            try:
                await self._force_delete_file(test_file["id"])
                self.logger.info(f"🧹 Force deleted file: {test_file['name']}")
            except Exception as e:
                self.logger.warning(f"⚠️ Could not force delete file {test_file['name']}: {e}")

        # Delete the test folder if it was created
        if self.test_folder_id:
            try:
                await self._delete_test_folder(self.test_folder_id)
                self.logger.info(f"🧹 Deleted test folder: {self.test_folder_id}")
            except Exception as e:
                self.logger.warning(f"⚠️ Could not delete test folder: {e}")

    # Helper methods for Google Drive API calls
    async def _ensure_test_folder(self):
        """Ensure we have a test folder to work with."""
        await self._rate_limit()

        # Create a new test folder
        folder_name = f"Monke Test Folder - {str(uuid.uuid4())[:8]}"

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://www.googleapis.com/drive/v3/files",
                headers={
                    "Authorization": f"Bearer {self.access_token}",
                    "Content-Type": "application/json",
                },
                json={
                    "name": folder_name,
                    "mimeType": "application/vnd.google-apps.folder",
                    "description": "Temporary folder for Monke testing",
                },
            )

            if response.status_code != 200:
                raise Exception(
                    f"Failed to create folder: {response.status_code} - {response.text}"
                )

            result = response.json()
            self.test_folder_id = result["id"]
            self.logger.info(f"📁 Created test folder: {self.test_folder_id}")

    async def _create_test_file(
        self, folder_id: str, filename: str, content: str, mime_type: str
    ) -> Dict[str, Any]:
        """Create a test file via Google Drive API (resumable)."""
        await self._rate_limit()

        # Metadata
        metadata = {"name": filename, "parents": [folder_id]}
        # Only set Google-native types in metadata; others can be inferred from media.
        if mime_type in (
            "application/vnd.google-apps.document",
            "application/vnd.google-apps.spreadsheet",
        ):
            metadata["mimeType"] = mime_type

        content_bytes = content.encode("utf-8")
        # Infer the *media* type we are uploading (critical for import to Docs/Sheets)
        media_type = get_media_content_type(
            file_type=(
                "document"
                if mime_type == "application/vnd.google-apps.document"
                else (
                    "spreadsheet"
                    if mime_type == "application/vnd.google-apps.spreadsheet"
                    else (
                        "pdf"
                        if mime_type == "application/pdf"
                        else "markdown" if mime_type == "text/markdown" else "text"
                    )
                )
            ),
            target_mime=mime_type,
        )

        async with httpx.AsyncClient() as client:
            # 1) INIT RESUMABLE SESSION
            init_response = await client.post(
                "https://www.googleapis.com/upload/drive/v3/files?uploadType=resumable",
                headers={
                    "Authorization": f"Bearer {self.access_token}",
                    # Required when sending metadata:
                    # https://developers.google.com/workspace/drive/api/guides/manage-uploads
                    "Content-Type": "application/json",
                    # Tell Drive what media type is coming so it doesn't default to octet-stream
                    # (Docs: X-Upload-Content-Type optional, but critical for import)
                    "X-Upload-Content-Type": media_type,
                    "X-Upload-Content-Length": str(len(content_bytes)),
                },
                json=metadata,
            )
            if init_response.status_code != 200:
                raise Exception(
                    f"Failed to initialize upload: {init_response.status_code} - {init_response.text}"
                )

            upload_url = init_response.headers.get("Location")
            if not upload_url:
                raise Exception("Resumable upload URL not returned in Location header")

            # 2) UPLOAD MEDIA (single request)
            upload_response = await client.put(
                upload_url,
                headers={
                    "Content-Type": media_type,
                    "Content-Length": str(len(content_bytes)),
                },
                content=content_bytes,
            )

            if upload_response.status_code not in (200, 201):
                raise Exception(
                    f"Failed to upload content: {upload_response.status_code} - {upload_response.text}"
                )

            result = upload_response.json()

            # Track created file
            self.created_entities.append({"id": result["id"], "name": result["name"]})

            return result

    @staticmethod
    def _filename_with_extension(filename: str, file_type: str) -> str:
        """
        Ensure files that need real extensions have them.
        We keep Google-native types extensionless; add for pdf/text/markdown.
        """
        ext_map = {
            "pdf": ".pdf",
            "text": ".txt",
            "markdown": ".md",
        }
        ext = ext_map.get(file_type)
        if ext and not filename.lower().endswith(ext):
            return f"{filename}{ext}"
        return filename

    async def _ensure_drive_name_extension(self, file_id: str, file_type: str):
        """
        If an existing Drive file is missing the expected extension, rename it.
        Safe no-op for Google-native types (Docs/Sheets).
        """
        ext_map = {
            "pdf": ".pdf",
            "text": ".txt",
            "markdown": ".md",
        }
        desired_ext = ext_map.get(file_type)
        if not desired_ext:
            return  # Docs/Sheets or unsupported -> nothing to do

        async with httpx.AsyncClient() as client:
            # Fetch current name
            meta_resp = await client.get(
                f"https://www.googleapis.com/drive/v3/files/{file_id}?fields=name",
                headers={"Authorization": f"Bearer {self.access_token}"},
            )
            if meta_resp.status_code != 200:
                return

            name = meta_resp.json().get("name", "")
            if name and not name.lower().endswith(desired_ext):
                await client.patch(
                    f"https://www.googleapis.com/drive/v3/files/{file_id}",
                    headers={
                        "Authorization": f"Bearer {self.access_token}",
                        "Content-Type": "application/json",
                    },
                    json={"name": f"{name}{desired_ext}"},
                )

    async def _update_test_file(self, file_id: str, content: str, mime_type: str) -> Dict[str, Any]:
        """Update a test file via Google Drive API (resumable)."""
        await self._rate_limit()

        content_bytes = content.encode("utf-8")
        # Infer the media type from the target mime
        media_type = get_media_content_type(
            # infer a file_type-ish hint from the target mime
            file_type=(
                "document"
                if mime_type == "application/vnd.google-apps.document"
                else (
                    "spreadsheet"
                    if mime_type == "application/vnd.google-apps.spreadsheet"
                    else (
                        "pdf"
                        if mime_type == "application/pdf"
                        else "markdown" if mime_type == "text/markdown" else "text"
                    )
                )
            ),
            target_mime=mime_type,
        )

        async with httpx.AsyncClient() as client:
            # INIT RESUMABLE SESSION for update (PATCH per docs)
            init_response = await client.patch(
                f"https://www.googleapis.com/upload/drive/v3/files/{file_id}?uploadType=resumable",
                headers={
                    "Authorization": f"Bearer {self.access_token}",
                    "Content-Type": "application/json",
                    "X-Upload-Content-Type": media_type,
                    "X-Upload-Content-Length": str(len(content_bytes)),
                },
                json={},  # content-only update
            )
            if init_response.status_code != 200:
                raise Exception(
                    f"Failed to initialize update: {init_response.status_code} - {init_response.text}"
                )

            upload_url = init_response.headers.get("Location")
            if not upload_url:
                raise Exception("Resumable upload URL not returned in Location header")

            # UPLOAD MEDIA
            upload_response = await client.put(
                upload_url,
                headers={
                    "Content-Type": media_type,
                    "Content-Length": str(len(content_bytes)),
                },
                content=content_bytes,
            )

            if upload_response.status_code not in (200, 201):
                raise Exception(
                    f"Failed to update content: {upload_response.status_code} - {upload_response.text}"
                )

            return upload_response.json()

    async def _delete_test_file(self, file_id: str):
        """Delete a test file via Google Drive API."""
        await self._rate_limit()

        async with httpx.AsyncClient() as client:
            response = await client.delete(
                f"https://www.googleapis.com/drive/v3/files/{file_id}",
                headers={"Authorization": f"Bearer {self.access_token}"},
            )

            if response.status_code != 204:
                raise Exception(f"Failed to delete file: {response.status_code} - {response.text}")

    async def _verify_file_deleted(self, file_id: str) -> bool:
        """Verify if a file is actually deleted from Google Drive."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"https://www.googleapis.com/drive/v3/files/{file_id}",
                    headers={"Authorization": f"Bearer {self.access_token}"},
                )

                if response.status_code == 404:
                    # File not found - successfully deleted
                    return True
                elif response.status_code == 200:
                    # Check if file is trashed
                    data = response.json()
                    return data.get("trashed", False)
                else:
                    # Unexpected response
                    self.logger.warning(
                        f"⚠️ Unexpected response checking {file_id}: {response.status_code}"
                    )
                    return False

        except Exception as e:
            self.logger.warning(f"⚠️ Error verifying file deletion for {file_id}: {e}")
            return False

    async def _force_delete_file(self, file_id: str):
        """Force delete a file (permanently)."""
        try:
            # First trash the file
            await self._delete_test_file(file_id)

            # Then permanently delete
            async with httpx.AsyncClient() as client:
                response = await client.delete(
                    f"https://www.googleapis.com/drive/v3/files/{file_id}?supportsAllDrives=true",
                    headers={"Authorization": f"Bearer {self.access_token}"},
                )

                if response.status_code == 204:
                    self.logger.info(f"🧹 Force deleted file: {file_id}")
                else:
                    self.logger.warning(
                        f"⚠️ Force delete failed for {file_id}: {response.status_code}"
                    )
        except Exception as e:
            self.logger.warning(f"Could not force delete {file_id}: {e}")

    async def _delete_test_folder(self, folder_id: str):
        """Delete the test folder."""
        await self._rate_limit()

        async with httpx.AsyncClient() as client:
            response = await client.delete(
                f"https://www.googleapis.com/drive/v3/files/{folder_id}",
                headers={"Authorization": f"Bearer {self.access_token}"},
            )

            if response.status_code != 204:
                raise Exception(
                    f"Failed to delete folder: {response.status_code} - {response.text}"
                )

    async def _rate_limit(self):
        """Implement rate limiting for Google Drive API."""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time

        if time_since_last < self.rate_limit_delay:
            sleep_time = self.rate_limit_delay - time_since_last
            await asyncio.sleep(sleep_time)

        self.last_request_time = time.time()
