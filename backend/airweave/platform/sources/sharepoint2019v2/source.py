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

Continuous sync:
- Uses SharePoint GetChanges API (site collection level change tokens)
- Tracks changes via tokens valid ~60 days; falls back to full sync on expiry
- ACL changes tracked via AD DirSync control
"""

import asyncio
import json
from dataclasses import dataclass
from typing import Any, AsyncGenerator, Dict, List, Optional, Union

from airweave.platform.access_control.schemas import MembershipTuple
from airweave.platform.configs.auth import SharePoint2019V2AuthConfig
from airweave.platform.configs.config import SharePoint2019V2Config
from airweave.platform.cursors.sharepoint2019v2 import SharePoint2019V2Cursor
from airweave.platform.decorators import source
from airweave.platform.entities._base import BaseEntity, Breadcrumb
from airweave.platform.entities.sharepoint2019v2 import (
    SharePoint2019V2FileDeletionEntity,
    SharePoint2019V2ItemDeletionEntity,
)
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

# Maximum concurrent file downloads
MAX_CONCURRENT_FILE_DOWNLOADS = 10

# Items to collect before parallel-processing a batch
ITEM_BATCH_SIZE = 50


@dataclass
class PendingFileDownload:
    """Holds a file entity that needs its content downloaded."""

    entity: Any  # SharePoint2019V2FileEntity
    site_url: str


@source(
    name="SharePoint 2019 On-Premise V2",
    short_name="sharepoint2019v2",
    auth_methods=[AuthenticationMethod.DIRECT],
    oauth_type=None,
    auth_config_class=SharePoint2019V2AuthConfig,
    config_class=SharePoint2019V2Config,
    supports_continuous=True,
    cursor_class=SharePoint2019V2Cursor,
    supports_access_control=True,
    feature_flag="sharepoint_2019_v2",
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

    # -------------------------------------------------------------------------
    # Entity Generation
    # -------------------------------------------------------------------------

    # -------------------------------------------------------------------------
    # Parallel File Downloads
    # -------------------------------------------------------------------------

    async def _download_files_parallel(
        self,
        pending: List[PendingFileDownload],
        client,
    ) -> List[BaseEntity]:
        """Download file contents in parallel with bounded concurrency.

        Args:
            pending: List of PendingFileDownload items.
            client: httpx AsyncClient instance.

        Returns:
            List of successfully downloaded file entities.
        """
        semaphore = asyncio.Semaphore(MAX_CONCURRENT_FILE_DOWNLOADS)
        results: List[BaseEntity] = []

        async def download_one(item: PendingFileDownload):
            async with semaphore:
                try:
                    entity = await self._download_and_save_file(item.entity, client, item.site_url)
                    results.append(entity)
                except FileSkippedException:
                    pass
                except EntityProcessingError as e:
                    self.logger.warning(f"Skipping file download: {e}")

        tasks = [asyncio.create_task(download_one(p)) for p in pending]
        await asyncio.gather(*tasks, return_exceptions=True)
        return results

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
        """Process a batch of items, downloading files in parallel.

        Separates files from non-file items. Non-file items are built and
        yielded immediately. File items are built first, then their contents
        are downloaded in parallel before yielding.

        Args:
            items_batch: List of item metadata dicts to process.
            site_url: Base URL of the site.
            list_id: GUID of the parent list.
            breadcrumbs: Parent breadcrumb trail.
            is_doc_lib: Whether this is a document library.
            client: httpx AsyncClient instance.
            ldap_client: LDAPClient for SID resolution.

        Yields:
            BaseEntity instances (items yielded immediately, files after download).
        """
        pending_files: List[PendingFileDownload] = []
        non_file_entities: List[BaseEntity] = []

        for item_meta in items_batch:
            fs_obj_type = item_meta.get("FileSystemObjectType")
            if fs_obj_type is None or fs_obj_type == 1:  # Skip missing/folders
                continue

            is_file = is_doc_lib and fs_obj_type == 0

            if is_file:
                try:
                    file_entity = await build_file_entity(
                        item_meta, site_url, list_id, breadcrumbs, ldap_client
                    )
                    self._track_entity_ad_groups(file_entity)
                    pending_files.append(PendingFileDownload(entity=file_entity, site_url=site_url))
                except EntityProcessingError as e:
                    self.logger.warning(f"Skipping file: {e}")
            else:
                try:
                    item_entity = await build_item_entity(
                        item_meta, site_url, list_id, breadcrumbs, ldap_client
                    )
                    self._track_entity_ad_groups(item_entity)
                    non_file_entities.append(item_entity)
                except EntityProcessingError as e:
                    self.logger.warning(f"Skipping item: {e}")

        # Yield non-file entities immediately
        for entity in non_file_entities:
            yield entity

        # Download files in parallel, then yield
        if pending_files:
            self.logger.debug(
                f"Downloading {len(pending_files)} files in parallel "
                f"(max concurrency: {MAX_CONCURRENT_FILE_DOWNLOADS})"
            )
            downloaded = await self._download_files_parallel(pending_files, client)
            for entity in downloaded:
                yield entity

    # -------------------------------------------------------------------------
    # Sync Decision Logic
    # -------------------------------------------------------------------------

    def _should_do_full_sync(self) -> tuple:
        """Decide whether to do a full or incremental entity sync.

        Checks cursor state to determine the sync strategy.

        Returns:
            Tuple of (is_full_sync: bool, reason: str).
        """
        cursor_data = self.cursor.data if self.cursor else {}

        if not cursor_data:
            return True, "no cursor data (first sync)"

        token = cursor_data.get("site_collection_change_token", "")
        if not token:
            return True, "no change token stored"

        if cursor_data.get("full_sync_required", True):
            return True, "full_sync_required flag is set"

        # Check token expiry using the cursor schema helper
        schema = SharePoint2019V2Cursor(**cursor_data)
        if schema.is_entity_token_expired():
            return True, "change token expired (>55 days old)"

        if schema.needs_periodic_full_sync():
            return True, "periodic full sync needed (>7 days since last)"

        return False, "incremental sync (valid token)"

    # -------------------------------------------------------------------------
    # Entity Generation (dispatches to full or incremental)
    # -------------------------------------------------------------------------

    async def generate_entities(self) -> AsyncGenerator[BaseEntity, None]:
        """Generate entities from SharePoint, using incremental sync when possible.

        On the first run (no cursor), performs a full crawl.
        On subsequent runs, uses the GetChanges API for incremental updates.

        Yields:
            BaseEntity instances (Site, List, Item, File, or Deletion markers)
        """
        is_full, reason = self._should_do_full_sync()
        self.logger.info(f"Sync strategy: {'FULL' if is_full else 'INCREMENTAL'} ({reason})")

        if is_full:
            async for entity in self._full_sync():
                yield entity
        else:
            async for entity in self._incremental_sync():
                yield entity

    async def _full_sync(self) -> AsyncGenerator[BaseEntity, None]:  # noqa: C901
        """Full crawl of the SharePoint site hierarchy.

        After completing the crawl, captures the current change token
        for use by incremental syncs on subsequent runs.

        Yields:
            BaseEntity instances (Site, List, Item, File)
        """
        from airweave.platform.sources.sharepoint2019v2.ldap import LDAPClient

        ldap_client = LDAPClient(
            server=self._ad_server,
            username=self._ad_username,
            password=self._ad_password,
            domain=self._ad_domain,
            search_base=self._ad_search_base,
            logger=self.logger,
        )

        entity_count = 0

        try:
            async with self.http_client(verify=False) as client:
                sp_client = self._create_client()

                # Capture initial change token BEFORE starting the crawl
                # so we don't miss changes that happen during the sync
                try:
                    initial_token = await sp_client.get_current_change_token(client, self._site_url)
                    self.logger.info(f"Captured initial change token: ...{initial_token[-20:]}")
                except Exception as e:
                    self.logger.warning(f"Could not get change token: {e}")
                    initial_token = ""

                # Queue of (site_url, parent_breadcrumbs) to process
                sites_to_process: List[tuple] = [(self._site_url, [])]
                processed_sites: set = set()

                while sites_to_process:
                    current_site_url, parent_breadcrumbs = sites_to_process.pop(0)

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
                        self._track_entity_ad_groups(site_entity)
                        yield site_entity
                        entity_count += 1

                        site_breadcrumb = Breadcrumb(
                            entity_id=site_entity.site_id,
                            name=site_entity.title,
                            entity_type="SharePoint2019V2SiteEntity",
                        )
                        current_site_breadcrumbs = parent_breadcrumbs + [site_breadcrumb]
                    except Exception as e:
                        self.logger.error(f"Skipping site {current_site_url}: {e}")
                        continue

                    # Process lists
                    async for list_meta in sp_client.discover_lists(client, current_site_url):
                        try:
                            list_entity = await build_list_entity(
                                list_meta,
                                current_site_url,
                                current_site_breadcrumbs,
                                ldap_client,
                            )
                            self._track_entity_ad_groups(list_entity)
                            yield list_entity
                            entity_count += 1

                            list_breadcrumb = Breadcrumb(
                                entity_id=list_entity.list_id,
                                name=list_entity.title,
                                entity_type="SharePoint2019V2ListEntity",
                            )
                            list_breadcrumbs = current_site_breadcrumbs + [list_breadcrumb]

                            is_doc_lib = list_entity.base_template == 101
                            list_guid = list_meta["Id"]

                            # Collect items into batches for parallel file downloads
                            batch: List[Dict[str, Any]] = []
                            async for item_meta in sp_client.discover_items(
                                client, current_site_url, list_guid
                            ):
                                batch.append(item_meta)

                                if len(batch) >= ITEM_BATCH_SIZE:
                                    async for entity in self._process_items_batch(
                                        batch,
                                        current_site_url,
                                        list_guid,
                                        list_breadcrumbs,
                                        is_doc_lib,
                                        client,
                                        ldap_client,
                                    ):
                                        yield entity
                                        entity_count += 1
                                    batch = []

                            # Process remaining items in last partial batch
                            if batch:
                                async for entity in self._process_items_batch(
                                    batch,
                                    current_site_url,
                                    list_guid,
                                    list_breadcrumbs,
                                    is_doc_lib,
                                    client,
                                    ldap_client,
                                ):
                                    yield entity
                                    entity_count += 1

                        except EntityProcessingError as e:
                            self.logger.warning(f"Skipping list: {e}")
                            continue

                    # Discover subsites
                    async for subsite in sp_client.discover_subsites(client, current_site_url):
                        subsite_url = subsite.get("Url", "").rstrip("/")
                        if subsite_url:
                            sites_to_process.append((subsite_url, current_site_breadcrumbs))

                # Update cursor with change token
                if self.cursor and initial_token:
                    self.cursor.update(
                        site_collection_change_token=initial_token,
                        site_collection_url=self._site_url,
                        full_sync_required=False,
                        total_entities_synced=entity_count,
                    )
                    # Use the schema helper for timestamp bookkeeping
                    schema = SharePoint2019V2Cursor(**self.cursor.data)
                    schema.update_entity_cursor(
                        new_token=initial_token,
                        changes_count=entity_count,
                        is_full_sync=True,
                    )
                    self.cursor.update(
                        last_entity_sync_timestamp=schema.last_entity_sync_timestamp,
                        last_full_sync_timestamp=schema.last_full_sync_timestamp,
                        last_entity_changes_count=entity_count,
                    )

                self.logger.info(f"Full sync complete: {entity_count} entities")

        finally:
            ldap_client.close()

    async def _incremental_sync(self) -> AsyncGenerator[BaseEntity, None]:  # noqa: C901
        """Incremental sync using SharePoint GetChanges API.

        Fetches only changes since the last stored change token.
        Resolves each change to the appropriate entity and yields it.

        For deleted items, yields DeletionEntity markers.

        Yields:
            BaseEntity instances or DeletionEntity markers.
        """
        from airweave.platform.sources.sharepoint2019v2.ldap import LDAPClient

        cursor_data = self.cursor.data if self.cursor else {}
        change_token = cursor_data.get("site_collection_change_token", "")

        if not change_token:
            self.logger.warning("No change token for incremental sync, falling back to full")
            async for entity in self._full_sync():
                yield entity
            return

        ldap_client = LDAPClient(
            server=self._ad_server,
            username=self._ad_username,
            password=self._ad_password,
            domain=self._ad_domain,
            search_base=self._ad_search_base,
            logger=self.logger,
        )

        changes_processed = 0

        try:
            async with self.http_client(verify=False) as client:
                sp_client = self._create_client()

                try:
                    changes, new_token = await sp_client.get_site_collection_changes(
                        client, self._site_url, change_token
                    )
                except Exception as e:
                    self.logger.error(f"GetChanges failed: {e}. Marking full sync required.")
                    if self.cursor:
                        self.cursor.update(full_sync_required=True)
                    return

                self.logger.info(f"Processing {len(changes)} changes from GetChanges API")

                for change in changes:
                    change_type = change.get("ChangeType", 0)
                    item_id = change.get("ItemId", 0)
                    list_id = change.get("ListId", "")

                    if not list_id or not item_id:
                        continue

                    # Delete: yield deletion marker with correct entity type
                    if change_type == 3:  # Delete
                        # Resolve list type to determine file vs item deletion
                        list_data = await sp_client.get_list_by_id(client, self._site_url, list_id)
                        is_doc_lib = list_data.get("BaseTemplate", 0) == 101 if list_data else False

                        if is_doc_lib:
                            sp_entity_id = f"sp2019v2:file:{list_id}:{item_id}"
                            yield SharePoint2019V2FileDeletionEntity(
                                list_id=list_id,
                                item_id=item_id,
                                sp_entity_id=sp_entity_id,
                                label=f"Deleted file {item_id} from {list_id}",
                            )
                        else:
                            sp_entity_id = f"sp2019v2:item:{list_id}:{item_id}"
                            yield SharePoint2019V2ItemDeletionEntity(
                                list_id=list_id,
                                item_id=item_id,
                                sp_entity_id=sp_entity_id,
                                label=f"Deleted item {item_id} from {list_id}",
                            )
                        changes_processed += 1
                        continue

                    # Add, Update, Rename, Restore: fetch the current item
                    if change_type in (1, 2, 4, 7):
                        item_data = await sp_client.get_item_by_id(
                            client, self._site_url, list_id, item_id
                        )
                        if not item_data:
                            self.logger.debug(
                                f"Changed item {item_id} in list {list_id} no longer exists"
                            )
                            continue

                        # Determine if this is a doc library item
                        list_data = await sp_client.get_list_by_id(client, self._site_url, list_id)
                        is_doc_lib = list_data.get("BaseTemplate", 0) == 101 if list_data else False

                        async for entity in self._process_item(
                            item_data,
                            self._site_url,
                            list_id,
                            [],  # No breadcrumbs for incremental items
                            is_doc_lib,
                            client,
                            ldap_client,
                        ):
                            yield entity
                            changes_processed += 1

                # Update cursor
                if self.cursor:
                    self.cursor.update(
                        site_collection_change_token=new_token,
                        last_entity_changes_count=changes_processed,
                    )
                    schema = SharePoint2019V2Cursor(**self.cursor.data)
                    schema.update_entity_cursor(
                        new_token=new_token,
                        changes_count=changes_processed,
                        is_full_sync=False,
                    )
                    self.cursor.update(
                        last_entity_sync_timestamp=schema.last_entity_sync_timestamp,
                    )

                self.logger.info(
                    f"Incremental sync complete: {changes_processed} changes processed"
                )

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
            list_id: GUID of the parent list
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
        ldap_client = self._create_ldap_client()
        # Track AD groups already expanded (to avoid duplicate work)
        expanded_ad_groups: set = set()

        try:
            async with self.http_client(verify=False) as client:
                sp_client = self._create_client()

                # Phase 1: Process SharePoint site groups
                async for sp_group in sp_client.get_site_groups(client, self._site_url):
                    group_id = sp_group.get("Id")
                    group_title = sp_group.get("Title", "Unknown Group")

                    if not group_id:
                        continue

                    self.logger.debug(f"Processing SP group: {group_title}")
                    sp_group_id = format_sp_group_id(group_title)

                    async for member in sp_client.get_group_members(
                        client, self._site_url, group_id
                    ):
                        async for membership in self._process_sp_group_member(
                            member, sp_group_id, group_title, ldap_client
                        ):
                            yield membership
                            membership_count += 1
                            # Track AD groups already expanded via SP group membership
                            if membership.group_id.startswith("ad:"):
                                expanded_ad_groups.add(membership.group_id)

            # Phase 2: Expand item-level AD groups that weren't in SP groups
            async for membership in self._expand_item_level_ad_groups(
                ldap_client, expanded_ad_groups
            ):
                yield membership
                membership_count += 1

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
    # Incremental ACL Support
    # -------------------------------------------------------------------------

    def _should_do_full_acl_sync(self) -> tuple:
        """Decide whether to do a full or incremental ACL sync.

        Returns:
            Tuple of (is_full: bool, reason: str).
        """
        cursor_data = self.cursor.data if self.cursor else {}

        if not cursor_data:
            return True, "no cursor data (first ACL sync)"

        cookie = cursor_data.get("acl_dirsync_cookie", "")
        if not cookie:
            return True, "no DirSync cookie stored"

        schema = SharePoint2019V2Cursor(**cursor_data)
        if schema.is_acl_cookie_expired():
            return True, "DirSync cookie expired (>55 days old)"

        return False, "incremental ACL sync (valid cookie)"

    async def get_acl_changes(self, dirsync_cookie: str = ""):
        """Get incremental ACL membership changes via AD DirSync.

        Called by the ACL pipeline when incremental ACL sync is possible.

        Args:
            dirsync_cookie: Base64-encoded DirSync cookie. If empty, reads
                from cursor data. Callers can pass explicitly to override.

        Returns:
            DirSyncResult with changes, new cookie, and modified group IDs.
        """
        from airweave.platform.sources.sharepoint2019v2.ldap import LDAPClient

        # Use provided cookie, or fall back to cursor data
        if not dirsync_cookie:
            cursor_data = self.cursor.data if self.cursor else {}
            dirsync_cookie = cursor_data.get("acl_dirsync_cookie", "")

        ldap_client = LDAPClient(
            server=self._ad_server,
            username=self._ad_username,
            password=self._ad_password,
            domain=self._ad_domain,
            search_base=self._ad_search_base,
            logger=self.logger,
        )

        try:
            await ldap_client.connect()
            result = await ldap_client.get_membership_changes(cookie_b64=dirsync_cookie)
            ldap_client.log_cache_stats()
            return result
        finally:
            ldap_client.close()

    def supports_incremental_acl(self) -> bool:
        """Whether this source supports incremental ACL sync via DirSync."""
        return self.has_ad_config and getattr(self, "_supports_continuous", False)
