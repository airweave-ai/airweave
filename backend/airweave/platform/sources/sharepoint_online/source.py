"""SharePoint Online source.

Syncs data from SharePoint Online via Microsoft Graph API.

Entity hierarchy:
- Sites - discovered via search or explicit URL
- Drives - document libraries within each site
- Items/Files - content within each drive
- Pages - site pages (optional)
- Lists/ListItems - non-document-library lists

Access graph generation:
- Extracts permissions from drive items via Graph API
- Expands Entra ID groups via /groups/{id}/members
- Maps to canonical principal format: user:{email}, group:entra:{id}

Incremental sync:
- Uses Graph delta queries (/drives/{id}/root/delta)
- Per-drive delta tokens stored in cursor
"""

import asyncio
from dataclasses import dataclass
from typing import Any, AsyncGenerator, Dict, List, Optional
from urllib.parse import urlparse

from airweave.platform.access_control.schemas import MembershipTuple
from airweave.platform.configs.config import SharePointOnlineConfig
from airweave.platform.cursors.sharepoint_online import SharePointOnlineCursor
from airweave.platform.decorators import source
from airweave.platform.entities._base import BaseEntity, Breadcrumb
from airweave.platform.entities.sharepoint_online import (
    SharePointOnlineFileDeletionEntity,
)
from airweave.platform.sources._base import BaseSource
from airweave.platform.sources.sharepoint_online.builders import (
    build_drive_entity,
    build_file_entity,
    build_page_entity,
    build_site_entity,
)
from airweave.platform.sources.sharepoint_online.client import GraphClient
from airweave.platform.sources.sharepoint_online.graph_groups import EntraGroupExpander
from airweave.platform.storage import FileSkippedException
from airweave.platform.sync.exceptions import EntityProcessingError
from airweave.schemas.source_connection import AuthenticationMethod, OAuthType

MAX_CONCURRENT_FILE_DOWNLOADS = 10
ITEM_BATCH_SIZE = 50


@dataclass
class PendingFileDownload:
    """Holds a file entity that needs its content downloaded."""

    entity: Any
    drive_id: str
    item_id: str


