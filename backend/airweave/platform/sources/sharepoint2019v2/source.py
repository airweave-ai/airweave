"""SharePoint 2019 On-Premise V2 Source.

This module contains the main source class that implements the BaseSource interface
for syncing data from SharePoint 2019 On-Premise.

Entity hierarchy:
- Sites (webs) - discovered recursively
- Lists - document libraries and custom lists within each site
- Items/Files - content within each list

Access graph generation:
- Requires AD credentials and server configuration
- Expands SP groups → users/AD groups
- Expands AD groups → users/nested groups via LDAP

Continuous Sync:
- Uses SharePoint GetChanges API (site collection level)
- Tracks changes via change tokens (valid ~60 days)
- Falls back to full sync when token expires

Performance:
- File downloads are parallelized (configurable concurrency)
- Items are processed in batches to reduce memory pressure
"""

import asyncio
import json
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Optional, Union

from airweave.platform.access_control.schemas import MembershipTuple
from airweave.platform.configs.auth import SharePoint2019V2AuthConfig
from airweave.platform.cursors.sharepoint2019v2 import SharePoint2019V2Cursor
from airweave.platform.decorators import source
from airweave.platform.entities._base import BaseEntity, Breadcrumb
from airweave.platform.sources._base import BaseSource
from airweave.platform.sources.sharepoint2019v2.acl import (
    extract_canonical_id,
    format_ad_group_id,
    format_sp_group_id,
)
from airweave.platform.sources.sharepoint2019v2.builders import (
    build_file_entity,
    build_item_entity,
    build_list_entity,
    build_site_entity,
)
from airweave.platform.sources.sharepoint2019v2.client import SharePointClient
from airweave.platform.storage import FileSkippedException
from airweave.platform.sync.exceptions import EntityProcessingError
from airweave.schemas.source_connection import AuthenticationMethod

# -------------------------------------------------------------------------
# Configuration Constants
# -------------------------------------------------------------------------

# Maximum concurrent file downloads (balance between speed and SharePoint load)
MAX_CONCURRENT_FILE_DOWNLOADS = 10

# Batch size for collecting items before parallel processing
# Larger batches = more parallelization, but more memory usage
ITEM_BATCH_SIZE = 50


@dataclass
class PendingFileDownload:
    """Holds a file entity pending download."""

    entity: Any  # SharePoint2019V2FileEntity
    site_url: str


