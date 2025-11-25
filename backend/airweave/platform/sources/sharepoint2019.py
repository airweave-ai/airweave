"""SharePoint 2019 On-Premise source implementation using REST API + LDAP.

Retrieves data from SharePoint 2019 On-Premise, including:
 - Lists (document libraries and custom lists)
 - List Items (rows of data or file metadata)
 - Files (downloadable documents)

And extracts access control from:
 - SharePoint Groups (cannot contain SP groups)
 - Active Directory Groups (can be nested)
 - Active Directory Users

Reference:
  SharePoint 2019 REST API: https://docs.microsoft.com/en-us/sharepoint/dev/sp-add-ins/get-to-know-the-sharepoint-rest-service
  SharePoint 2019 uses OData v3 (different from Microsoft Graph)
"""

import hashlib
import os
import ssl
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx
from httpx_ntlm import HttpNtlmAuth
from ldap3 import BASE, SUBTREE, Connection, Server, Tls
from tenacity import retry, stop_after_attempt

from airweave.platform.access_control.schemas import AccessControlMembership
from airweave.platform.decorators import source
from airweave.platform.downloader import FileSkippedException
from airweave.platform.entities._base import AccessControl, BaseEntity, Breadcrumb
from airweave.platform.entities.sharepoint2019 import (
    SharePoint2019FileEntity,
    SharePoint2019ListEntity,
    SharePoint2019ListItemEntity,
)
from airweave.platform.sources._base import BaseSource
from airweave.platform.sources.retry_helpers import (
    retry_if_rate_limit_or_timeout,
    wait_rate_limit_with_backoff,
)
from airweave.schemas.source_connection import AuthenticationMethod


def _ensure_md4_support() -> None:
    """Ensure hashlib can create MD4 digests required for NTLM."""
    try:
        hashlib.new("md4", b"test")
    except ValueError:
        from Crypto.Hash import MD4

        _original_new = hashlib.new

        def _patched_new(name, data=b"", **kwargs):
            if name.lower() == "md4":
                digest = MD4.new()
                if data:
                    digest.update(data)
                return digest
            return _original_new(name, data, **kwargs)

        hashlib.new = _patched_new


_ensure_md4_support()