@source(
    name="SharePoint Online",
    short_name="sharepoint_online",
    auth_methods=[
        AuthenticationMethod.OAUTH_BROWSER,
        AuthenticationMethod.OAUTH_TOKEN,
        AuthenticationMethod.AUTH_PROVIDER,
    ],
    oauth_type=OAuthType.WITH_ROTATING_REFRESH,
    auth_config_class=None,
    config_class=SharePointOnlineConfig,
    supports_continuous=True,
    cursor_class=SharePointOnlineCursor,
    supports_access_control=True,
    labels=["Collaboration", "File Storage"],
)
class SharePointOnlineSource(BaseSource):
    """SharePoint Online source using Microsoft Graph API.

    Syncs sites, drives, files, lists, and pages with full ACL support.
    Uses Entra ID for group membership expansion.
    """

    @classmethod
    async def create(
        cls,
        access_token: Optional[str] = None,
        credentials: Optional[Dict[str, Any]] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> "SharePointOnlineSource":
        """Create and configure a SharePoint Online source instance."""
        instance = cls()

        if isinstance(credentials, dict):
            instance.access_token = credentials.get("access_token") or access_token
        else:
            instance.access_token = access_token

        config = config or {}
        instance._site_url = config.get("site_url", "").rstrip("/")
        instance._include_personal_sites = config.get("include_personal_sites", False)
        instance._include_pages = config.get("include_pages", True)

        instance._item_level_entra_groups: set = set()

        return instance

    def _create_graph_client(self) -> GraphClient:
        return GraphClient(
            access_token_provider=self.get_access_token,
            logger=self.logger,
        )

    def _create_group_expander(self) -> EntraGroupExpander:
        return EntraGroupExpander(
            access_token_provider=self.get_access_token,
            logger=self.logger,
        )

    def _track_entity_entra_groups(self, entity: BaseEntity) -> None:
        """Track Entra ID groups found in entity permissions."""
        if not hasattr(entity, "access") or entity.access is None:
            return
        for viewer in entity.access.viewers or []:
            if viewer.startswith("group:entra:"):
                group_id = viewer[len("group:") :]
                self._item_level_entra_groups.add(group_id)

    # -- File Download --

    async def _download_and_save_file(self, entity, client, drive_id: str, item_id: str):
        """Download file content and save via file_downloader."""
        graph_client = self._create_graph_client()
        try:
            download_url = await graph_client.get_file_content_url(
                client,
                drive_id,
                item_id,
            )
            if download_url:
                entity.url = download_url
            elif not entity.url or "graph.microsoft.com" not in entity.url:
                entity.url = (
                    f"https://graph.microsoft.com/v1.0/drives/{drive_id}/items/{item_id}/content"
                )
            await self.file_downloader.download_from_url(
                entity=entity,
                http_client_factory=self.http_client,
                access_token_provider=self.get_access_token,
                logger=self.logger,
            )
            return entity
        except FileSkippedException:
            raise
        except Exception as e:
            self.logger.error(f"Failed to download file {entity.file_name}: {e}")
            raise EntityProcessingError(f"Failed to download file {entity.file_name}: {e}") from e

    async def _download_files_parallel(
        self, pending: List[PendingFileDownload], client
    ) -> List[BaseEntity]:
        semaphore = asyncio.Semaphore(MAX_CONCURRENT_FILE_DOWNLOADS)
        results: List[BaseEntity] = []

        async def download_one(item: PendingFileDownload):
            async with semaphore:
                try:
                    entity = await self._download_and_save_file(
                        item.entity,
                        client,
                        item.drive_id,
                        item.item_id,
                    )
                    results.append(entity)
                except FileSkippedException:
                    pass
                except EntityProcessingError as e:
                    self.logger.warning(f"Skipping file download: {e}")

        tasks = [asyncio.create_task(download_one(p)) for p in pending]
        await asyncio.gather(*tasks, return_exceptions=True)
        return results

    # -- Sync Decision --

    def _should_do_full_sync(self) -> tuple:
        cursor_data = self.cursor.data if self.cursor else {}
        if not cursor_data:
            return True, "no cursor data (first sync)"

        schema = SharePointOnlineCursor(**cursor_data)
        if schema.needs_full_sync():
            return True, "full_sync_required flag set or no delta tokens"

        if schema.needs_periodic_full_sync():
            return True, "periodic full sync needed (>7 days since last)"

        return False, "incremental sync (valid delta tokens)"

    # -- Entity Generation --

    async def generate_entities(self) -> AsyncGenerator[BaseEntity, None]:
        """Generate all SharePoint entities using full or incremental sync."""
        is_full, reason = self._should_do_full_sync()
        self.logger.info(f"Sync strategy: {'FULL' if is_full else 'INCREMENTAL'} ({reason})")

        if is_full:
            async for entity in self._full_sync():
                yield entity
        else:
            async for entity in self._incremental_sync():
                yield entity

    async def _discover_sites(self, client, graph_client: GraphClient) -> List[Dict[str, Any]]:
        """Discover sites to sync based on config."""
        sites = []

        if self._site_url:
            parsed = urlparse(self._site_url)
            hostname = parsed.netloc
            site_path = parsed.path.lstrip("/")
            try:
                site = await graph_client.get_site_by_url(client, hostname, site_path)
                sites.append(site)
            except Exception as e:
                self.logger.error(f"Could not resolve site URL {self._site_url}: {e}")
                raise
        else:
            async for site in graph_client.search_sites(client, "*"):
                if not self._include_personal_sites and site.get("isPersonalSite", False):
                    continue
                sites.append(site)

        self.logger.info(f"Discovered {len(sites)} sites to sync")
        return sites

    async def _full_sync(self) -> AsyncGenerator[BaseEntity, None]:  # noqa: C901
        entity_count = 0

        async with self.http_client() as client:
            graph_client = self._create_graph_client()

            sites = await self._discover_sites(client, graph_client)

            for site_data in sites:
                site_id = site_data.get("id", "")

                try:
                    site_entity = await build_site_entity(site_data, [])
                    yield site_entity
                    entity_count += 1

                    site_breadcrumb = Breadcrumb(
                        entity_id=site_entity.site_id,
                        name=site_entity.display_name,
                        entity_type="SharePointOnlineSiteEntity",
                    )
                    site_breadcrumbs = [site_breadcrumb]
                except EntityProcessingError as e:
                    self.logger.warning(f"Skipping site {site_id}: {e}")
                    continue

                async for drive_data in graph_client.get_drives(client, site_id):
                    drive_id = drive_data.get("id", "")
                    try:
                        drive_entity = await build_drive_entity(
                            drive_data, site_id, site_breadcrumbs
                        )
                        yield drive_entity
                        entity_count += 1

                        drive_breadcrumb = Breadcrumb(
                            entity_id=drive_entity.drive_id,
                            name=drive_entity.name,
                            entity_type="SharePointOnlineDriveEntity",
                        )
                        drive_breadcrumbs = site_breadcrumbs + [drive_breadcrumb]

                        pending_files: List[PendingFileDownload] = []

                        async for item_data in graph_client.get_drive_items_recursive(
                            client, drive_id
                        ):
                            if item_data.get("folder"):
                                continue

                            if item_data.get("file"):
                                try:
                                    permissions = await graph_client.get_item_permissions(
                                        client,
                                        drive_id,
                                        item_data["id"],
                                    )

                                    file_entity = await build_file_entity(
                                        item_data,
                                        drive_id,
                                        site_id,
                                        drive_breadcrumbs,
                                        permissions,
                                    )
                                    self._track_entity_entra_groups(file_entity)
                                    pending_files.append(
                                        PendingFileDownload(
                                            entity=file_entity,
                                            drive_id=drive_id,
                                            item_id=item_data["id"],
                                        )
                                    )

                                    if len(pending_files) >= ITEM_BATCH_SIZE:
                                        downloaded = await self._download_files_parallel(
                                            pending_files, client
                                        )
                                        for ent in downloaded:
                                            yield ent
                                            entity_count += 1
                                        pending_files = []

                                except EntityProcessingError as e:
                                    self.logger.warning(f"Skipping file: {e}")

                        if pending_files:
                            downloaded = await self._download_files_parallel(pending_files, client)
                            for ent in downloaded:
                                yield ent
                                entity_count += 1

                        if self.cursor:
                            try:
                                _, delta_token = await graph_client.get_drive_delta(
                                    client, drive_id
                                )
                                if delta_token:
                                    cursor_schema = SharePointOnlineCursor(**self.cursor.data)
                                    cursor_schema.update_entity_cursor(
                                        drive_id=drive_id,
                                        delta_token=delta_token,
                                        changes_count=entity_count,
                                        is_full_sync=True,
                                    )
                                    self.cursor.update(**cursor_schema.model_dump())
                            except Exception as e:
                                self.logger.warning(
                                    f"Could not get delta token for drive {drive_id}: {e}"
                                )

                    except EntityProcessingError as e:
                        self.logger.warning(f"Skipping drive {drive_id}: {e}")
                        continue

                if self._include_pages:
                    try:
                        async for page_data in graph_client.get_pages(client, site_id):
                            try:
                                page_entity = await build_page_entity(
                                    page_data, site_id, site_breadcrumbs
                                )
                                yield page_entity
                                entity_count += 1
                            except EntityProcessingError as e:
                                self.logger.warning(f"Skipping page: {e}")
                    except Exception as e:
                        self.logger.debug(f"Pages not available for site {site_id}: {e}")

                if self.cursor:
                    cursor_data = self.cursor.data
                    synced_sites = cursor_data.get("synced_site_ids", {})
                    synced_sites[site_id] = site_data.get("displayName", "")
                    self.cursor.update(synced_site_ids=synced_sites)

            if self.cursor:
                self.cursor.update(
                    full_sync_required=False,
                    total_entities_synced=entity_count,
                )

            self.logger.info(f"Full sync complete: {entity_count} entities")

    async def _incremental_sync(self) -> AsyncGenerator[BaseEntity, None]:  # noqa: C901
        cursor_data = self.cursor.data if self.cursor else {}
        schema = SharePointOnlineCursor(**cursor_data)
        delta_tokens = schema.drive_delta_tokens

        if not delta_tokens:
            self.logger.warning("No delta tokens for incremental sync, falling back to full")
            async for entity in self._full_sync():
                yield entity
            return

        changes_processed = 0

        async with self.http_client() as client:
            graph_client = self._create_graph_client()

            for drive_id, token in delta_tokens.items():
                try:
                    changed_items, new_token = await graph_client.get_drive_delta(
                        client, drive_id, token
                    )
                except Exception as e:
                    self.logger.error(f"Delta query failed for drive {drive_id}: {e}")
                    if self.cursor:
                        self.cursor.update(full_sync_required=True)
                    return

                self.logger.info(f"Drive {drive_id}: {len(changed_items)} changes")

                for item_data in changed_items:
                    item_id = item_data.get("id", "")

                    if item_data.get("deleted"):
                        spo_entity_id = f"spo:file:{drive_id}:{item_id}"
                        yield SharePointOnlineFileDeletionEntity(
                            drive_id=drive_id,
                            item_id=item_id,
                            spo_entity_id=spo_entity_id,
                            label=f"Deleted item {item_id} from drive {drive_id}",
                            deletion_status="removed",
                            breadcrumbs=[],
                        )
                        changes_processed += 1
                        continue

                    if item_data.get("folder"):
                        continue

                    if item_data.get("file"):
                        try:
                            file_entity = await build_file_entity(
                                item_data,
                                drive_id,
                                "",
                                [],
                            )
                            self._track_entity_entra_groups(file_entity)
                            file_entity = await self._download_and_save_file(
                                file_entity,
                                client,
                                drive_id,
                                item_id,
                            )
                            yield file_entity
                            changes_processed += 1
                        except (FileSkippedException, EntityProcessingError) as e:
                            self.logger.warning(f"Skipping changed file: {e}")

                if self.cursor and new_token:
                    cursor_schema = SharePointOnlineCursor(**self.cursor.data)
                    cursor_schema.update_entity_cursor(
                        drive_id=drive_id,
                        delta_token=new_token,
                        changes_count=changes_processed,
                    )
                    self.cursor.update(**cursor_schema.model_dump())

        self.logger.info(f"Incremental sync complete: {changes_processed} changes processed")

    # -- Validation --

    async def validate(self) -> bool:
        """Validate the SharePoint Online connection by pinging the root site."""
        try:
            return await self._validate_oauth2(
                ping_url="https://graph.microsoft.com/v1.0/sites/root",
                headers={"Accept": "application/json"},
            )
        except Exception as e:
            self.logger.error(f"Validation failed: {e}")
            return False

    # -- Access Control Memberships --

    async def generate_access_control_memberships(
        self,
    ) -> AsyncGenerator[MembershipTuple, None]:
        """Expand Entra ID groups found in item permissions into user memberships."""
        self.logger.info("Starting access control membership extraction")
        membership_count = 0

        group_expander = self._create_group_expander()

        async with self.http_client() as client:
            entra_group_ids = list(self._item_level_entra_groups)
            self.logger.info(f"Expanding {len(entra_group_ids)} Entra ID groups")

            for group_ref in entra_group_ids:
                if ":" in group_ref:
                    group_id = group_ref.split(":", 1)[1]
                else:
                    group_id = group_ref

                async for membership in group_expander.expand_group(client, group_id):
                    yield membership
                    membership_count += 1

        group_expander.log_stats()
        self.logger.info(f"Access control extraction complete: {membership_count} memberships")

        if self.cursor:
            self.cursor.update(total_acl_memberships=membership_count)
