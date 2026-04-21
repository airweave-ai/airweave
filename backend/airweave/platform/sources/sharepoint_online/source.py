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

Two source variants:
- SharePointOnlineSource: OAuth (delegated user auth)
- SharePointOnlineAppSource: Client credentials (app-only auth)
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, AsyncGenerator, Callable, Dict, List, Optional
from urllib.parse import urlparse

import httpx
from tenacity import retry, stop_after_attempt

from airweave.core.logging import ContextualLogger
from airweave.domains.access_control.schemas import MembershipTuple
from airweave.domains.browse_tree.types import BrowseNode, NodeSelectionData
from airweave.domains.sources.exceptions import SourceAuthError
from airweave.domains.sources.token_providers.credential import DirectCredentialProvider
from airweave.domains.sources.token_providers.protocol import TokenProviderProtocol
from airweave.domains.sources.token_providers.static import StaticTokenProvider
from airweave.domains.storage import FileSkippedException
from airweave.domains.storage.file_service import FileService
from airweave.domains.sync_pipeline.exceptions import EntityProcessingError
from airweave.domains.syncs.cursors.cursor import SyncCursor
from airweave.platform.configs.auth import SharePointOnlineAppAuthConfig
from airweave.platform.configs.config import SharePointOnlineConfig
from airweave.platform.cursors.sharepoint_online import SharePointOnlineCursor
from airweave.platform.decorators import source
from airweave.platform.entities._base import BaseEntity, Breadcrumb
from airweave.platform.entities.sharepoint_online import (
    SharePointOnlineFileDeletionEntity,
)
from airweave.platform.http_client.airweave_client import AirweaveHttpClient
from airweave.platform.sources._base import BaseSource
from airweave.platform.sources.http_helpers import raise_for_status
from airweave.platform.sources.retry_helpers import (
    retry_if_rate_limit_or_timeout,
    wait_rate_limit_with_backoff,
)
from airweave.platform.sources.sharepoint_online.acl import extract_access_control
from airweave.platform.sources.sharepoint_online.builders import (
    build_drive_entity,
    build_file_entity,
    build_page_entity,
    build_site_entity,
)
from airweave.platform.sources.sharepoint_online.client import GRAPH_BASE_URL, GraphClient
from airweave.platform.sources.sharepoint_online.graph_groups import EntraGroupExpander
from airweave.schemas.source_connection import AuthenticationMethod, OAuthType

if TYPE_CHECKING:
    from airweave.domains.sync_pipeline.source_hash_lookup import SourceHashLookup

MAX_CONCURRENT_FILE_DOWNLOADS = 10
ITEM_BATCH_SIZE = 50


@dataclass
class PendingFileDownload:
    """Holds a file entity that needs its content downloaded."""

    entity: Any
    drive_id: str
    item_id: str


# =============================================================================
# Base class — shared sync, browse tree, download, and ACL logic
# =============================================================================


