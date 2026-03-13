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
- Expands SP site groups via SharePoint REST API (requires SP-scoped token)
- Maps to canonical principal format: user:{email}, group:entra:{id}, group:sp:{name}

Incremental sync:
- Uses Graph delta queries (/drives/{id}/root/delta)
- Per-drive delta tokens stored in cursor
"""

import asyncio
from dataclasses import dataclass
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional
from urllib.parse import urlparse

import httpx

from airweave.domains.access_control.schemas import MembershipTuple
from airweave.domains.browse_tree.types import BrowseNode, NodeSelectionData
from airweave.domains.sync_pipeline.exceptions import EntityProcessingError
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
from airweave.domains.storage import FileSkippedException
from airweave.domains.sync_pipeline.exceptions import EntityProcessingError
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
    supports_browse_tree=True,
    feature_flag="sharepoint_2019_v2",
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
        instance._item_level_sp_groups: set = set()

        instance._node_selections: Optional[List[NodeSelectionData]] = None

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

    def _derive_sp_resource_scope(self) -> Optional[str]:
        """Derive the SharePoint resource scope from the site URL.

        E.g. https://neenacorp.sharepoint.com/sites/JAman
             -> https://neenacorp.sharepoint.com/.default
        """
        if not self._site_url:
            return None
        parsed = urlparse(self._site_url)
        if not parsed.netloc:
            return None
        return f"https://{parsed.netloc}/.default"

    def _make_sp_token_provider(self) -> Optional[Callable]:
        """Create an async callable that returns a SharePoint-scoped token.

        Returns None if the site URL is not set or no token manager is available.
        """
        sp_scope = self._derive_sp_resource_scope()
        if not sp_scope:
            return None

        async def _provider() -> str:
            token = await self.get_token_for_resource(sp_scope)
            if not token:
                raise RuntimeError(f"Could not obtain SharePoint token for scope {sp_scope}")
            return token

        return _provider

    def _track_entity_groups(self, entity: BaseEntity) -> None:
        """Track Entra ID and SP site groups found in entity permissions."""
        if not hasattr(entity, "access") or entity.access is None:
            return
        for viewer in entity.access.viewers or []:
            if viewer.startswith("group:entra:"):
                group_id = viewer[len("group:") :]
                self._item_level_entra_groups.add(group_id)
            elif viewer.startswith("group:sp:"):
                self._item_level_sp_groups.add(viewer[len("group:") :])

    # -- Browse Tree --

    def set_node_selections(self, selections: List[NodeSelectionData]) -> None:
        """Set node selections for targeted sync."""
        self._node_selections = selections

    BROWSE_TREE_MAX_ITEMS = 500

    def parse_browse_node_id(self, node_id: str) -> tuple:
        """Parse an encoded browse node ID into (node_type, metadata_dict).

        Encoding conventions (defined by get_browse_children):
        - "site:{site_id}"
        - "drive:{site_id}|{drive_id}"
        - "folder:{drive_id}|{folder_id}"
        """
        if ":" not in node_id:
            return "unknown", {"raw_id": node_id}

        prefix, _, payload = node_id.partition(":")
        if prefix == "site":
            return "site", {"site_id": payload}
        elif prefix == "drive":
            parts = payload.split("|", 1)
            return "drive", {
                "site_id": parts[0],
                "drive_id": parts[1] if len(parts) > 1 else "",
            }
        elif prefix == "folder":
            parts = payload.split("|", 1)
            return "folder", {
                "drive_id": parts[0],
                "folder_id": parts[1] if len(parts) > 1 else "",
            }
        else:
            return prefix, {"raw_id": node_id}

    async def get_browse_children(
        self,
        parent_node_id: Optional[str] = None,
    ) -> List[BrowseNode]:
        """Lazy-load tree nodes from Microsoft Graph API.

        Tree structure:
        - Root (parent_node_id=None): returns discovered sites
        - Site node (site:{site_id}): returns drives for the site
        - Drive node (drive:{site_id}|{drive_id}): returns root children of the drive
        - Folder node (folder:{drive_id}|{folder_id}): returns children of the folder

        Args:
            parent_node_id: Encoded node ID. None = root level.

        Returns:
            List of BrowseNode objects.
        """
        graph_client = self._create_graph_client()
        nodes: List[BrowseNode] = []

        async with self.http_client() as client:
            if parent_node_id is None:
                sites = await self._discover_sites(client, graph_client)
                for site in sites:
                    site_id = site.get("id", "")
                    nodes.append(
                        BrowseNode(
                            source_node_id=f"site:{site_id}",
                            node_type="site",
                            title=site.get("displayName", site_id),
                            description=site.get("description"),
                            has_children=True,
                            node_metadata={
                                "site_id": site_id,
                                "web_url": site.get("webUrl", ""),
                            },
                        )
                    )

            elif parent_node_id.startswith("site:"):
                site_id = parent_node_id[5:]

                async for drive in graph_client.get_drives(client, site_id):
                    drive_id = drive.get("id", "")
                    nodes.append(
                        BrowseNode(
                            source_node_id=f"drive:{site_id}|{drive_id}",
                            node_type="drive",
                            title=drive.get("name", drive_id),
                            description=drive.get("description"),
                            has_children=True,
                            node_metadata={
                                "site_id": site_id,
                                "drive_id": drive_id,
                                "drive_type": drive.get("driveType", ""),
                            },
                        )
                    )

            elif parent_node_id.startswith("drive:"):
                payload = parent_node_id[6:]
                if "|" not in payload:
                    raise ValueError(
                        f"Malformed drive node ID: expected 'drive:{{site_id}}|{{drive_id}}', "
                        f"got '{parent_node_id}'"
                    )
                _site_id, drive_id = payload.split("|", 1)
                await self._browse_drive_children(client, graph_client, drive_id, "root", nodes)

            elif parent_node_id.startswith("folder:"):
                payload = parent_node_id[7:]
                if "|" not in payload:
                    raise ValueError(
                        f"Malformed folder node ID: expected 'folder:{{drive_id}}|{{folder_id}}', "
                        f"got '{parent_node_id}'"
                    )
                drive_id, folder_id = payload.split("|", 1)
                await self._browse_drive_children(client, graph_client, drive_id, folder_id, nodes)

            else:
                raise ValueError(
                    f"Unrecognized browse node ID prefix: '{parent_node_id}'. "
                    f"Expected 'site:', 'drive:', or 'folder:'."
                )

        return nodes

    async def _browse_drive_children(
        self,
        client,
        graph_client: GraphClient,
        drive_id: str,
        folder_id: str,
        nodes: List[BrowseNode],
    ) -> None:
        """Populate nodes list with immediate children of a drive folder."""
        count = 0
        async for item in graph_client.get_drive_children(client, drive_id, folder_id):
            if count >= self.BROWSE_TREE_MAX_ITEMS:
                break

            item_id = item.get("id", "")
            name = item.get("name", "")

            if item.get("folder"):
                child_count = item["folder"].get("childCount", 0)
                nodes.append(
                    BrowseNode(
                        source_node_id=f"folder:{drive_id}|{item_id}",
                        node_type="folder",
                        title=name,
                        item_count=child_count,
                        has_children=child_count > 0,
                        node_metadata={
                            "drive_id": drive_id,
                            "folder_id": item_id,
                        },
                    )
                )
            elif item.get("file"):
                nodes.append(
                    BrowseNode(
                        source_node_id=f"file:{drive_id}|{item_id}",
                        node_type="file",
                        title=name,
                        has_children=False,
                        node_metadata={
                            "drive_id": drive_id,
                            "item_id": item_id,
                            "mime_type": item.get("file", {}).get("mimeType", ""),
                            "size": item.get("size", 0),
                        },
                    )
                )

            count += 1

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
                    self.logger.debug(f"File download skipped for {item.drive_id}/{item.item_id}")
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
        """Generate all SharePoint entities using full, incremental, or targeted sync."""
        cursor_data = self.cursor.data if self.cursor else {}
        for g in cursor_data.get("tracked_entra_groups", []):
            self._item_level_entra_groups.add(g)
        for g in cursor_data.get("tracked_sp_groups", []):
            self._item_level_sp_groups.add(g)

        if self._node_selections:
            self.logger.info(
                f"Sync strategy: TARGETED ({len(self._node_selections)} node selections)"
            )
            async for entity in self._targeted_sync():
                yield entity
            return

        is_full, reason = self._should_do_full_sync()
        self.logger.info(f"Sync strategy: {'FULL' if is_full else 'INCREMENTAL'} ({reason})")

        if is_full:
            async for entity in self._full_sync():
                yield entity
        else:
            async for entity in self._incremental_sync():
                yield entity

    async def _discover_sites(self, client, graph_client: GraphClient) -> List[Dict[str, Any]]:
        """Discover sites to sync based on config.

        Supports:
          - Single URL: "https://tenant.sharepoint.com/sites/MySite"
          - Comma-separated: "https://tenant.sharepoint.com/sites/A, .../sites/B"
          - Empty string: discover all accessible sites
        """
        sites = []

        if self._site_url:
            urls = [u.strip() for u in self._site_url.split(",") if u.strip()]
            for url in urls:
                parsed = urlparse(url)
                hostname = parsed.netloc
                site_path = parsed.path.lstrip("/")
                try:
                    site = await graph_client.get_site_by_url(client, hostname, site_path)
                    sites.append(site)
                except Exception as e:
                    self.logger.error(f"Could not resolve site URL {url}: {e}")
                    raise
        else:
            async for site in graph_client.search_sites(client, "*"):
                if not self._include_personal_sites and site.get("isPersonalSite", False):
                    continue
                sites.append(site)

        self.logger.info(f"Discovered {len(sites)} sites to sync")
        return sites

    async def _resolve_unresolved_viewers(
        self, entity: BaseEntity, client, graph_client: "GraphClient"
    ) -> None:
        """Resolve any user:id:{uuid} viewers to user:{email}."""
        if not hasattr(entity, "access") or entity.access is None:
            return
        viewers = entity.access.viewers or []
        unresolved = [v for v in viewers if v.startswith("user:id:")]
        if not unresolved:
            return
        user_ids = [v[len("user:id:") :] for v in unresolved]
        resolved = await graph_client.resolve_user_ids(client, user_ids)
        new_viewers = []
        for v in viewers:
            if v.startswith("user:id:"):
                uid = v[len("user:id:") :]
                email = resolved.get(uid)
                if email:
                    new_viewers.append(f"user:{email}")
                    continue
                self.logger.warning(f"Dropping unresolvable user viewer: {v}")
            else:
                new_viewers.append(v)
        entity.access.viewers = new_viewers

    async def _fetch_sp_group_viewers(self) -> List[str]:
        """Fetch all SP site groups and return their viewer strings.

        Uses a dedicated httpx client with the SP-scoped token.
        Returns empty list if SP token is unavailable.
        """
        sp_token_provider = self._make_sp_token_provider()
        if not sp_token_provider or not self._site_url:
            return []
        try:
            token = await sp_token_provider()
            headers = {
                "Authorization": f"Bearer {token}",
                "Accept": "application/json;odata=verbose",
            }
            async with httpx.AsyncClient() as sp_client:
                resp = await sp_client.get(
                    f"{self._site_url}/_api/web/sitegroups",
                    headers=headers,
                    timeout=30.0,
                )
                resp.raise_for_status()
                groups = resp.json().get("d", {}).get("results", [])

            viewers = []
            for g in groups:
                title = g.get("Title", "")
                if title:
                    tag = f"group:sp:{title.lower().replace(' ', '_')}"
                    viewers.append(tag)
                    self._item_level_sp_groups.add(tag[len("group:") :])
            self.logger.info(f"Fetched {len(viewers)} SP site groups as viewers")
            return viewers
        except Exception as e:
            self.logger.warning(f"SP group fetch failed: {e}")
            return []

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

                sp_group_viewers = await self._fetch_sp_group_viewers()

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

                                    await self._resolve_unresolved_viewers(
                                        file_entity, client, graph_client
                                    )
                                    if sp_group_viewers and file_entity.access:
                                        existing = set(file_entity.access.viewers or [])
                                        for spv in sp_group_viewers:
                                            if spv not in existing:
                                                file_entity.access.viewers.append(spv)
                                    self._track_entity_groups(file_entity)
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
                    tracked_entra_groups=list(self._item_level_entra_groups),
                    tracked_sp_groups=list(self._item_level_sp_groups),
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
                            permissions = await graph_client.get_item_permissions(
                                client, drive_id, item_id
                            )
                            file_entity = await build_file_entity(
                                item_data,
                                drive_id,
                                "",
                                [],
                                permissions,
                            )
                            await self._resolve_unresolved_viewers(
                                file_entity, client, graph_client
                            )
                            self._track_entity_groups(file_entity)
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

    # -- Targeted Sync --

    async def _targeted_sync(self) -> AsyncGenerator[BaseEntity, None]:  # noqa: C901
        """Sync only the nodes specified in node_selections.

        Each selection has node_type and node_metadata with enough info
        to do targeted Graph API calls (site_id, drive_id, folder_id).
        """
        entity_count = 0
        selections = self._node_selections or []

        site_ids: set = set()
        drive_selections: List[NodeSelectionData] = []

        for sel in selections:
            if sel.node_type == "site":
                site_ids.add(sel.node_metadata.get("site_id", "") if sel.node_metadata else "")
            elif sel.node_type in ("drive", "folder", "file"):
                drive_selections.append(sel)
                if sel.node_metadata and sel.node_metadata.get("site_id"):
                    site_ids.add(sel.node_metadata["site_id"])

        async with self.http_client() as client:
            graph_client = self._create_graph_client()

            # Phase 1: For selected sites (without specific drives), sync all drives
            for site_id in site_ids:
                if not site_id:
                    continue

                has_specific_drives = any(
                    s.node_metadata
                    and s.node_metadata.get("site_id") == site_id
                    and s.node_type in ("drive", "folder", "file")
                    for s in drive_selections
                )
                if has_specific_drives:
                    continue

                try:
                    site_data = await graph_client.get_site(client, site_id)
                    site_entity = await build_site_entity(site_data, [])
                    yield site_entity
                    entity_count += 1
                except Exception as e:
                    self.logger.warning(f"Targeted sync: skipping site {site_id}: {e}")
                    continue

                site_breadcrumbs = [
                    Breadcrumb(
                        entity_id=site_entity.site_id,
                        name=site_entity.display_name,
                        entity_type="SharePointOnlineSiteEntity",
                    )
                ]

                async for drive_data in graph_client.get_drives(client, site_id):
                    drive_id = drive_data.get("id", "")
                    async for ent in self._sync_drive(
                        client, graph_client, drive_id, site_id, site_breadcrumbs
                    ):
                        yield ent
                        entity_count += 1

            # Phase 2: Sync specifically selected drives/folders
            for sel in drive_selections:
                meta = sel.node_metadata or {}

                if sel.node_type == "drive":
                    drive_id = meta.get("drive_id", "")
                    sel_site_id = meta.get("site_id", "")
                    if not drive_id:
                        continue
                    async for ent in self._sync_drive(
                        client, graph_client, drive_id, sel_site_id, []
                    ):
                        yield ent
                        entity_count += 1

                elif sel.node_type == "folder":
                    drive_id = meta.get("drive_id", "")
                    folder_id = meta.get("folder_id", "")
                    if not drive_id or not folder_id:
                        continue
                    async for ent in self._sync_folder_recursive(
                        client, graph_client, drive_id, folder_id, ""
                    ):
                        yield ent
                        entity_count += 1

                elif sel.node_type == "file":
                    drive_id = meta.get("drive_id", "")
                    item_id = meta.get("item_id", "")
                    if not drive_id or not item_id:
                        continue
                    try:
                        url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/items/{item_id}"
                        item_data = await graph_client.get(client, url)
                        if item_data.get("file"):
                            permissions = await graph_client.get_item_permissions(
                                client, drive_id, item_id
                            )
                            file_entity = await build_file_entity(
                                item_data, drive_id, "", [], permissions
                            )
                            await self._resolve_unresolved_viewers(
                                file_entity, client, graph_client
                            )
                            self._track_entity_groups(file_entity)
                            file_entity = await self._download_and_save_file(
                                file_entity, client, drive_id, item_id
                            )
                            yield file_entity
                            entity_count += 1
                    except Exception as e:
                        self.logger.warning(f"Targeted sync: skipping file {item_id}: {e}")

        self.logger.info(f"Targeted sync complete: {entity_count} entities")

    async def _sync_drive(
        self,
        client,
        graph_client: GraphClient,
        drive_id: str,
        site_id: str,
        site_breadcrumbs: List[Breadcrumb],
    ) -> AsyncGenerator[BaseEntity, None]:
        """Sync all files in a single drive (used by both full and targeted sync)."""
        try:
            drive_data = await graph_client.get_drive(client, drive_id)
            drive_entity = await build_drive_entity(drive_data, site_id, site_breadcrumbs)
            yield drive_entity

            drive_breadcrumbs = site_breadcrumbs + [
                Breadcrumb(
                    entity_id=drive_entity.drive_id,
                    name=drive_entity.name,
                    entity_type="SharePointOnlineDriveEntity",
                )
            ]

            pending_files: List[PendingFileDownload] = []

            async for item_data in graph_client.get_drive_items_recursive(client, drive_id):
                if item_data.get("folder"):
                    continue
                if item_data.get("file"):
                    try:
                        permissions = await graph_client.get_item_permissions(
                            client, drive_id, item_data["id"]
                        )
                        file_entity = await build_file_entity(
                            item_data, drive_id, site_id, drive_breadcrumbs, permissions
                        )
                        self._track_entity_groups(file_entity)
                        pending_files.append(
                            PendingFileDownload(
                                entity=file_entity,
                                drive_id=drive_id,
                                item_id=item_data["id"],
                            )
                        )

                        if len(pending_files) >= ITEM_BATCH_SIZE:
                            downloaded = await self._download_files_parallel(pending_files, client)
                            for ent in downloaded:
                                yield ent
                            pending_files = []
                    except EntityProcessingError as e:
                        self.logger.warning(f"Skipping file: {e}")

            if pending_files:
                downloaded = await self._download_files_parallel(pending_files, client)
                for ent in downloaded:
                    yield ent
        except EntityProcessingError as e:
            self.logger.warning(f"Skipping drive {drive_id}: {e}")

    async def _sync_folder_recursive(
        self,
        client,
        graph_client: GraphClient,
        drive_id: str,
        folder_id: str,
        site_id: str,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Recursively sync all files under a specific folder."""
        pending_files: List[PendingFileDownload] = []

        async for item_data in graph_client.get_drive_items_recursive(client, drive_id, folder_id):
            if item_data.get("folder"):
                continue
            if item_data.get("file"):
                try:
                    permissions = await graph_client.get_item_permissions(
                        client, drive_id, item_data["id"]
                    )
                    file_entity = await build_file_entity(
                        item_data, drive_id, site_id, [], permissions
                    )
                    await self._resolve_unresolved_viewers(file_entity, client, graph_client)
                    self._track_entity_groups(file_entity)
                    pending_files.append(
                        PendingFileDownload(
                            entity=file_entity,
                            drive_id=drive_id,
                            item_id=item_data["id"],
                        )
                    )

                    if len(pending_files) >= ITEM_BATCH_SIZE:
                        downloaded = await self._download_files_parallel(pending_files, client)
                        for ent in downloaded:
                            yield ent
                        pending_files = []
                except EntityProcessingError as e:
                    self.logger.warning(f"Skipping file: {e}")

        if pending_files:
            downloaded = await self._download_files_parallel(pending_files, client)
            for ent in downloaded:
                yield ent

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

    async def _expand_entra_groups(
        self, client, group_expander: EntraGroupExpander
    ) -> AsyncGenerator[MembershipTuple, None]:
        """Expand tracked Entra ID groups into user memberships."""
        entra_group_ids = list(self._item_level_entra_groups)
        self.logger.info(f"Expanding {len(entra_group_ids)} Entra ID groups")
        for group_ref in entra_group_ids:
            group_id = group_ref.split(":", 1)[1] if ":" in group_ref else group_ref
            async for membership in group_expander.expand_group(client, group_id):
                yield membership

    async def _expand_sp_site_groups(self) -> AsyncGenerator[MembershipTuple, None]:
        """Expand tracked SP site groups into user memberships.

        Uses a dedicated httpx client with SP-scoped token (the Airweave
        HTTP client only handles Graph API requests).
        """
        sp_group_names = list(self._item_level_sp_groups)
        if not sp_group_names or not self._site_url:
            return
        sp_token_provider = self._make_sp_token_provider()
        if not sp_token_provider:
            self.logger.warning("No SP token provider for site group expansion")
            return

        self.logger.info(f"Expanding {len(sp_group_names)} SP site groups")
        graph_client = self._create_graph_client()

        async with httpx.AsyncClient() as sp_client:
            sp_groups = await graph_client.get_site_groups(
                sp_client,
                self._site_url,
                sp_token_provider=sp_token_provider,
            )
            sp_name_to_id = {
                f"sp:{g['Title'].replace(' ', '_').lower()}": g.get("Id")
                for g in sp_groups
                if g.get("Title")
            }

            for sp_name in sp_group_names:
                sp_id = sp_name_to_id.get(sp_name)
                if not sp_id:
                    self.logger.debug(f"SP group '{sp_name}' not found in site")
                    continue

                users = await graph_client.get_site_group_users(
                    sp_client,
                    self._site_url,
                    sp_id,
                    sp_token_provider=sp_token_provider,
                )
                for user in users:
                    email = user.get("Email", "")
                    login = user.get("LoginName", "")
                    if not email and login and "|" in login:
                        email = login.split("|")[-1]
                    if email:
                        yield MembershipTuple(
                            member_id=email.lower(),
                            member_type="user",
                            group_id=sp_name,
                            group_name=user.get("Title", sp_name),
                        )

    async def generate_access_control_memberships(
        self,
    ) -> AsyncGenerator[MembershipTuple, None]:
        """Expand Entra ID groups and SP site groups into user memberships."""
        self.logger.info("Starting access control membership extraction")
        membership_count = 0
        group_expander = self._create_group_expander()

        async with self.http_client() as client:
            async for m in self._expand_entra_groups(client, group_expander):
                yield m
                membership_count += 1

        try:
            async for m in self._expand_sp_site_groups():
                yield m
                membership_count += 1
        except Exception as e:
            self.logger.warning(f"SP site group expansion failed: {e}")

        group_expander.log_stats()
        self.logger.info(f"Access control extraction complete: {membership_count} memberships")

        if self.cursor:
            self.cursor.update(total_acl_memberships=membership_count)