@source(
    name="SharePoint 2019 On-Premise V2",
    short_name="sharepoint2019v2",
    auth_methods=[AuthenticationMethod.DIRECT],
    oauth_type=None,
    auth_config_class="SharePoint2019V2AuthConfig",
    config_class="SharePoint2019V2Config",
    supports_continuous=True,  # Enable incremental sync via GetChanges API
    cursor_class=SharePoint2019V2Cursor,  # Typed cursor for change token tracking
    supports_access_control=True,  # Enable access control sync
)
class SharePoint2019V2Source(BaseSource):
    """SharePoint 2019 On-Premise V2 source.

    Syncs data from SharePoint 2019 On-Premise using NTLM authentication:
    - Sites/subsites (recursive discovery)
    - Lists and document libraries
    - List items and files (with download)

    Access control is extracted from SharePoint role assignments and
    converted to canonical principal identifiers.
    """

    @classmethod
    async def create(
        cls,
        credentials: Union[SharePoint2019V2AuthConfig, Dict[str, Any]],
        config: Optional[Dict[str, Any]] = None,
    ) -> "SharePoint2019V2Source":
        """Create SharePoint 2019 V2 source instance.

        Args:
            credentials: Auth config with SharePoint and AD credentials
            config: Config dict with site_url, ad_server, and ad_search_base

        Returns:
            Configured source instance

        Raises:
            ValueError: If required config/credentials are missing
        """
        instance = cls()

        # Extract credentials
        if hasattr(credentials, "model_dump"):
            creds_dict = credentials.model_dump()
        else:
            creds_dict = dict(credentials)

        # SharePoint NTLM credentials (required)
        instance._sp_username = creds_dict.get("sharepoint_username")
        instance._sp_password = creds_dict.get("sharepoint_password")
        instance._sp_domain = creds_dict.get("sharepoint_domain")

        if not all([instance._sp_username, instance._sp_password, instance._sp_domain]):
            raise ValueError(
                "SharePoint credentials are required: sharepoint_username, "
                "sharepoint_password, and sharepoint_domain"
            )

        # AD LDAP credentials (required for access control)
        instance._ad_username = creds_dict.get("ad_username")
        instance._ad_password = creds_dict.get("ad_password")
        instance._ad_domain = creds_dict.get("ad_domain")

        if not all([instance._ad_username, instance._ad_password, instance._ad_domain]):
            raise ValueError(
                "Active Directory credentials are required for access control: "
                "ad_username, ad_password, and ad_domain. "
                "SharePoint 2019 V2 requires AD connectivity to resolve SIDs to sAMAccountNames."
            )

        # Validate config
        if not config:
            raise ValueError("Config is required with site_url, ad_server, and ad_search_base")

        # SharePoint config (required)
        if "site_url" not in config:
            raise ValueError("site_url is required in config")
        instance._site_url = config["site_url"].rstrip("/")

        # AD config (required for access control)
        instance._ad_server = config.get("ad_server")
        instance._ad_search_base = config.get("ad_search_base")

        if not all([instance._ad_server, instance._ad_search_base]):
            raise ValueError(
                "Active Directory server configuration is required: "
                "ad_server and ad_search_base. "
                "SharePoint 2019 V2 requires AD connectivity to resolve SIDs to sAMAccountNames."
            )

        # Track AD groups from item-level ACLs (populated during entity sync)
        # These are AD groups directly assigned to items, not via SP site groups
        instance._item_level_ad_groups: set = set()

        # Test mode limits (optional - for quick testing)
        instance._max_entities: Optional[int] = config.get("max_entities")
        instance._max_memberships: Optional[int] = config.get("max_memberships")

        if instance._max_entities:
            instance.logger.info(f"🧪 TEST MODE: Limiting to {instance._max_entities} entities")
        if instance._max_memberships:
            instance.logger.info(
                f"🧪 TEST MODE: Limiting to {instance._max_memberships} memberships"
            )

        return instance

    @property
    def site_url(self) -> str:
        """Get the configured site URL."""
        return self._site_url

    @property
    def has_ad_config(self) -> bool:
        """Check if AD configuration is available for access graph generation."""
        return all(
            [
                self._ad_username,
                self._ad_password,
                self._ad_domain,
                self._ad_server,
                self._ad_search_base,
            ]
        )

    def _track_entity_ad_groups(self, entity: BaseEntity) -> None:
        """Extract and track AD groups from an entity's access control.

        Called during entity generation to collect AD groups that are directly
        assigned to items (not via SharePoint site groups). These groups will
        be expanded via LDAP during the access control membership sync.

        Args:
            entity: Entity with potential access control
        """
        if not hasattr(entity, "access") or entity.access is None:
            return

        viewers = entity.access.viewers or []
        for viewer in viewers:
            # AD groups have format "group:ad:{group_name}"
            if viewer.startswith("group:ad:"):
                # Extract the AD group ID (e.g., "ad:group_sales" from "group:ad:group_sales")
                # The format used in memberships is "ad:{group_name}" without the "group:" prefix
                ad_group_id = viewer[6:]  # Remove "group:" prefix → "ad:group_sales"
                self._item_level_ad_groups.add(ad_group_id)

    def _create_client(self) -> SharePointClient:
        """Create SharePoint API client with current credentials."""
        return SharePointClient(
            username=self._sp_username,
            password=self._sp_password,
            domain=self._sp_domain,
            logger=self.logger,
        )

    # -------------------------------------------------------------------------
    # File Download
    # -------------------------------------------------------------------------

    async def _download_and_save_file(
        self,
        entity,
        client,
        site_url: str,
    ):
        """Download file content and save using file downloader.

        Args:
            entity: SharePoint2019V2FileEntity to populate
            client: httpx AsyncClient instance
            site_url: Base URL of the site

        Returns:
            The entity if download succeeded

        Raises:
            FileSkippedException: If file should be skipped
            EntityProcessingError: If download fails
        """
        sp_client = self._create_client()
        try:
            content = await sp_client.get_file_content(client, site_url, entity.server_relative_url)
            await self.file_downloader.save_bytes(
                entity=entity,
                content=content,
                filename_with_extension=entity.file_name,
                logger=self.logger,
            )
            return entity
        except FileSkippedException:
            raise
        except Exception as e:
            self.logger.error(f"Failed to download file {entity.file_name}: {e}")
            raise EntityProcessingError(f"Failed to download file {entity.file_name}: {e}") from e

    async def _download_files_parallel(
        self,
        pending_downloads: List[PendingFileDownload],
        client,
    ) -> List[BaseEntity]:
        """Download multiple files in parallel with concurrency limit.

        Args:
            pending_downloads: List of PendingFileDownload with entity and site_url
            client: httpx AsyncClient instance

        Returns:
            List of successfully downloaded file entities
        """
        if not pending_downloads:
            return []

        semaphore = asyncio.Semaphore(MAX_CONCURRENT_FILE_DOWNLOADS)
        results: List[Optional[BaseEntity]] = []
        start_time = time.monotonic()

        async def download_with_semaphore(
            pending: PendingFileDownload, index: int
        ) -> Optional[BaseEntity]:
            """Download a single file with semaphore control."""
            async with semaphore:
                try:
                    entity = await self._download_and_save_file(
                        pending.entity, client, pending.site_url
                    )
                    return entity
                except FileSkippedException:
                    self.logger.debug(f"Skipped file: {pending.entity.file_name}")
                    return None
                except EntityProcessingError as e:
                    self.logger.warning(f"Failed to download file: {e}")
                    return None

        # Execute all downloads concurrently (limited by semaphore)
        download_tasks = [
            download_with_semaphore(pending, i) for i, pending in enumerate(pending_downloads)
        ]
        results = await asyncio.gather(*download_tasks)

        # Filter out failed/skipped downloads
        successful = [entity for entity in results if entity is not None]

        elapsed = time.monotonic() - start_time
        self.logger.info(
            f"📥 Parallel download: {len(successful)}/{len(pending_downloads)} files "
            f"in {elapsed:.2f}s ({MAX_CONCURRENT_FILE_DOWNLOADS} concurrent)"
        )

        return successful

    async def _process_items_batch(
        self,
        items_batch: List[Dict[str, Any]],
        site_url: str,
        list_id: str,
        breadcrumbs: List[Breadcrumb],
        is_doc_lib: bool,
        client,
        ldap_client,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Process a batch of items with parallel file downloads.

        This method:
        1. Separates file items from non-file items
        2. Builds entities for all items (without downloading files)
        3. Downloads all files in parallel
        4. Yields all successfully processed entities

        Args:
            items_batch: List of item metadata dicts from SharePoint
            site_url: Base URL of the site
            list_id: GUID of the list containing these items
            breadcrumbs: Parent breadcrumb trail
            is_doc_lib: Whether this is a document library
            client: httpx AsyncClient instance
            ldap_client: LDAPClient for SID resolution

        Yields:
            Successfully processed entities
        """
        if not items_batch:
            return

        # Separate files from non-files and build entities
        pending_files: List[PendingFileDownload] = []
        non_file_entities: List[BaseEntity] = []

        for item_meta in items_batch:
            fs_obj_type: Optional[int] = item_meta.get("FileSystemObjectType")

            if fs_obj_type is None:
                item_id = item_meta.get("Id", "unknown")
                self.logger.warning(f"Skipping item {item_id}: Missing FileSystemObjectType")
                continue

            # Skip folders
            if fs_obj_type == 1:
                continue

            is_file = is_doc_lib and fs_obj_type == 0

            if is_file:
                try:
                    file_entity = await build_file_entity(
                        item_meta, site_url, list_id, breadcrumbs, ldap_client
                    )
                    pending_files.append(
                        PendingFileDownload(
                            entity=file_entity,
                            site_url=site_url,
                        )
                    )
                except EntityProcessingError as e:
                    self.logger.warning(f"Skipping file entity build: {e}")
            else:
                try:
                    item_entity = await build_item_entity(
                        item_meta, site_url, list_id, breadcrumbs, ldap_client
                    )
                    non_file_entities.append(item_entity)
                except EntityProcessingError as e:
                    self.logger.warning(f"Skipping item: {e}")

        # Yield non-file entities immediately (no download needed)
        for entity in non_file_entities:
            self._track_entity_ad_groups(entity)
            yield entity

        # Download files in parallel and yield
        if pending_files:
            downloaded_entities = await self._download_files_parallel(pending_files, client)
            for entity in downloaded_entities:
                self._track_entity_ad_groups(entity)
                yield entity

    # -------------------------------------------------------------------------
    # Entity Generation (with Incremental Sync Support)
    # -------------------------------------------------------------------------

    def _should_do_full_sync(self) -> tuple[bool, str]:
        """Determine if full sync is needed.

        Returns:
            Tuple of (should_full_sync, reason)
        """
        if not self.cursor:
            return True, "No cursor available"

        cursor_data = self.cursor.data
        change_token = cursor_data.get("site_collection_change_token")

        if not change_token:
            return True, "No change token stored"

        # Check token age (expire after 55 days to be safe)
        last_sync = cursor_data.get("last_entity_sync_timestamp")
        if last_sync:
            try:
                last_sync_dt = datetime.fromisoformat(last_sync.replace("Z", "+00:00"))
                age_days = (datetime.now(last_sync_dt.tzinfo) - last_sync_dt).days
                if age_days > 55:
                    return True, f"Change token is {age_days} days old (max 60 days retention)"
            except (ValueError, TypeError):
                return True, "Invalid last_entity_sync_timestamp"

        # Check if periodic full sync is needed (weekly for cleanup)
        last_full = cursor_data.get("last_full_sync_timestamp")
        if last_full:
            try:
                last_full_dt = datetime.fromisoformat(last_full.replace("Z", "+00:00"))
                days_since_full = (datetime.now(last_full_dt.tzinfo) - last_full_dt).days
                if days_since_full >= 7:
                    return True, f"Periodic full sync needed ({days_since_full} days since last)"
            except (ValueError, TypeError):
                pass

        return False, ""

    async def generate_entities(self) -> AsyncGenerator[BaseEntity, None]:
        """Generate entities from SharePoint with incremental sync support.

        Routing logic:
        1. Check cursor for existing change token
        2. If token valid: do incremental sync (fetch only changes)
        3. If no token or expired: do full sync (fetch everything)
        4. Update cursor with new token after sync

        Yields:
            BaseEntity instances (Site, List, Item, File)
        """
        should_full, reason = self._should_do_full_sync()

        if should_full:
            self.logger.info(f"🔄 FULL SYNC: {reason}")
            async for entity in self._full_sync():
                yield entity
        else:
            self.logger.info("⚡ INCREMENTAL SYNC: Using stored change token")
            async for entity in self._incremental_sync():
                yield entity

    async def _full_sync(self) -> AsyncGenerator[BaseEntity, None]:
        """Full sync: traverse entire site hierarchy.

        Traverses the site hierarchy:
        1. Fetch site metadata
        2. For each site, discover and process lists
        3. For each list, discover and process items/files
        4. Recursively discover subsites

        After sync completes, stores current change token for future incremental syncs.

        Yields:
            BaseEntity instances (Site, List, Item, File)
        """
        from airweave.platform.sources.sharepoint2019v2.ldap import LDAPClient

        # Create LDAP client for SID resolution (reused across all entities)
        ldap_client = LDAPClient(
            server=self._ad_server,
            username=self._ad_username,
            password=self._ad_password,
            domain=self._ad_domain,
            search_base=self._ad_search_base,
            logger=self.logger,
        )

        entity_count = 0
        limit_reached = False

        def _check_limit() -> bool:
            """Check if entity limit has been reached."""
            if self._max_entities and entity_count >= self._max_entities:
                self.logger.info(
                    f"🧪 TEST MODE: Entity limit reached ({entity_count}/{self._max_entities})"
                )
                return True
            return False

        try:
            async with self.http_client(verify=False) as client:
                sp_client = self._create_client()

                # Queue of (site_url, parent_breadcrumbs) to process
                sites_to_process: List[tuple] = [(self._site_url, [])]
                processed_sites: set = set()

                while sites_to_process and not limit_reached:
                    current_site_url, parent_breadcrumbs = sites_to_process.pop(0)

                    # Skip already processed sites
                    if current_site_url in processed_sites:
                        continue
                    processed_sites.add(current_site_url)

                    # Fetch and yield site entity
                    current_site_breadcrumbs = parent_breadcrumbs
                    try:
                        site_data = await sp_client.get_site(client, current_site_url)
                        site_entity = await build_site_entity(
                            site_data, parent_breadcrumbs, ldap_client
                        )
                        self.logger.debug(
                            f"Site entity: {json.dumps(site_entity, indent=2, default=str)}"
                        )
                        self._track_entity_ad_groups(site_entity)
                        yield site_entity
                        entity_count += 1

                        if _check_limit():
                            limit_reached = True
                            break

                        # Build breadcrumb for child entities
                        site_breadcrumb = Breadcrumb(
                            entity_id=site_entity.site_id,
                            name=site_entity.title,
                            entity_type="SharePoint2019V2SiteEntity",
                        )
                        current_site_breadcrumbs = parent_breadcrumbs + [site_breadcrumb]
                    except Exception as e:
                        self.logger.error(f"Skipping site {current_site_url}: {e}")
                        continue

                    # Process lists in this site
                    async for list_meta in sp_client.discover_lists(client, current_site_url):
                        if limit_reached:
                            break

                        try:
                            list_entity = await build_list_entity(
                                list_meta, current_site_url, current_site_breadcrumbs, ldap_client
                            )
                            self.logger.debug(
                                f"List entity: {json.dumps(list_entity, indent=2, default=str)}"
                            )
                            self._track_entity_ad_groups(list_entity)
                            yield list_entity
                            entity_count += 1

                            if _check_limit():
                                limit_reached = True
                                break

                            # Build breadcrumb for items
                            list_breadcrumb = Breadcrumb(
                                entity_id=list_entity.list_id,
                                name=list_entity.title,
                                entity_type="SharePoint2019V2ListEntity",
                            )
                            list_breadcrumbs = current_site_breadcrumbs + [list_breadcrumb]

                            # Process items in this list (with batch parallelization)
                            is_doc_lib = list_entity.base_template == 101
                            current_list_id = list_meta["Id"]
                            items_batch: List[Dict[str, Any]] = []

                            async for item_meta in sp_client.discover_items(
                                client, current_site_url, current_list_id
                            ):
                                if limit_reached:
                                    break

                                items_batch.append(item_meta)

                                # Process batch when full
                                if len(items_batch) >= ITEM_BATCH_SIZE:
                                    async for entity in self._process_items_batch(
                                        items_batch,
                                        current_site_url,
                                        current_list_id,
                                        list_breadcrumbs,
                                        is_doc_lib,
                                        client,
                                        ldap_client,
                                    ):
                                        yield entity
                                        entity_count += 1

                                        if _check_limit():
                                            limit_reached = True
                                            break
                                    items_batch = []

                            # Process remaining items in final batch
                            if items_batch and not limit_reached:
                                async for entity in self._process_items_batch(
                                    items_batch,
                                    current_site_url,
                                    current_list_id,
                                    list_breadcrumbs,
                                    is_doc_lib,
                                    client,
                                    ldap_client,
                                ):
                                    yield entity
                                    entity_count += 1

                                    if _check_limit():
                                        limit_reached = True
                                        break

                        except EntityProcessingError as e:
                            self.logger.warning(f"Skipping list: {e}")
                            continue

                    # Discover subsites and add to queue (skip if limit reached)
                    if not limit_reached:
                        async for subsite in sp_client.discover_subsites(client, current_site_url):
                            subsite_url = subsite.get("Url", "").rstrip("/")
                            if subsite_url:
                                sites_to_process.append((subsite_url, current_site_breadcrumbs))

                # After full sync, get current change token for next incremental
                if self.cursor:
                    try:
                        new_token = await sp_client.get_current_change_token(client, self._site_url)
                        now = datetime.utcnow().isoformat() + "Z"
                        self.cursor.update(
                            site_collection_change_token=new_token,
                            site_collection_url=self._site_url,
                            last_entity_sync_timestamp=now,
                            last_full_sync_timestamp=now,
                            last_entity_changes_count=entity_count,
                            total_entities_synced=entity_count,
                            full_sync_required=False,
                        )
                        self.logger.info(
                            f"📝 Stored change token for future incremental syncs "
                            f"({entity_count} entities synced)"
                        )
                    except Exception as e:
                        self.logger.warning(f"Failed to store change token: {e}")
        finally:
            ldap_client.close()

    async def _incremental_sync(self) -> AsyncGenerator[BaseEntity, None]:
        """Incremental sync: fetch only changed entities since last token.

        Uses SharePoint GetChanges API at site collection level to retrieve:
        - Added entities
        - Updated entities
        - Deleted entities (yielded as deletion markers)

        Yields:
            BaseEntity instances for changed items
        """
        from airweave.platform.sources.sharepoint2019v2.ldap import LDAPClient

        cursor_data = self.cursor.data if self.cursor else {}
        change_token = cursor_data.get("site_collection_change_token", "")

        # Create LDAP client for SID resolution
        ldap_client = LDAPClient(
            server=self._ad_server,
            username=self._ad_username,
            password=self._ad_password,
            domain=self._ad_domain,
            search_base=self._ad_search_base,
            logger=self.logger,
        )

        changes_count = 0
        try:
            async with self.http_client(verify=False) as client:
                sp_client = self._create_client()

                # Get changes since last token
                changes, new_token = await sp_client.get_site_collection_changes(
                    client,
                    self._site_url,
                    change_token=change_token,
                    include_deletes=True,
                )

                self.logger.info(f"📊 Found {len(changes)} changes since last sync")

                for change in changes:
                    change_type = change.get("change_type")
                    list_id = change.get("list_id")
                    item_id = change.get("item_id")

                    # Map change type codes: 1=Add, 2=Update, 3=Delete
                    if change_type == 3:  # Delete
                        # Yield deletion entity - orchestrator will handle removal from vector store
                        if item_id and list_id:
                            from airweave.platform.entities.sharepoint2019v2 import (
                                SharePoint2019V2FileDeletionEntity,
                                SharePoint2019V2ItemDeletionEntity,
                            )

                            # Determine if this was a file or item based on the list type
                            # We need to check if the list is a document library
                            list_meta = await sp_client.get_list_by_id(
                                client, self._site_url, list_id
                            )
                            is_doc_lib = (
                                list_meta.get("BaseTemplate") == 101 if list_meta else False
                            )

                            # Create the appropriate deletion entity
                            # The sp_entity_id matches the format used during creation
                            if is_doc_lib:
                                deletion_entity = SharePoint2019V2FileDeletionEntity(
                                    breadcrumbs=[],
                                    list_id=list_id,
                                    item_id=item_id,
                                    sp_entity_id=f"sp2019v2:file:{list_id}:{item_id}",
                                    label=f"Deleted file {item_id}",
                                    deletion_status="removed",
                                )
                            else:
                                deletion_entity = SharePoint2019V2ItemDeletionEntity(
                                    breadcrumbs=[],
                                    list_id=list_id,
                                    item_id=item_id,
                                    sp_entity_id=f"sp2019v2:item:{list_id}:{item_id}",
                                    label=f"Deleted item {item_id}",
                                    deletion_status="removed",
                                )
                            yield deletion_entity
                            changes_count += 1
                    else:  # Add (1) or Update (2)
                        if item_id and list_id:
                            try:
                                # Fetch the changed item
                                item_meta = await sp_client.get_item_by_id(
                                    client, self._site_url, list_id, item_id
                                )
                                if item_meta:
                                    # Determine if doc library item
                                    list_meta = await sp_client.get_list_by_id(
                                        client, self._site_url, list_id
                                    )
                                    is_doc_lib = (
                                        list_meta.get("BaseTemplate") == 101 if list_meta else False
                                    )

                                    # Process item (yields file or item entity)
                                    async for entity in self._process_item(
                                        item_meta,
                                        self._site_url,
                                        list_id,
                                        [],  # TODO: rebuild breadcrumbs
                                        is_doc_lib,
                                        client,
                                        ldap_client,
                                    ):
                                        yield entity
                                        changes_count += 1
                            except Exception as e:
                                self.logger.warning(
                                    f"Failed to fetch changed item {list_id}/{item_id}: {e}"
                                )

                # Update cursor with new token
                if self.cursor:
                    now = datetime.utcnow().isoformat() + "Z"
                    self.cursor.update(
                        site_collection_change_token=new_token,
                        last_entity_sync_timestamp=now,
                        last_entity_changes_count=changes_count,
                    )
                    self.logger.info(f"📝 Updated change token ({changes_count} changes processed)")

        finally:
            ldap_client.close()

    async def _process_item(
        self,
        item_meta: Dict[str, Any],
        site_url: str,
        list_id: str,
        breadcrumbs: List[Breadcrumb],
        is_doc_lib: bool,
        client,
        ldap_client,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Process a single list item, yielding appropriate entity.

        Args:
            item_meta: Item metadata from SharePoint API
            site_url: Base URL of the site
            list_id: GUID of the list containing this item
            breadcrumbs: Parent breadcrumb trail
            is_doc_lib: Whether this is a document library
            client: httpx AsyncClient instance
            ldap_client: LDAPClient for SID resolution

        Yields:
            Item or File entity
        """
        fs_obj_type: Optional[int] = item_meta.get("FileSystemObjectType")

        if fs_obj_type is None:
            item_id = item_meta.get("Id", "unknown")
            self.logger.warning(f"Skipping item {item_id}: Missing FileSystemObjectType")
            return

        # Skip folders
        if fs_obj_type == 1:
            return

        is_file = is_doc_lib and fs_obj_type == 0

        if is_file:
            try:
                file_entity = await build_file_entity(
                    item_meta, site_url, list_id, breadcrumbs, ldap_client
                )
                self.logger.debug(f"File entity: {json.dumps(file_entity, indent=2, default=str)}")
                file_entity = await self._download_and_save_file(file_entity, client, site_url)
                self._track_entity_ad_groups(file_entity)
                yield file_entity
            except FileSkippedException:
                return
            except EntityProcessingError as e:
                self.logger.warning(f"Skipping file: {e}")
                return
        else:
            try:
                item_entity = await build_item_entity(
                    item_meta, site_url, list_id, breadcrumbs, ldap_client
                )
                self.logger.debug(f"Item entity: {json.dumps(item_entity, indent=2, default=str)}")
                self._track_entity_ad_groups(item_entity)
                yield item_entity
            except EntityProcessingError as e:
                self.logger.warning(f"Skipping item: {e}")
                return

    # -------------------------------------------------------------------------
    # Validation
    # -------------------------------------------------------------------------

    async def validate(self) -> bool:
        """Validate SharePoint and Active Directory connections.

        Verifies:
        1. SharePoint connectivity (fetch site metadata)
        2. AD/LDAP connectivity (establish LDAP connection)

        Returns:
            True if both connections are valid, False otherwise
        """
        # Validate SharePoint connection
        try:
            async with self.http_client(verify=False) as client:
                sp_client = self._create_client()
                await sp_client.get(client, f"{self._site_url}/_api/web")
            self.logger.info("SharePoint connection validated successfully")
        except Exception as e:
            self.logger.error(f"SharePoint validation failed: {e}")
            return False

        # Validate AD/LDAP connection
        try:
            from airweave.platform.sources.sharepoint2019v2.ldap import LDAPClient

            ldap_client = LDAPClient(
                server=self._ad_server,
                username=self._ad_username,
                password=self._ad_password,
                domain=self._ad_domain,
                search_base=self._ad_search_base,
                logger=self.logger,
            )
            await ldap_client.connect()
            ldap_client.close()
            self.logger.info("Active Directory connection validated successfully")
        except Exception as e:
            self.logger.error(f"Active Directory validation failed: {e}")
            return False

        return True

    # -------------------------------------------------------------------------
    # Access Control Memberships
    # -------------------------------------------------------------------------

    async def _process_sp_group_member(
        self,
        member: Dict[str, Any],
        sp_group_id: str,
        group_title: str,
        ldap_client: Optional[Any],
    ) -> AsyncGenerator[MembershipTuple, None]:
        """Process a single SharePoint group member.

        Args:
            member: Member metadata from SharePoint API
            sp_group_id: Canonical SP group ID (e.g., "sp:site_members")
            group_title: Human-readable group title
            ldap_client: Optional LDAPClient for AD group expansion

        Yields:
            MembershipTuple instances
        """
        principal_type = member.get("PrincipalType", 0)
        login_name = member.get("LoginName", "")

        if not login_name:
            return

        if principal_type == 1:  # User
            yield MembershipTuple(
                member_id=extract_canonical_id(login_name),
                member_type="user",
                group_id=sp_group_id,
                group_name=group_title,
            )

        elif principal_type == 4:  # AD Security Group
            ad_group_id = format_ad_group_id(login_name)
            yield MembershipTuple(
                member_id=ad_group_id,
                member_type="group",
                group_id=sp_group_id,
                group_name=group_title,
            )

            if ldap_client:
                async for ad_membership in ldap_client.expand_group_recursive(login_name):
                    yield ad_membership

    def _create_ldap_client(self) -> Optional[Any]:
        """Create LDAP client if AD is configured.

        Returns:
            LDAPClient instance or None if AD not configured
        """
        if not self.has_ad_config:
            self.logger.warning(
                "AD configuration not provided - AD groups will NOT be expanded. "
                "Only SharePoint group memberships will be generated."
            )
            return None

        from airweave.platform.sources.sharepoint2019v2.ldap import LDAPClient

        self.logger.info("AD configuration found - will expand AD groups via LDAP")
        return LDAPClient(
            server=self._ad_server,
            username=self._ad_username,
            password=self._ad_password,
            domain=self._ad_domain,
            search_base=self._ad_search_base,
            logger=self.logger,
        )

    async def generate_access_control_memberships(
        self,
    ) -> AsyncGenerator[MembershipTuple, None]:
        """Generate access control memberships for SharePoint + AD.

        Creates membership tuples that map the access graph:
        - SP Group → User (direct user membership)
        - SP Group → AD Group (AD group is member of SP group)
        - AD Group → User (via LDAP expansion)
        - AD Group → AD Group (nested groups via LDAP)

        Also expands AD groups that are directly assigned to items (not via SP groups).
        These are collected during entity generation in _item_level_ad_groups.

        The formats used here MUST match the entity access control format in acl.py:
        - Entity viewer: "user:{id}" or "group:{type}:{id}"
        - Membership group_id: "{type}:{id}" (broker adds "group:" prefix)
        - Membership member_id: raw identifier for users, "{type}:{id}" for groups

        If AD configuration is not provided, only SharePoint group memberships
        are returned (AD groups will not be expanded).

        Yields:
            MembershipTuple instances
        """
        self.logger.info("Starting access control membership extraction")
        membership_count = 0
        limit_reached = False
        ldap_client = self._create_ldap_client()
        # Track AD groups already expanded (to avoid duplicate work)
        expanded_ad_groups: set = set()

        def _check_membership_limit() -> bool:
            """Check if membership limit has been reached."""
            if self._max_memberships and membership_count >= self._max_memberships:
                self.logger.info(
                    f"🧪 TEST MODE: Membership limit reached "
                    f"({membership_count}/{self._max_memberships})"
                )
                return True
            return False

        try:
            async with self.http_client(verify=False) as client:
                sp_client = self._create_client()

                # Phase 1: Process SharePoint site groups
                async for sp_group in sp_client.get_site_groups(client, self._site_url):
                    if limit_reached:
                        break

                    group_id = sp_group.get("Id")
                    group_title = sp_group.get("Title", "Unknown Group")

                    if not group_id:
                        continue

                    self.logger.debug(f"Processing SP group: {group_title}")
                    sp_group_id = format_sp_group_id(group_title)

                    async for member in sp_client.get_group_members(
                        client, self._site_url, group_id
                    ):
                        if limit_reached:
                            break

                        async for membership in self._process_sp_group_member(
                            member, sp_group_id, group_title, ldap_client
                        ):
                            yield membership
                            membership_count += 1
                            # Track AD groups already expanded via SP group membership
                            if membership.group_id.startswith("ad:"):
                                expanded_ad_groups.add(membership.group_id)

                            if _check_membership_limit():
                                limit_reached = True
                                break

            # Phase 2: Expand item-level AD groups that weren't in SP groups
            if not limit_reached:
                async for membership in self._expand_item_level_ad_groups(
                    ldap_client, expanded_ad_groups
                ):
                    yield membership
                    membership_count += 1

                    if _check_membership_limit():
                        break

            self.logger.info(f"Access control extraction complete: {membership_count} memberships")

        except Exception as e:
            self.logger.error(f"Error generating access control memberships: {e}", exc_info=True)
            raise
        finally:
            if ldap_client:
                ldap_client.close()

    async def _expand_item_level_ad_groups(
        self,
        ldap_client,
        expanded_ad_groups: set,
    ) -> AsyncGenerator[MembershipTuple, None]:
        """Expand AD groups directly assigned to items (not via SP site groups).

        Args:
            ldap_client: LDAP client for group expansion
            expanded_ad_groups: Set of AD group IDs already expanded via SP groups
        """
        if not ldap_client or not self._item_level_ad_groups:
            return

        # Find AD groups only on items (not also in SP groups)
        item_only_ad_groups = self._item_level_ad_groups - expanded_ad_groups

        if not item_only_ad_groups:
            return

        self.logger.info(
            f"Expanding {len(item_only_ad_groups)} item-level AD groups "
            f"(not in SP site groups): {item_only_ad_groups}"
        )

        for ad_group_id in item_only_ad_groups:
            # ad_group_id is in format "ad:group_name"
            group_name = ad_group_id[3:]  # Remove "ad:" prefix
            login_name = f"{self._ad_domain}\\{group_name}"

            self.logger.debug(f"Expanding item-level AD group: {group_name}")
            async for membership in ldap_client.expand_group_recursive(login_name):
                yield membership

    # -------------------------------------------------------------------------
    # Incremental ACL Sync (via AD DirSync)
    # -------------------------------------------------------------------------

    def _should_do_full_acl_sync(self) -> tuple[bool, str]:
        """Determine if full ACL sync is needed.

        Returns:
            Tuple of (should_full_sync, reason)
        """
        if not self.cursor:
            return True, "No cursor available"

        cursor_data = self.cursor.data
        dirsync_cookie = cursor_data.get("acl_dirsync_cookie", "")

        if not dirsync_cookie:
            return True, "No DirSync cookie stored"

        # Check cookie age (expire after 55 days to be safe)
        last_sync = cursor_data.get("last_acl_sync_timestamp", "")
        if last_sync:
            try:
                from datetime import datetime

                last_sync_dt = datetime.fromisoformat(last_sync.replace("Z", "+00:00"))
                age_days = (datetime.now(last_sync_dt.tzinfo) - last_sync_dt).days
                if age_days > 55:
                    return True, f"DirSync cookie is {age_days} days old (max retention varies)"
            except (ValueError, TypeError):
                return True, "Invalid last_acl_sync_timestamp"

        # Check if periodic full sync is needed (weekly for cleanup)
        last_full = cursor_data.get("last_full_sync_timestamp", "")
        if last_full:
            try:
                from datetime import datetime

                last_full_dt = datetime.fromisoformat(last_full.replace("Z", "+00:00"))
                days_since_full = (datetime.now(last_full_dt.tzinfo) - last_full_dt).days
                if days_since_full >= 7:
                    return True, f"Periodic full ACL sync ({days_since_full} days since last)"
            except (ValueError, TypeError):
                pass

        return False, ""

    async def get_acl_changes(
        self,
        dirsync_cookie: str = "",
    ):
        """Get ACL membership changes since last sync using AD DirSync.

        This is the incremental ACL sync method. It uses the DirSync control
        to efficiently fetch only the group membership changes since the last
        sync (identified by the cookie).

        For initial sync (no cookie), returns all current memberships as ADD changes.

        Args:
            dirsync_cookie: Base64-encoded cookie from previous sync (empty for first)

        Returns:
            DirSyncResult with list of MembershipChange objects and new cookie

        Raises:
            ValueError: If AD is not configured
        """
        from airweave.platform.sources.sharepoint2019v2.ldap import DirSyncResult, LDAPClient

        if not self.has_ad_config:
            raise ValueError(
                "AD configuration required for incremental ACL sync. "
                "Provide ad_username, ad_password, ad_domain, ad_server, ad_search_base."
            )

        # Late import to get the actual class for type checking
        _ = DirSyncResult  # noqa: F841 - used for return type

        ldap_client = LDAPClient(
            server=self._ad_server,
            username=self._ad_username,
            password=self._ad_password,
            domain=self._ad_domain,
            search_base=self._ad_search_base,
            logger=self.logger,
        )

        try:
            result = await ldap_client.get_membership_changes(cookie_b64=dirsync_cookie)
            ldap_client.log_cache_stats()
            return result
        finally:
            ldap_client.close()

    def supports_incremental_acl(self) -> bool:
        """Check if this source supports incremental ACL sync.

        Returns True if:
        1. AD configuration is available
        2. The source supports continuous sync

        Returns:
            True if incremental ACL sync is supported
        """
        return self.has_ad_config and getattr(self, "_supports_continuous", False)