class SharePointOnlineBase(BaseSource):
    """Shared implementation for SharePoint Online sources.

    Subclasses must implement the auth-specific hooks:
    - create() — class constructor
    - _get_access_token() — return a valid Microsoft Graph token
    - _handle_401() — refresh/re-exchange on 401, return new token
    - _make_sp_token_provider() — callable returning SP REST API token
    - _get_download_auth(url) — auth suitable for file download
    - _discover_sites(graph_client) — site discovery strategy
    """

    # Instance attributes set by _init_common()
    _site_url: str
    _include_personal_sites: bool
    _include_pages: bool
    _item_level_entra_groups: set
    _item_level_sp_groups: set

    def _init_common(self, config: SharePointOnlineConfig) -> None:
        """Initialize fields shared by both OAuth and client-credentials sources."""
        self._site_url = config.site_url.rstrip("/") if config.site_url else ""
        self._include_personal_sites = config.include_personal_sites
        self._include_pages = config.include_pages
        self._item_level_entra_groups = set()
        self._item_level_sp_groups = set()

    # -- Auth hooks (subclasses override) --

    async def _get_access_token(self) -> str:
        """Get a valid Microsoft Graph access token."""
        raise NotImplementedError

    async def _handle_401(self) -> str:
        """Handle a 401 by refreshing/re-exchanging. Returns new token."""
        raise NotImplementedError

    def _make_sp_token_provider(self) -> Optional[Callable]:
        """Create an async callable returning a SharePoint REST API token, or None."""
        raise NotImplementedError

    async def _get_download_auth(self, url: str) -> Any:
        """Return an auth object suitable for FileService.download_from_url."""
        return self.auth

    async def _discover_sites(self, graph_client: GraphClient) -> List[Dict[str, Any]]:
        """Discover SharePoint sites to sync."""
        raise NotImplementedError

    @property
    def _delta_prefer_headers(self) -> List[str]:
        """Prefer headers for delta queries (permission change tracking)."""
        return []

    # -- Shared client factories --

    def _create_graph_client(self) -> GraphClient:
        return GraphClient(
            access_token_provider=self._get_access_token,
            http_client=self.http_client,
            logger=self.logger,
        )

    def _create_group_expander(self) -> EntraGroupExpander:
        return EntraGroupExpander(
            access_token_provider=self._get_access_token,
            http_client=self.http_client,
            logger=self.logger,
        )

    @retry(
        stop=stop_after_attempt(5),
        retry=retry_if_rate_limit_or_timeout,
        wait=wait_rate_limit_with_backoff,
        reraise=True,
    )
    async def _get(self, url: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """Make an authenticated GET request to Microsoft Graph API."""
        token = await self._get_access_token()
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
        response = await self.http_client.get(url, headers=headers, params=params)

        if response.status_code == 401:
            self.logger.warning("Received 401 from Microsoft Graph API — refreshing token")
            new_token = await self._handle_401()
            headers = {"Authorization": f"Bearer {new_token}", "Accept": "application/json"}
            response = await self.http_client.get(url, headers=headers, params=params)

        raise_for_status(
            response,
            source_short_name=self.short_name,
            token_provider_kind=self.auth.provider_kind,
        )
        return response.json()

    def _derive_sp_hostname(self) -> Optional[str]:
        """Derive the SharePoint hostname from the site URL."""
        if not self._site_url:
            return None
        parsed = urlparse(self._site_url)
        return parsed.netloc or None

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
        """Lazy-load tree nodes from Microsoft Graph API."""
        graph_client = self._create_graph_client()
        nodes: List[BrowseNode] = []

        if parent_node_id is None:
            sites = await self._discover_sites(graph_client)
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

            async for drive in graph_client.get_drives(site_id):
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
            await self._browse_drive_children(graph_client, drive_id, "root", nodes)

        elif parent_node_id.startswith("folder:"):
            payload = parent_node_id[7:]
            if "|" not in payload:
                raise ValueError(
                    f"Malformed folder node ID: expected 'folder:{{drive_id}}|{{folder_id}}', "
                    f"got '{parent_node_id}'"
                )
            drive_id, folder_id = payload.split("|", 1)
            await self._browse_drive_children(graph_client, drive_id, folder_id, nodes)

        else:
            raise ValueError(
                f"Unrecognized browse node ID prefix: '{parent_node_id}'. "
                f"Expected 'site:', 'drive:', or 'folder:'."
            )

        return nodes

    async def _browse_drive_children(
        self,
        graph_client: GraphClient,
        drive_id: str,
        folder_id: str,
        nodes: List[BrowseNode],
    ) -> None:
        """Populate nodes list with immediate children of a drive folder."""
        count = 0
        async for item in graph_client.get_drive_children(drive_id, folder_id):
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

    async def _download_and_save_file(
        self,
        entity: Any,
        files: FileService,
        drive_id: str,
        item_id: str,
    ) -> Any:
        """Download file content and save via FileService."""
        graph_client = self._create_graph_client()
        try:
            download_url = await graph_client.get_file_content_url(drive_id, item_id)
            if download_url:
                entity.url = download_url
            elif not entity.url or "graph.microsoft.com" not in entity.url:
                entity.url = (
                    f"https://graph.microsoft.com/v1.0/drives/{drive_id}/items/{item_id}/content"
                )

            auth = await self._get_download_auth(entity.url)

            await files.download_from_url(
                entity=entity,
                client=self.http_client,
                auth=auth,
                logger=self.logger,
            )
            return entity
        except FileSkippedException:
            raise
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise
            self.logger.warning(f"Failed to download file {entity.file_name}: {e}")
            raise EntityProcessingError(f"Failed to download file {entity.file_name}: {e}") from e

    async def _download_files_parallel(
        self, pending: List[PendingFileDownload], files: FileService
    ) -> List[BaseEntity]:
        semaphore = asyncio.Semaphore(MAX_CONCURRENT_FILE_DOWNLOADS)
        results: List[BaseEntity] = []
        lookup = getattr(self, "_source_hash_lookup", None)

        async def download_one(item: PendingFileDownload):
            async with semaphore:
                # Skip download if content + metadata unchanged
                if lookup and lookup.should_skip_download(item.entity):
                    self.logger.debug(
                        f"Source-hash match, skipping download: {item.entity.file_name}"
                    )
                    results.append(item.entity)
                    return

                try:
                    entity = await self._download_and_save_file(
                        item.entity,
                        files,
                        item.drive_id,
                        item.item_id,
                    )
                    results.append(entity)
                except FileSkippedException:
                    self.logger.debug(f"File download skipped for {item.drive_id}/{item.item_id}")
                except EntityProcessingError as e:
                    self.logger.warning(f"Skipping file download: {e}")
                except Exception as e:
                    self.logger.warning(f"Unexpected error downloading {item.entity.name}: {e}")

        tasks = [asyncio.create_task(download_one(p)) for p in pending]
        await asyncio.gather(*tasks, return_exceptions=True)
        return results

    # -- Sync Decision --

    def _should_do_full_sync(self, cursor: SyncCursor | None) -> tuple:
        cursor_data = cursor.data if cursor else {}
        if not cursor_data:
            return True, "no cursor data (first sync)"

        schema = SharePointOnlineCursor(**cursor_data)
        if schema.needs_full_sync():
            return True, "full_sync_required flag set or no delta tokens"

        if schema.needs_periodic_full_sync():
            return True, "periodic full sync needed (>7 days since last)"

        return False, "incremental sync (valid delta tokens)"

    # -- Entity Generation --

    async def generate_entities(
        self,
        *,
        cursor: SyncCursor | None = None,
        files: FileService | None = None,
        node_selections: list[NodeSelectionData] | None = None,
        source_hash_lookup: SourceHashLookup | None = None,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate all SharePoint entities using full, incremental, or targeted sync."""
        self._source_hash_lookup = source_hash_lookup
        cursor_data = cursor.data if cursor else {}
        for g in cursor_data.get("tracked_entra_groups", []):
            self._item_level_entra_groups.add(g)
        for g in cursor_data.get("tracked_sp_groups", []):
            self._item_level_sp_groups.add(g)

        if node_selections:
            self.logger.info(f"Sync strategy: TARGETED ({len(node_selections)} node selections)")
            async for entity in self._targeted_sync(cursor, files, node_selections):
                yield entity
            return

        is_full, reason = self._should_do_full_sync(cursor)
        self.logger.info(f"Sync strategy: {'FULL' if is_full else 'INCREMENTAL'} ({reason})")

        if is_full:
            async for entity in self._full_sync(cursor, files):
                yield entity
        else:
            async for entity in self._incremental_sync(cursor, files):
                yield entity

    async def _resolve_unresolved_viewers(
        self, entity: BaseEntity, graph_client: GraphClient
    ) -> None:
        """Resolve any user:id:{uuid} viewers to user:{email}."""
        if not hasattr(entity, "access") or entity.access is None:
            return
        viewers = entity.access.viewers or []
        unresolved = [v for v in viewers if v.startswith("user:id:")]
        if not unresolved:
            return
        user_ids = [v[len("user:id:") :] for v in unresolved]
        resolved = await graph_client.resolve_user_ids(user_ids)
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
        """Fetch all SP site groups and return their viewer strings."""
        sp_token_provider = self._make_sp_token_provider()
        if not sp_token_provider or not self._site_url:
            return []
        try:
            token = await sp_token_provider()
            headers = {
                "Authorization": f"Bearer {token}",
                "Accept": "application/json;odata=verbose",
            }
            resp = await self.http_client.get(
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
        except SourceAuthError:
            raise
        except Exception as e:
            self.logger.warning(f"SP group fetch failed: {e}")
            return []

    async def _full_sync(  # noqa: C901
        self,
        cursor: SyncCursor | None,
        files: FileService | None,
    ) -> AsyncGenerator[BaseEntity, None]:
        entity_count = 0
        graph_client = self._create_graph_client()

        sites = await self._discover_sites(graph_client)

        for site_data in sites:
            site_id = site_data.get("id", "")

            # Collect all drives for this site (single API call)
            all_drives = []
            async for drive_data in graph_client.get_drives(site_id):
                all_drives.append(drive_data)

            # Fetch site-level permissions from the first drive's root.
            site_access = None
            if all_drives:
                try:
                    site_permissions = await graph_client.get_drive_root_permissions(
                        all_drives[0]["id"]
                    )
                    site_access = await extract_access_control(site_permissions)
                except Exception as e:
                    self.logger.warning(f"Could not fetch site-level permissions: {e}")

            try:
                site_entity = await build_site_entity(site_data, [], access=site_access)
                self._track_entity_groups(site_entity)
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

            for drive_data in all_drives:
                drive_id = drive_data.get("id", "")
                try:
                    # Each drive gets its own root permissions
                    drive_access = site_access
                    if drive_id != all_drives[0]["id"]:
                        try:
                            drive_permissions = await graph_client.get_drive_root_permissions(
                                drive_id
                            )
                            drive_access = await extract_access_control(drive_permissions)
                        except Exception:
                            pass  # Fall back to site_access

                    drive_entity = await build_drive_entity(
                        drive_data, site_id, site_breadcrumbs, access=drive_access
                    )
                    self._track_entity_groups(drive_entity)
                    yield drive_entity
                    entity_count += 1

                    drive_breadcrumb = Breadcrumb(
                        entity_id=drive_entity.drive_id,
                        name=drive_entity.name,
                        entity_type="SharePointOnlineDriveEntity",
                    )
                    drive_breadcrumbs = site_breadcrumbs + [drive_breadcrumb]

                    pending_files: List[PendingFileDownload] = []

                    async for item_data in graph_client.get_drive_items_recursive(drive_id):
                        if item_data.get("folder"):
                            continue

                        if item_data.get("file"):
                            try:
                                permissions = await graph_client.get_item_permissions(
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

                                await self._resolve_unresolved_viewers(file_entity, graph_client)
                                if sp_group_viewers and file_entity.access:
                                    existing = set(file_entity.access.viewers or [])
                                    for spv in sp_group_viewers:
                                        if spv not in existing:
                                            file_entity.access.viewers.append(spv)
                                self._track_entity_groups(file_entity)

                                if files:
                                    pending_files.append(
                                        PendingFileDownload(
                                            entity=file_entity,
                                            drive_id=drive_id,
                                            item_id=item_data["id"],
                                        )
                                    )

                                    if len(pending_files) >= ITEM_BATCH_SIZE:
                                        downloaded = await self._download_files_parallel(
                                            pending_files, files
                                        )
                                        for ent in downloaded:
                                            yield ent
                                            entity_count += 1
                                        pending_files = []
                                else:
                                    yield file_entity
                                    entity_count += 1

                            except EntityProcessingError as e:
                                self.logger.warning(f"Skipping file: {e}")
                            except Exception as e:
                                self.logger.warning(f"Unexpected error processing file: {e}")

                    if pending_files and files:
                        downloaded = await self._download_files_parallel(pending_files, files)
                        for ent in downloaded:
                            yield ent
                            entity_count += 1

                    if cursor:
                        try:
                            _, delta_token = await graph_client.get_drive_delta(
                                drive_id, prefer_headers=self._delta_prefer_headers
                            )
                            if delta_token:
                                cursor_schema = SharePointOnlineCursor(**cursor.data)
                                cursor_schema.update_entity_cursor(
                                    drive_id=drive_id,
                                    delta_token=delta_token,
                                    changes_count=entity_count,
                                    is_full_sync=True,
                                )
                                cursor.update(**cursor_schema.model_dump())
                        except SourceAuthError:
                            raise
                        except Exception as e:
                            self.logger.warning(
                                f"Could not get delta token for drive {drive_id}: {e}"
                            )

                except EntityProcessingError as e:
                    self.logger.warning(f"Skipping drive {drive_id}: {e}")
                    continue

            if self._include_pages:
                try:
                    async for page_data in graph_client.get_pages(site_id):
                        try:
                            page_entity = await build_page_entity(
                                page_data, site_id, site_breadcrumbs, access=site_access
                            )
                            self._track_entity_groups(page_entity)
                            yield page_entity
                            entity_count += 1
                        except EntityProcessingError as e:
                            self.logger.warning(f"Skipping page: {e}")
                except SourceAuthError:
                    raise
                except Exception as e:
                    self.logger.debug(f"Pages not available for site {site_id}: {e}")

            if cursor:
                cursor_data = cursor.data
                synced_sites = cursor_data.get("synced_site_ids", {})
                synced_sites[site_id] = site_data.get("displayName", "")
                cursor.update(synced_site_ids=synced_sites)

        if cursor:
            cursor.update(
                full_sync_required=False,
                total_entities_synced=entity_count,
                tracked_entra_groups=list(self._item_level_entra_groups),
                tracked_sp_groups=list(self._item_level_sp_groups),
            )

        self.logger.info(f"Full sync complete: {entity_count} entities")

    async def _incremental_sync(  # noqa: C901
        self,
        cursor: SyncCursor | None,
        files: FileService | None,
    ) -> AsyncGenerator[BaseEntity, None]:
        cursor_data = cursor.data if cursor else {}
        schema = SharePointOnlineCursor(**cursor_data)
        delta_tokens = schema.drive_delta_tokens

        if not delta_tokens:
            self.logger.warning("No delta tokens for incremental sync, falling back to full")
            async for entity in self._full_sync(cursor, files):
                yield entity
            return

        changes_processed = 0
        graph_client = self._create_graph_client()

        for drive_id, token in delta_tokens.items():
            try:
                changed_items, new_token = await graph_client.get_drive_delta(
                    drive_id, token, prefer_headers=self._delta_prefer_headers
                )
            except SourceAuthError:
                raise
            except Exception as e:
                self.logger.warning(f"Delta query failed for drive {drive_id}: {e}")
                if cursor:
                    cursor.update(full_sync_required=True)
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
                        permissions = await graph_client.get_item_permissions(drive_id, item_id)
                        file_entity = await build_file_entity(
                            item_data,
                            drive_id,
                            "",
                            [],
                            permissions,
                        )
                        await self._resolve_unresolved_viewers(file_entity, graph_client)
                        self._track_entity_groups(file_entity)

                        if files:
                            file_entity = await self._download_and_save_file(
                                file_entity,
                                files,
                                drive_id,
                                item_id,
                            )
                        yield file_entity
                        changes_processed += 1
                    except (FileSkippedException, EntityProcessingError) as e:
                        self.logger.warning(f"Skipping changed file: {e}")

            if cursor and new_token:
                cursor_schema = SharePointOnlineCursor(**cursor.data)
                cursor_schema.update_entity_cursor(
                    drive_id=drive_id,
                    delta_token=new_token,
                    changes_count=changes_processed,
                )
                cursor.update(**cursor_schema.model_dump())

        self.logger.info(f"Incremental sync complete: {changes_processed} changes processed")

    # -- Targeted Sync --

    async def _targeted_sync(  # noqa: C901
        self,
        cursor: SyncCursor | None,
        files: FileService | None,
        node_selections: list[NodeSelectionData],
    ) -> AsyncGenerator[BaseEntity, None]:
        """Sync only the nodes specified in node_selections."""
        entity_count = 0

        site_ids: set = set()
        drive_selections: List[NodeSelectionData] = []

        for sel in node_selections:
            if sel.node_type == "site":
                site_ids.add(sel.node_metadata.get("site_id", "") if sel.node_metadata else "")
            elif sel.node_type in ("drive", "folder", "file"):
                drive_selections.append(sel)
                if sel.node_metadata and sel.node_metadata.get("site_id"):
                    site_ids.add(sel.node_metadata["site_id"])

        graph_client = self._create_graph_client()

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
                site_data = await graph_client.get_site(site_id)

                # Fetch site-level permissions from first drive root
                targeted_site_access = None
                async for peek_drive in graph_client.get_drives(site_id):
                    try:
                        perms = await graph_client.get_drive_root_permissions(peek_drive["id"])
                        targeted_site_access = await extract_access_control(perms)
                    except Exception:
                        pass
                    break

                site_entity = await build_site_entity(site_data, [], access=targeted_site_access)
                self._track_entity_groups(site_entity)
                yield site_entity
                entity_count += 1
            except SourceAuthError:
                raise
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

            async for drive_data in graph_client.get_drives(site_id):
                drive_id = drive_data.get("id", "")
                async for ent in self._sync_drive(
                    graph_client, drive_id, site_id, site_breadcrumbs, files
                ):
                    yield ent
                    entity_count += 1

        for sel in drive_selections:
            meta = sel.node_metadata or {}

            if sel.node_type == "drive":
                drive_id = meta.get("drive_id", "")
                sel_site_id = meta.get("site_id", "")
                if not drive_id:
                    continue
                async for ent in self._sync_drive(graph_client, drive_id, sel_site_id, [], files):
                    yield ent
                    entity_count += 1

            elif sel.node_type == "folder":
                drive_id = meta.get("drive_id", "")
                folder_id = meta.get("folder_id", "")
                if not drive_id or not folder_id:
                    continue
                async for ent in self._sync_folder_recursive(
                    graph_client, drive_id, folder_id, "", files
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
                    item_data = await graph_client.get(url)
                    if item_data.get("file"):
                        permissions = await graph_client.get_item_permissions(drive_id, item_id)
                        file_entity = await build_file_entity(
                            item_data, drive_id, "", [], permissions
                        )
                        await self._resolve_unresolved_viewers(file_entity, graph_client)
                        self._track_entity_groups(file_entity)
                        if files:
                            file_entity = await self._download_and_save_file(
                                file_entity, files, drive_id, item_id
                            )
                        yield file_entity
                        entity_count += 1
                except SourceAuthError:
                    raise
                except Exception as e:
                    self.logger.warning(f"Targeted sync: skipping file {item_id}: {e}")

        self.logger.info(f"Targeted sync complete: {entity_count} entities")

    async def _sync_drive(
        self,
        graph_client: GraphClient,
        drive_id: str,
        site_id: str,
        site_breadcrumbs: List[Breadcrumb],
        files: FileService | None,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Sync all files in a single drive (used by both full and targeted sync)."""
        try:
            drive_data = await graph_client.get_drive(drive_id)

            # Fetch drive root permissions for the drive entity
            drive_access = None
            try:
                drive_permissions = await graph_client.get_drive_root_permissions(drive_id)
                drive_access = await extract_access_control(drive_permissions)
            except Exception:
                pass

            drive_entity = await build_drive_entity(
                drive_data, site_id, site_breadcrumbs, access=drive_access
            )
            self._track_entity_groups(drive_entity)
            yield drive_entity

            drive_breadcrumbs = site_breadcrumbs + [
                Breadcrumb(
                    entity_id=drive_entity.drive_id,
                    name=drive_entity.name,
                    entity_type="SharePointOnlineDriveEntity",
                )
            ]

            item_stream = graph_client.get_drive_items_recursive(drive_id)
            async for entity in self._process_file_items(
                graph_client, item_stream, drive_id, site_id, drive_breadcrumbs, files
            ):
                yield entity
        except EntityProcessingError as e:
            self.logger.warning(f"Skipping drive {drive_id}: {e}")

    async def _sync_folder_recursive(
        self,
        graph_client: GraphClient,
        drive_id: str,
        folder_id: str,
        site_id: str,
        files: FileService | None,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Recursively sync all files under a specific folder."""
        item_stream = graph_client.get_drive_items_recursive(drive_id, folder_id)
        async for entity in self._process_file_items(
            graph_client,
            item_stream,
            drive_id,
            site_id,
            [],
            files,
            resolve_viewers=True,
        ):
            yield entity

    async def _process_file_items(
        self,
        graph_client: GraphClient,
        item_stream: AsyncGenerator[Dict[str, Any], None],
        drive_id: str,
        site_id: str,
        breadcrumbs: List[Breadcrumb],
        files: FileService | None,
        *,
        resolve_viewers: bool = False,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Iterate drive items, build file entities, and yield with batched downloads."""
        pending_files: List[PendingFileDownload] = []

        async for item_data in item_stream:
            if item_data.get("folder") or not item_data.get("file"):
                continue
            try:
                permissions = await graph_client.get_item_permissions(drive_id, item_data["id"])
                file_entity = await build_file_entity(
                    item_data, drive_id, site_id, breadcrumbs, permissions
                )
                if resolve_viewers:
                    await self._resolve_unresolved_viewers(file_entity, graph_client)
                self._track_entity_groups(file_entity)

                if files:
                    pending_files.append(
                        PendingFileDownload(
                            entity=file_entity,
                            drive_id=drive_id,
                            item_id=item_data["id"],
                        )
                    )
                    if len(pending_files) >= ITEM_BATCH_SIZE:
                        downloaded = await self._download_files_parallel(pending_files, files)
                        for ent in downloaded:
                            yield ent
                        pending_files = []
                else:
                    yield file_entity
            except EntityProcessingError as e:
                self.logger.warning(f"Skipping file: {e}")

        if pending_files and files:
            downloaded = await self._download_files_parallel(pending_files, files)
            for ent in downloaded:
                yield ent

    # -- Validation --

    async def validate(self) -> None:
        """Validate credentials by pinging the root site endpoint."""
        await self._get(f"{GRAPH_BASE_URL}/sites/root")

    # -- Access Control Memberships --

    async def _expand_entra_groups(
        self, group_expander: EntraGroupExpander
    ) -> AsyncGenerator[MembershipTuple, None]:
        """Expand tracked Entra ID groups into user memberships."""
        entra_group_ids = list(self._item_level_entra_groups)
        self.logger.info(f"Expanding {len(entra_group_ids)} Entra ID groups")
        for group_ref in entra_group_ids:
            group_id = group_ref.split(":", 1)[1] if ":" in group_ref else group_ref
            async for membership in group_expander.expand_group(group_id):
                yield membership

    async def _expand_sp_site_groups(self) -> AsyncGenerator[MembershipTuple, None]:
        """Expand tracked SP site groups into user memberships."""
        sp_group_names = list(self._item_level_sp_groups)
        if not sp_group_names or not self._site_url:
            return
        sp_token_provider = self._make_sp_token_provider()
        if not sp_token_provider:
            self.logger.warning("No SP token provider for site group expansion")
            return

        self.logger.info(f"Expanding {len(sp_group_names)} SP site groups")
        graph_client = self._create_graph_client()

        sp_groups = await graph_client.get_site_groups(
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

        async for m in self._expand_entra_groups(group_expander):
            yield m
            membership_count += 1

        try:
            async for m in self._expand_sp_site_groups():
                yield m
                membership_count += 1
        except SourceAuthError:
            raise
        except Exception as e:
            self.logger.warning(f"SP site group expansion failed: {e}")

        group_expander.log_stats()
        self.logger.info(f"Access control extraction complete: {membership_count} memberships")


# =============================================================================
# OAuth source — delegated user auth
# =============================================================================


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
class SharePointOnlineSource(SharePointOnlineBase):
    """SharePoint Online source using delegated OAuth.

    Uses the signed-in user's permissions via OAuth browser flow.
    Site discovery uses Graph search (delegated permissions).
    """

    @classmethod
    async def create(
        cls,
        *,
        auth: TokenProviderProtocol,
        logger: ContextualLogger,
        http_client: AirweaveHttpClient,
        config: SharePointOnlineConfig,
    ) -> SharePointOnlineSource:
        """Create and configure an OAuth SharePoint Online source."""
        instance = cls(auth=auth, logger=logger, http_client=http_client)
        instance._init_common(config)
        return instance

    async def _get_access_token(self) -> str:
        return await self.auth.get_token()

    async def _handle_401(self) -> str:
        if self.auth.supports_refresh:
            return await self.auth.force_refresh()
        return await self.auth.get_token()

    def _make_sp_token_provider(self) -> Optional[Callable]:
        """Create SP token provider via OAuth scope exchange."""
        sp_scope = self._derive_sp_resource_scope()
        if not sp_scope:
            return None

        async def _provider() -> str:
            token = await self.get_token_for_resource(sp_scope)
            if not token:
                raise RuntimeError(f"Could not obtain SharePoint token for scope {sp_scope}")
            return token

        return _provider

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

    async def _discover_sites(self, graph_client: GraphClient) -> List[Dict[str, Any]]:
        """Discover sites via Graph search (delegated permissions).

        Supports:
          - Single URL: "https://tenant.sharepoint.com/sites/MySite"
          - Comma-separated: "https://tenant.sharepoint.com/sites/A, .../sites/B"
          - Empty string: search all accessible sites
        """
        sites = []

        if self._site_url:
            urls = [u.strip() for u in self._site_url.split(",") if u.strip()]
            for url in urls:
                parsed = urlparse(url)
                hostname = parsed.netloc
                site_path = parsed.path.lstrip("/")
                try:
                    site = await graph_client.get_site_by_url(hostname, site_path)
                    sites.append(site)
                except SourceAuthError:
                    raise
                except Exception as e:
                    self.logger.warning(f"Could not resolve site URL {url}: {e}")
                    raise
        else:
            async for site in graph_client.search_sites("*"):
                if not self._include_personal_sites and site.get("isPersonalSite", False):
                    continue
                sites.append(site)

        self.logger.info(f"Discovered {len(sites)} sites to sync")
        return sites


# =============================================================================
# Client credentials source — app-only auth
# =============================================================================


@source(
    name="SharePoint Online (App)",
    short_name="sharepoint_online_app",
    auth_methods=[AuthenticationMethod.DIRECT],
    auth_config_class=SharePointOnlineAppAuthConfig,
    config_class=SharePointOnlineConfig,
    supports_continuous=True,
    cursor_class=SharePointOnlineCursor,
    supports_access_control=True,
    supports_browse_tree=True,
    feature_flag="sharepoint_2019_v2",
    labels=["Collaboration", "File Storage"],
)
class SharePointOnlineAppSource(SharePointOnlineBase):
    """SharePoint Online source using client credentials (app-only auth).

    Uses client_id + client_secret for Graph API and certificate-based
    authentication for SharePoint REST API. Requires Azure AD app registration
    with application permissions and admin consent.
    """

    _tenant_id: str
    _client_id: str
    _client_secret: str
    _private_key: str
    _certificate: str
    _graph_token: Optional[str]
    _graph_token_expires: float
    _sp_tokens: Dict[str, tuple[str, float]]

    @classmethod
    async def create(
        cls,
        *,
        auth: DirectCredentialProvider,
        logger: ContextualLogger,
        http_client: AirweaveHttpClient,
        config: SharePointOnlineConfig,
    ) -> SharePointOnlineAppSource:
        """Create and configure a client-credentials SharePoint Online source."""
        instance = cls(auth=auth, logger=logger, http_client=http_client)
        instance._init_common(config)

        creds: SharePointOnlineAppAuthConfig = auth.credentials
        instance._tenant_id = creds.tenant_id
        instance._client_id = creds.client_id
        instance._client_secret = creds.client_secret
        instance._private_key = creds.private_key
        instance._certificate = creds.certificate

        # Token cache
        instance._graph_token = None
        instance._graph_token_expires = 0.0
        instance._sp_tokens = {}  # hostname -> (token, expires_at)

        # Exchange for initial Graph token
        instance._graph_token = await instance._exchange_graph_token()
        instance._graph_token_expires = asyncio.get_event_loop().time() + 3500

        return instance

    # -- Token exchange (app-only mode) --

    async def _exchange_graph_token(self) -> str:
        """Exchange client credentials for a Microsoft Graph access token."""
        url = f"https://login.microsoftonline.com/{self._tenant_id}/oauth2/v2.0/token"
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                    "scope": "https://graph.microsoft.com/.default",
                },
            )
            resp.raise_for_status()
            data = resp.json()
            self.logger.info(f"App-only Graph token obtained (expires_in={data.get('expires_in')})")
            return str(data["access_token"])

    async def _exchange_sp_token_with_certificate(self, hostname: str) -> str:
        """Exchange certificate credentials for a SharePoint REST API access token."""
        import base64
        import hashlib
        import time as _time

        import jwt as pyjwt
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey
        from cryptography.x509 import load_pem_x509_certificate

        token_url = f"https://login.microsoftonline.com/{self._tenant_id}/oauth2/v2.0/token"

        loaded_key = serialization.load_pem_private_key(self._private_key.encode(), password=None)
        if not isinstance(loaded_key, RSAPrivateKey):
            raise ValueError("SharePoint certificate auth requires an RSA private key")
        private_key: RSAPrivateKey = loaded_key

        if not self._certificate:
            raise ValueError(
                "Certificate PEM is required for SP REST API token exchange. "
                "Provide the PEM certificate that was uploaded to the Azure AD app registration."
            )

        cert = load_pem_x509_certificate(self._certificate.encode())
        cert_der = cert.public_bytes(serialization.Encoding.DER)
        cert_hash = hashlib.sha1(cert_der).digest()  # noqa: S324
        x5t = base64.urlsafe_b64encode(cert_hash).rstrip(b"=").decode()

        now = int(_time.time())
        assertion = pyjwt.encode(
            {
                "aud": token_url,
                "iss": self._client_id,
                "sub": self._client_id,
                "jti": str(now),
                "nbf": now,
                "exp": now + 600,
            },
            private_key,
            algorithm="RS256",
            headers={"x5t": x5t},
        )

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                token_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self._client_id,
                    "client_assertion_type": (
                        "urn:ietf:params:oauth:client-assertion-type:jwt-bearer"
                    ),
                    "client_assertion": assertion,
                    "scope": f"https://{hostname}/.default",
                },
            )
            resp.raise_for_status()
            data = resp.json()
            self.logger.info(
                f"App-only SP token for {hostname} obtained (expires_in={data.get('expires_in')})"
            )
            return str(data["access_token"])

    async def _get_sp_token(self, hostname: str) -> str:
        """Get a valid SP REST API token for a hostname, re-exchanging if expired."""
        now = asyncio.get_event_loop().time()
        cached = self._sp_tokens.get(hostname)
        if cached:
            token, expires_at = cached
            if now < expires_at:
                return token
        token = await self._exchange_sp_token_with_certificate(hostname)
        self._sp_tokens[hostname] = (token, now + 3500)
        return token

    # -- Auth hooks --

    async def _get_access_token(self) -> str:
        now = asyncio.get_event_loop().time()
        if self._graph_token and now < self._graph_token_expires:
            return self._graph_token
        self._graph_token = await self._exchange_graph_token()
        self._graph_token_expires = now + 3500  # ~58 min
        return self._graph_token

    async def _handle_401(self) -> str:
        self._graph_token_expires = 0  # force re-exchange
        return await self._get_access_token()

    def _make_sp_token_provider(self) -> Optional[Callable]:
        """Create SP token provider via certificate exchange."""
        hostname = self._derive_sp_hostname()
        if not hostname:
            return None

        async def _provider() -> str:
            return await self._get_sp_token(hostname)

        return _provider

    @property
    def _delta_prefer_headers(self) -> List[str]:
        return [
            "deltashowsharingchanges",
            "deltashowremovedasdeleted",
            "deltatraversepermissiongaps",
        ]

    async def _get_download_auth(self, url: str) -> Any:
        """For client-credentials auth, use StaticTokenProvider for Graph URLs."""
        if "tempauth=" in url:
            return self.auth  # pre-signed URL, no auth needed
        graph_token = await self._get_access_token()
        return StaticTokenProvider(graph_token)

    async def _discover_sites(self, graph_client: GraphClient) -> List[Dict[str, Any]]:
        """Discover sites via getAllSites (application permissions).

        When site_url is set: resolve the specific site.
        When empty: use getAllSites for complete enumeration.
        """
        sites = []

        if self._site_url:
            parsed = urlparse(self._site_url)
            hostname = parsed.netloc
            site_path = parsed.path.lstrip("/")
            try:
                site = await graph_client.get_site_by_url(hostname, site_path)
                sites.append(site)
            except SourceAuthError:
                raise
            except Exception as e:
                self.logger.warning(f"Could not resolve site URL {self._site_url}: {e}")
                raise
        else:
            async for site in graph_client.get_all_sites():
                if not self._include_personal_sites and site.get("isPersonalSite", False):
                    continue
                sites.append(site)

        self.logger.info(f"Discovered {len(sites)} sites to sync")
        return sites