@source(
    name="SharePoint 2019 On-Premise",
    short_name="sharepoint2019",
    auth_methods=[AuthenticationMethod.DIRECT],
    oauth_type=None,
    auth_config_class="SharePoint2019AuthConfig",
    config_class="SharePoint2019Config",
    labels=["File Storage", "Collaboration", "On-Premise"],
    supports_continuous=False,
)
class SharePoint2019Source(BaseSource):
    """SharePoint 2019 On-Premise connector using NTLM + LDAP.

    Syncs data from a specific SharePoint site including:
    - All lists and document libraries
    - List items and file metadata
    - File downloads using the download service

    Extracts access control from:
    - SharePoint Groups (first-level principals)
    - Active Directory Groups (expanded recursively)
    - Active Directory Users

    Uses LoginName for all principals to ensure consistent identity tracking
    across SharePoint and Active Directory.
    """

    def __init__(self):
        """Initialize SharePoint 2019 source."""
        super().__init__()
        self.site_url: Optional[str] = None
        self.sp_username: Optional[str] = None
        self.sp_password: Optional[str] = None
        self.sp_domain: Optional[str] = None
        self.ad_server: Optional[str] = None
        self.ad_username: Optional[str] = None
        self.ad_password: Optional[str] = None
        self.ad_domain: Optional[str] = None
        self.ad_search_base: Optional[str] = None
        self._ad_connection: Optional[Connection] = None
        self._ntlm_auth: Optional[HttpNtlmAuth] = None

    @classmethod
    async def create(
        cls, credentials: Dict[str, Any], config: Optional[Dict[str, Any]] = None
    ) -> "SharePoint2019Source":
        """Create SharePoint 2019 source with NTLM + LDAP credentials.

        Args:
            credentials: Dict containing:
                - sharepoint_username: Windows username for NTLM
                - sharepoint_password: Password for NTLM
                - sharepoint_domain: Optional Windows domain
                - ad_username: AD username for LDAP
                - ad_password: AD password for LDAP
                - ad_domain: AD domain
            config: Dict containing:
                - site_url: Full URL of the SharePoint site
                - ad_server: AD server hostname or IP
                - ad_search_base: LDAP search base DN

        Returns:
            Configured SharePoint2019Source instance
        """
        instance = cls()

        credentials_dict = cls._coerce_to_dict(credentials)
        config_dict = cls._coerce_to_dict(config)

        # SharePoint credentials
        instance.sp_username = credentials_dict.get("sharepoint_username")
        instance.sp_password = credentials_dict.get("sharepoint_password")
        instance.sp_domain = credentials_dict.get("sharepoint_domain")

        # AD credentials
        instance.ad_username = credentials_dict.get("ad_username")
        instance.ad_password = credentials_dict.get("ad_password")
        instance.ad_domain = credentials_dict.get("ad_domain")

        # Config
        instance.site_url = config_dict.get("site_url", "").rstrip("/")
        instance.ad_server = config_dict.get("ad_server")
        instance.ad_search_base = config_dict.get("ad_search_base")

        return instance

    @staticmethod
    def _coerce_to_dict(data: Optional[Any]) -> Dict[str, Any]:
        """Convert config/auth inputs (dict or BaseModel) to a dict."""
        if data is None:
            return {}
        if isinstance(data, dict):
            return data
        if hasattr(data, "model_dump"):
            return data.model_dump()
        return dict(data)

    def _create_ntlm_auth(self) -> HttpNtlmAuth:
        """Create NTLM authentication object for SharePoint API calls."""
        if self._ntlm_auth is None:
            username = (
                f"{self.sp_domain}\\{self.sp_username}" if self.sp_domain else self.sp_username
            )
            self._ntlm_auth = HttpNtlmAuth(username, self.sp_password)
        return self._ntlm_auth

    async def _connect_to_ad(self) -> Connection:
        """Establish LDAP connection to Active Directory."""
        if self._ad_connection and self._ad_connection.bound:
            return self._ad_connection

        # Strip protocol prefix if present
        server_clean = self.ad_server.replace("ldap://", "").replace("ldaps://", "")

        # Try LDAPS first (port 636), fallback to STARTTLS on 389
        tls_config = Tls(validate=ssl.CERT_NONE, version=ssl.PROTOCOL_TLSv1_2)

        # Try LDAPS
        try:
            if ":" in server_clean:
                server_url = server_clean
            else:
                server_url = f"{server_clean}:636"

            server = Server(server_url, get_info="ALL", use_ssl=True, tls=tls_config)
            user_dn = f"{self.ad_domain}\\{self.ad_username}"
            conn = Connection(server, user=user_dn, password=self.ad_password, auto_bind=True)
            self._ad_connection = conn
            self.logger.info(f"Connected to AD via LDAPS: {server_url}")
            return conn
        except Exception as ldaps_error:
            self.logger.debug(f"LDAPS failed, trying STARTTLS: {ldaps_error}")

            # Fallback to STARTTLS
            try:
                server_url_starttls = server_clean if ":" in server_clean else server_clean
                server = Server(server_url_starttls, get_info="ALL", tls=tls_config)
                user_dn = f"{self.ad_domain}\\{self.ad_username}"
                conn = Connection(server, user=user_dn, password=self.ad_password, auto_bind=False)
                conn.open()
                conn.start_tls()
                conn.bind()
                self._ad_connection = conn
                self.logger.info(f"Connected to AD via STARTTLS: {server_url_starttls}")
                return conn
            except Exception as starttls_error:
                self.logger.error(
                    "Both LDAPS and STARTTLS failed: LDAPS=%s, STARTTLS=%s",
                    ldaps_error,
                    starttls_error,
                )
                raise Exception(f"Could not connect to AD: {starttls_error}")

    @retry(
        stop=stop_after_attempt(3),
        retry=retry_if_rate_limit_or_timeout,
        wait=wait_rate_limit_with_backoff,
        reraise=True,
    )
    async def _sp_get(self, endpoint: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """Make authenticated GET request to SharePoint REST API.

        Args:
            endpoint: REST API endpoint (e.g., '/web/lists')
            params: Optional query parameters

        Returns:
            JSON response from SharePoint
        """
        url = f"{self.site_url}/_api{endpoint}"
        auth = self._create_ntlm_auth()
        headers = {
            "Accept": "application/json;odata=verbose",
            "Content-Type": "application/json;odata=verbose",
        }

        try:
            timeout = httpx.Timeout(30.0, connect=30.0, read=30.0)
            async with self.http_client(
                auth=auth,
                verify=False,
                timeout=timeout,
            ) as client:
                response = await client.get(url, headers=headers, params=params)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as http_err:
            resp = http_err.response
            status_code = resp.status_code if resp is not None else "unknown"
            error_snippet = resp.text if resp is not None and resp.text else "<empty body>"
            self.logger.error(
                "SharePoint API %s returned %s. Response body snippet: %s",
                url,
                status_code,
                error_snippet,
            )
            raise
        except Exception as e:
            self.logger.error(
                "Error calling SharePoint API %s: %s (%s)",
                url,
                e,
                type(e).__name__,
                exc_info=True,
            )
            raise

    async def _sp_get_file_content(self, server_relative_url: str) -> bytes:
        """Download file content from SharePoint.

        Args:
            server_relative_url: Server-relative URL of the file

        Returns:
            File content as bytes
        """
        url = f"{self.site_url}/_api/web/GetFileByServerRelativeUrl('{server_relative_url}')/$value"
        auth = self._create_ntlm_auth()

        try:
            timeout = httpx.Timeout(60.0, connect=30.0, read=60.0)
            async with self.http_client(
                auth=auth,
                verify=False,
                timeout=timeout,
            ) as client:
                response = await client.get(url)
            response.raise_for_status()
            return response.content
        except httpx.HTTPStatusError as http_err:
            resp = http_err.response
            status_code = resp.status_code if resp is not None else "unknown"
            error_snippet = resp.text[:1000] if resp is not None and resp.text else "<empty body>"
            self.logger.error(
                "Failed to download %s (status=%s). Response snippet: %s",
                server_relative_url,
                status_code,
                error_snippet,
            )
            raise
        except Exception as e:
            self.logger.error(f"Error downloading file {server_relative_url}: {e}")
            raise

    async def _get_lists(self) -> AsyncGenerator[Dict[str, Any], None]:
        """Get all lists in the site using pagination."""
        endpoint = "/web/lists"
        params = {
            "$filter": "Hidden eq false",  # Skip hidden system lists
            "$top": 100,
        }

        while True:
            data = await self._sp_get(endpoint, params)
            results = data.get("d", {}).get("results", [])

            for list_obj in results:
                yield list_obj

            # Handle pagination
            next_link = data.get("d", {}).get("__next")
            if not next_link:
                break
            # Extract endpoint from next link
            endpoint = next_link.replace(f"{self.site_url}/_api", "")
            params = None  # Params are in the next link

    async def _get_list_items(
        self, list_id: str, is_document_library: bool = False
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Get all items in a list using pagination.

        Args:
            list_id: The GUID of the list
            is_document_library: If True, expands File properties to get file metadata
                                 including ServerRelativeUrl, Name, etc.

        Expansions used:
            - FieldValuesAsText: Returns text representations of all field values,
              which is essential for lookup fields, person fields, choice fields, etc.
              Without this, these fields return IDs instead of display values.
            - File (for document libraries): Returns file metadata including
              ServerRelativeUrl, Name, Length, UniqueId, etc.
        """
        endpoint = f"/web/lists(guid'{list_id}')/items"
        params = {
            "$top": 100,
        }

        # Always expand FieldValuesAsText to get human-readable values for:
        # - Lookup fields (shows display value instead of ID)
        # - Person/Group fields (shows name instead of ID)
        # - Choice fields (shows selected value)
        # - Managed Metadata (shows term value)
        # For document libraries, also expand File for file metadata
        if is_document_library:
            params["$expand"] = "File,FieldValuesAsText"
        else:
            params["$expand"] = "FieldValuesAsText"

        while True:
            try:
                data = await self._sp_get(endpoint, params)
                results = data.get("d", {}).get("results", [])

                for item in results:
                    yield item

                # Handle pagination
                next_link = data.get("d", {}).get("__next")
                if not next_link:
                    break
                endpoint = next_link.replace(f"{self.site_url}/_api", "")
                params = None
            except Exception as e:
                self.logger.error(f"Error getting items for list {list_id}: {e}")
                break

    async def _get_role_assignments(self, list_id: str, item_id: int) -> List[Dict[str, Any]]:
        """Get role assignments (permissions) for a list item.

        Returns list of principals with READ permission.
        """
        endpoint = f"/web/lists(guid'{list_id}')/items({item_id})/roleassignments"
        params = {
            "$expand": "Member,RoleDefinitionBindings",
        }

        try:
            data = await self._sp_get(endpoint, params)
            assignments = data.get("d", {}).get("results", [])

            # Filter for READ permissions (BasePermissions.Low & 1)
            read_principals = []
            for assignment in assignments:
                member = assignment.get("Member", {})
                bindings = assignment.get("RoleDefinitionBindings", {}).get("results", [])

                # Check if any role has READ permission (bit 1 in Low)
                has_read = False
                for role in bindings:
                    perms = role.get("BasePermissions", {})
                    low = int(perms.get("Low", 0))
                    if low & 1:  # ViewListItems permission
                        has_read = True
                        break

                if has_read:
                    read_principals.append(member)

            return read_principals
        except Exception as e:
            self.logger.warning(
                f"Could not get role assignments for list {list_id} item {item_id}: {e}"
            )
            return []

    def _build_access_control(self, principals: List[Dict[str, Any]]) -> AccessControl:
        """Build AccessControl object from SharePoint principal list.

        Uses LoginName for all principals to ensure consistent identity tracking.
        """
        viewers = []

        for principal in principals:
            principal_type = principal.get("PrincipalType", 0)
            login_name = principal.get("LoginName", "")

            if not login_name:
                continue

            if principal_type == 1:  # User
                # Use LoginName directly (e.g., "i:0#.w|DOMAIN\username")
                viewers.append(f"user:{login_name}")
            elif principal_type == 8:  # SharePoint Group
                # Use group:sp:<GroupId> to distinguish from AD groups
                group_id = principal.get("Id")
                if group_id:
                    viewers.append(f"group:sp:{group_id}")
            elif principal_type == 4:  # AD Security Group
                # Use LoginName (e.g., "c:0+.w|DOMAIN\groupname")
                viewers.append(f"group:ad:{login_name}")

        return AccessControl(viewers=viewers)

    def _extract_field_values(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Extract and merge field values from a list item.

        SharePoint returns field values in two places:
        1. Direct item properties (may contain IDs for lookup/person fields)
        2. FieldValuesAsText (contains text representations of all fields)

        This method merges both, preferring the text values from FieldValuesAsText
        for human-readable output while keeping both available.

        Args:
            item: Raw list item from SharePoint API

        Returns:
            Dictionary with merged field values, including:
            - All direct properties
            - text_values: Dict of text representations from FieldValuesAsText
        """
        # Get FieldValuesAsText if available (expanded in the query)
        field_values_as_text = item.get("FieldValuesAsText", {})
        if "__deferred" in field_values_as_text:
            # FieldValuesAsText wasn't expanded, just has a deferred reference
            field_values_as_text = {}

        # Remove metadata keys from FieldValuesAsText
        text_values = {
            k: v
            for k, v in field_values_as_text.items()
            if not k.startswith("__") and k != "odata.type"
        }

        # Build a clean fields dictionary
        # Include important direct properties and add text_values as a nested dict
        fields = {}

        # Copy relevant direct properties (excluding metadata and deferred objects)
        skip_keys = {
            "__metadata",
            "File",
            "FieldValuesAsText",
            "FieldValuesForEdit",
            "FirstUniqueAncestorSecurableObject",
            "RoleAssignments",
            "AttachmentFiles",
            "ContentType",
            "ParentList",
            "Folder",
        }
        for key, value in item.items():
            if key in skip_keys:
                continue
            # Skip deferred navigation properties
            if isinstance(value, dict) and "__deferred" in value:
                continue
            fields[key] = value

        # Add text values as a nested key for easy access
        if text_values:
            fields["_text_values"] = text_values

        return fields

    def _get_item_title(self, item: Dict[str, Any], file_obj: Dict[str, Any], item_id: Any) -> str:
        """Extract the best available title for a list item.

        Priority:
        1. File.Name (for documents)
        2. FieldValuesAsText.Title (text representation)
        3. Item.Title (direct property)
        4. Item.FileLeafRef (file name for documents)
        5. Fallback to "Item {id}"

        Args:
            item: Raw list item from SharePoint API
            file_obj: Expanded File object (may be empty)
            item_id: Item ID for fallback

        Returns:
            Best available title string
        """
        # For documents, prefer the file name
        if file_obj:
            file_name = file_obj.get("Name")
            if file_name:
                return file_name

        # Try FieldValuesAsText.Title (human-readable)
        field_values_as_text = item.get("FieldValuesAsText", {})
        if not isinstance(field_values_as_text, dict) or "__deferred" in field_values_as_text:
            field_values_as_text = {}

        text_title = field_values_as_text.get("Title")
        if text_title:
            return text_title

        # Fall back to direct Title property
        direct_title = item.get("Title")
        if direct_title:
            return direct_title

        # Try FileLeafRef (file name)
        file_leaf_ref = item.get("FileLeafRef")
        if file_leaf_ref:
            return file_leaf_ref

        # Last resort fallback
        return f"Item {item_id}"

    async def _generate_list_entities(self) -> AsyncGenerator[SharePoint2019ListEntity, None]:
        """Generate list entities for all lists in the site."""
        self.logger.info("Generating list entities...")

        async for list_obj in self._get_lists():
            list_id = list_obj.get("Id")
            title = list_obj.get("Title", "Untitled List")

            self.logger.debug(f"Processing list: {title} ({list_id})")

            # Parse timestamps
            created = self._parse_datetime(list_obj.get("Created"))
            modified = self._parse_datetime(list_obj.get("LastItemModifiedDate"))

            yield SharePoint2019ListEntity(
                breadcrumbs=[],
                id=list_id,
                name=title,
                title=title,
                created_at=created,
                updated_at=modified,
                description=list_obj.get("Description"),
                base_template=list_obj.get("BaseTemplate"),
                item_count=list_obj.get("ItemCount"),
                server_relative_url=list_obj.get("RootFolder", {}).get("ServerRelativeUrl"),
                enable_versioning=list_obj.get("EnableVersioning"),
                hidden=list_obj.get("Hidden"),
                raw_metadata=list_obj,
            )

    async def _generate_list_item_and_file_entities(
        self, list_entity: SharePoint2019ListEntity
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate list item entities and file entities for a list.

        For document libraries (BaseTemplate=101), also download files.
        """
        list_id = list_entity.id
        is_document_library = list_entity.base_template == 101

        list_breadcrumb = Breadcrumb(
            entity_id=list_id,
            name=list_entity.title,
            entity_type="SharePoint2019ListEntity",
        )

        # Pass is_document_library to expand File properties when needed
        async for item in self._get_list_items(list_id, is_document_library=is_document_library):
            item_id = item.get("Id")
            file_system_obj_type = item.get("FileSystemObjectType", 0)

            # Skip folders
            if file_system_obj_type == 1:
                continue

            # Get expanded File object (populated when $expand=File is used)
            file_obj = item.get("File", {})
            # Handle deferred File object (not expanded) - check for __deferred key
            if "__deferred" in file_obj:
                file_obj = {}

            # Extract field values (merges raw values with FieldValuesAsText for better data)
            fields = self._extract_field_values(item)

            # Extract title using best available source (File.Name, FieldValuesAsText, etc.)
            title = self._get_item_title(item, file_obj, item_id)

            # Get access control
            principals = await self._get_role_assignments(list_id, item_id)
            access = self._build_access_control(principals)

            # Parse timestamps
            created = self._parse_datetime(item.get("Created"))
            modified = self._parse_datetime(item.get("Modified"))

            # For document libraries, also yield file entity
            if is_document_library and file_system_obj_type == 0:
                # Get file metadata from expanded File object
                # ServerRelativeUrl is the key property for file access
                file_ref = file_obj.get("ServerRelativeUrl") or item.get("FileRef")

                if file_ref and file_obj:
                    try:
                        # File metadata is already available from the expanded File object
                        file_name = file_obj.get("Name", title)
                        file_length = int(file_obj.get("Length", 0) or 0)

                        # Determine file type and MIME type
                        _, ext = os.path.splitext(file_name)
                        ext = ext.lower().lstrip(".")

                        # Create file entity using expanded File properties
                        file_entity = SharePoint2019FileEntity(
                            breadcrumbs=[list_breadcrumb],
                            id=file_obj.get("UniqueId", str(item_id)),
                            name=file_name,
                            title=title,
                            created_at=created,
                            updated_at=modified,
                            access=access,
                            url=f"{self.site_url}{file_ref}",
                            size=file_length,
                            file_type=ext or "file",
                            mime_type=f"application/{ext}" if ext else "application/octet-stream",
                            server_relative_url=file_ref,
                            length=file_length,
                            time_created=file_obj.get("TimeCreated"),
                            time_last_modified=file_obj.get("TimeLastModified"),
                            list_item_id=item_id,
                            list_id=list_id,
                            author=file_obj.get("Author"),
                            modified_by=file_obj.get("ModifiedBy"),
                            checked_out_by_user=file_obj.get("CheckedOutByUser"),
                            check_out_type=file_obj.get("CheckOutType"),
                            raw_metadata=file_obj,
                            local_path=None,
                        )

                        # Download file using downloader service
                        try:
                            # Download directly as we have NTLM auth
                            file_content = await self._sp_get_file_content(file_ref)

                            # Use file downloader to save
                            await self.file_downloader.save_bytes(
                                entity=file_entity,
                                content=file_content,
                                filename_with_extension=file_name,
                                logger=self.logger,
                            )

                            yield file_entity

                        except FileSkippedException as e:
                            self.logger.debug(f"Skipping file {file_name}: {e.reason}")
                        except Exception as e:
                            self.logger.error(f"Failed to download file {file_name}: {e}")

                    except Exception as e:
                        self.logger.error(f"Error processing file for item {item_id}: {e}")
                elif file_ref and not file_obj:
                    # File expansion didn't return data, try fetching directly
                    self.logger.debug(
                        f"File object not expanded for item {item_id}, fetching directly"
                    )
                    try:
                        file_endpoint = f"/web/GetFileByServerRelativeUrl('{file_ref}')"
                        file_data = await self._sp_get(file_endpoint)
                        fetched_file_obj = file_data.get("d", {})

                        file_name = fetched_file_obj.get("Name", title)
                        file_length = int(fetched_file_obj.get("Length", 0) or 0)

                        _, ext = os.path.splitext(file_name)
                        ext = ext.lower().lstrip(".")

                        file_entity = SharePoint2019FileEntity(
                            breadcrumbs=[list_breadcrumb],
                            id=fetched_file_obj.get("UniqueId", str(item_id)),
                            name=file_name,
                            title=title,
                            created_at=created,
                            updated_at=modified,
                            access=access,
                            url=f"{self.site_url}{file_ref}",
                            size=file_length,
                            file_type=ext or "file",
                            mime_type=f"application/{ext}" if ext else "application/octet-stream",
                            server_relative_url=file_ref,
                            length=file_length,
                            time_created=fetched_file_obj.get("TimeCreated"),
                            time_last_modified=fetched_file_obj.get("TimeLastModified"),
                            list_item_id=item_id,
                            list_id=list_id,
                            author=fetched_file_obj.get("Author"),
                            modified_by=fetched_file_obj.get("ModifiedBy"),
                            checked_out_by_user=fetched_file_obj.get("CheckedOutByUser"),
                            check_out_type=fetched_file_obj.get("CheckOutType"),
                            raw_metadata=fetched_file_obj,
                            local_path=None,
                        )

                        try:
                            file_content = await self._sp_get_file_content(file_ref)
                            await self.file_downloader.save_bytes(
                                entity=file_entity,
                                content=file_content,
                                filename_with_extension=file_name,
                                logger=self.logger,
                            )
                            yield file_entity
                        except FileSkippedException as e:
                            self.logger.debug(f"Skipping file {file_name}: {e.reason}")
                        except Exception as e:
                            self.logger.error(f"Failed to download file {file_name}: {e}")

                    except Exception as e:
                        self.logger.error(f"Error fetching file for item {item_id}: {e}")
            else:
                # Regular list item (not a file)
                yield SharePoint2019ListItemEntity(
                    breadcrumbs=[list_breadcrumb],
                    id=str(item_id),
                    name=title,
                    title=title,
                    created_at=created,
                    updated_at=modified,
                    access=access,
                    fields=fields,  # Processed fields with text values
                    content_type_id=fields.get("ContentTypeId"),
                    file_system_object_type=file_system_obj_type,
                    server_relative_url=fields.get("FileRef"),
                    list_id=list_id,
                    raw_metadata=item,
                )

    async def generate_entities(self) -> AsyncGenerator[BaseEntity, None]:
        """Generate all SharePoint 2019 entities.

        Yields:
            - SharePoint2019ListEntity for each list
            - SharePoint2019ListItemEntity for each non-file list item
            - SharePoint2019FileEntity for each file (with download)
        """
        self.logger.info("===== STARTING SHAREPOINT 2019 ENTITY GENERATION =====")
        entity_count = 0

        try:
            # Generate list entities and their items
            async for list_entity in self._generate_list_entities():
                entity_count += 1
                self.logger.info(f"Entity #{entity_count}: List - {list_entity.title}")
                yield list_entity

                # Generate items/files for this list
                async for item_or_file in self._generate_list_item_and_file_entities(list_entity):
                    entity_count += 1
                    entity_type = type(item_or_file).__name__
                    entity_name = getattr(item_or_file, "name", "unknown")
                    self.logger.info(
                        "Entity #%s: %s - %s",
                        entity_count,
                        entity_type,
                        entity_name,
                    )
                    yield item_or_file

        except Exception as e:
            self.logger.error(f"Error in entity generation: {e}", exc_info=True)
            raise
        finally:
            self.logger.info(
                f"===== SHAREPOINT 2019 ENTITY GENERATION COMPLETE: {entity_count} entities ====="
            )

    async def generate_access_control_memberships(
        self,
    ) -> AsyncGenerator[AccessControlMembership, None]:
        """Generate access control membership tuples for SharePoint + AD.

        Creates tuples for:
        - SP Group → User
        - SP Group → AD Group
        - AD Group → AD Group (nested)
        - AD Group → User

        Uses LoginName consistently to track principals.
        """
        self.logger.info("===== STARTING ACCESS CONTROL MEMBERSHIP EXTRACTION =====")
        membership_count = 0

        try:
            # Connect to AD
            ad_conn = await self._connect_to_ad()

            # 1. Get all SharePoint Groups
            sp_groups_endpoint = "/web/sitegroups"
            sp_groups_data = await self._sp_get(sp_groups_endpoint)
            sp_groups = sp_groups_data.get("d", {}).get("results", [])

            for sp_group in sp_groups:
                group_id = sp_group.get("Id")
                group_title = sp_group.get("Title", "Unknown Group")

                self.logger.info(f"Processing SP Group: {group_title} (ID: {group_id})")

                # Get members of this SP group
                members_endpoint = f"/web/sitegroups/getbyid({group_id})/users"
                members_data = await self._sp_get(members_endpoint)
                members = members_data.get("d", {}).get("results", [])

                for member in members:
                    principal_type = member.get("PrincipalType", 0)
                    login_name = member.get("LoginName", "")

                    if not login_name:
                        continue

                    if principal_type == 1:  # User
                        # SP Group → User membership
                        yield AccessControlMembership(
                            member_id=login_name,
                            member_type="user",
                            group_id=f"sp:{group_id}",
                            group_name=group_title,
                        )
                        membership_count += 1

                    elif principal_type == 4:  # AD Security Group
                        # SP Group → AD Group membership
                        yield AccessControlMembership(
                            member_id=login_name,
                            member_type="group",
                            group_id=f"sp:{group_id}",
                            group_name=group_title,
                        )
                        membership_count += 1

                        # Now expand this AD group recursively
                        async for ad_membership in self._expand_ad_group_recursive(
                            ad_conn, login_name
                        ):
                            yield ad_membership
                            membership_count += 1

            self.logger.info(
                "===== ACCESS CONTROL MEMBERSHIP EXTRACTION COMPLETE: %s memberships =====",
                membership_count,
            )

        except Exception as e:
            self.logger.error(f"Error generating access control memberships: {e}", exc_info=True)
            raise

    async def _expand_ad_group_recursive(
        self, ad_conn: Connection, group_login_name: str
    ) -> AsyncGenerator[AccessControlMembership, None]:
        r"""Recursively expand an AD group to find all nested memberships.

        Args:
            ad_conn: LDAP connection
            group_login_name: LoginName of the AD group (e.g., "c:0+.w|DOMAIN\\groupname")

        Yields:
            AccessControlMembership for AD Group → User and AD Group → AD Group
        """
        # Extract actual group name from LoginName
        # LoginName format: "c:0+.w|DOMAIN\\groupname"
        group_name = (
            group_login_name.split("|")[-1].split("\\")[-1]
            if "|" in group_login_name
            else group_login_name
        )

        # Query AD for this group
        search_filter = f"(&(objectClass=group)(sAMAccountName={group_name}))"
        ad_conn.search(
            search_base=self.ad_search_base,
            search_filter=search_filter,
            search_scope=SUBTREE,
            attributes=["cn", "distinguishedName", "member"],
        )

        if not ad_conn.entries:
            self.logger.warning(f"AD group not found: {group_name}")
            return

        group_entry = ad_conn.entries[0]
        members = [str(m) for m in group_entry.member] if hasattr(group_entry, "member") else []

        for member_dn in members:
            # Query this member to determine if it's a user or group
            ad_conn.search(
                search_base=member_dn,
                search_filter="(objectClass=*)",
                search_scope=BASE,
                attributes=["objectClass", "sAMAccountName"],
            )

            if not ad_conn.entries:
                continue

            member_entry = ad_conn.entries[0]
            object_classes = (
                [str(oc) for oc in member_entry.objectClass]
                if hasattr(member_entry, "objectClass")
                else []
            )
            sam_account_name = (
                str(member_entry.sAMAccountName)
                if hasattr(member_entry, "sAMAccountName")
                else None
            )

            if not sam_account_name:
                continue

            # Build LoginName format
            member_login_name = f"{self.ad_domain}\\{sam_account_name}"

            if "user" in object_classes:
                # AD Group → User
                yield AccessControlMembership(
                    member_id=member_login_name,
                    member_type="user",
                    group_id=group_login_name,
                    group_name=group_name,
                )
            elif "group" in object_classes:
                # AD Group → AD Group
                nested_group_login = f"c:0+.w|{member_login_name}"
                yield AccessControlMembership(
                    member_id=nested_group_login,
                    member_type="group",
                    group_id=group_login_name,
                    group_name=group_name,
                )

                # Recurse into nested group
                async for nested_membership in self._expand_ad_group_recursive(
                    ad_conn, nested_group_login
                ):
                    yield nested_membership

    async def validate(self) -> bool:
        """Validate SharePoint 2019 and AD connections."""
        try:
            # Test SharePoint connection
            try:
                await self._sp_get("/web")
                self.logger.info("SharePoint connection validated")
            except Exception as sp_error:
                # Helper: If HTTP failed, check if HTTPS works and guide the user
                if self.site_url and self.site_url.startswith("http://"):
                    original_url = self.site_url
                    https_url = self.site_url.replace("http://", "https://")
                    self.logger.warning(
                        "HTTP validation failed for %s: %s (%s). Trying HTTPS: %s",
                        original_url,
                        sp_error,
                        type(sp_error).__name__,
                        https_url,
                    )

                    try:
                        self.site_url = https_url
                        await self._sp_get("/web")
                        # If we get here, HTTPS works!
                        self.logger.error(
                            f"Validation succeeded with {https_url} but failed with "
                            f"{original_url}. Please update your Site URL to use 'https://'."
                        )
                        # We must return False because the saved config would still be HTTP
                        return False
                    except Exception as https_error:
                        self.logger.error(
                            "HTTPS validation failed for %s as well: %s (%s)",
                            https_url,
                            https_error,
                            type(https_error).__name__,
                            exc_info=True,
                        )
                        # HTTPS also failed, revert and raise original error
                        self.site_url = original_url
                        raise sp_error
                else:
                    self.logger.error(
                        "SharePoint validation failed for %s: %s (%s)",
                        self.site_url,
                        sp_error,
                        type(sp_error).__name__,
                        exc_info=True,
                    )
                    raise sp_error

            # Test AD connection
            await self._connect_to_ad()
            self.logger.info("Active Directory connection validated")

            return True
        except Exception as e:
            self.logger.error(f"Validation failed: {e}")
            return False

    def _parse_datetime(self, dt_str: Optional[str]) -> Optional[datetime]:
        """Parse datetime string from SharePoint OData format."""
        if not dt_str:
            return None
        try:
            # SharePoint returns ISO format or OData format
            if dt_str.endswith("Z"):
                dt_str = dt_str.replace("Z", "+00:00")
            return datetime.fromisoformat(dt_str)
        except (ValueError, TypeError):
            return None
