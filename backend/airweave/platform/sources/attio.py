"""Attio source implementation.

Attio is a flexible CRM platform. We extract:
- Objects (Companies, People, Deals, etc.)
- Lists (Custom collections)
- Records (Individual entries in objects/lists)
- Notes (Attached to records)

Note: Comments are not supported as the Attio API does not expose them via REST API.
"""

import asyncio
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx
from tenacity import retry, stop_after_attempt

from airweave.core.shared_models import RateLimitLevel
from airweave.platform.configs.auth import AttioAuthConfig
from airweave.platform.configs.config import AttioConfig
from airweave.platform.decorators import source
from airweave.platform.entities._base import BaseEntity, Breadcrumb
from airweave.platform.entities.attio import (
    AttioListEntity,
    AttioNoteEntity,
    AttioObjectEntity,
    AttioRecordEntity,
)
from airweave.platform.sources._base import BaseSource
from airweave.platform.sources.retry_helpers import (
    retry_if_rate_limit_or_timeout,
    wait_rate_limit_with_backoff,
)
from airweave.schemas.source_connection import AuthenticationMethod


@source(
    name="Attio",
    short_name="attio",
    auth_methods=[AuthenticationMethod.DIRECT, AuthenticationMethod.AUTH_PROVIDER],
    oauth_type=None,
    auth_config_class=AttioAuthConfig,
    config_class=AttioConfig,
    labels=["CRM"],
    supports_continuous=False,
    rate_limit_level=RateLimitLevel.ORG,
)
class AttioSource(BaseSource):
    """Attio source connector integrates with the Attio API to extract CRM data.

    Synchronizes your Attio workspace including objects, lists, records, and notes.
    """

    BASE_URL = "https://api.attio.com/v2"

    @classmethod
    async def create(
        cls, attio_auth_config: AttioAuthConfig, config: Optional[Dict[str, Any]] = None
    ) -> "AttioSource":
        """Create a new Attio source instance.

        Args:
            attio_auth_config: Authentication configuration with API key
            config: Optional configuration parameters

        Returns:
            Configured AttioSource instance
        """
        instance = cls()
        instance.api_key = attio_auth_config.api_key
        return instance

    @retry(
        stop=stop_after_attempt(5),
        retry=retry_if_rate_limit_or_timeout,
        wait=wait_rate_limit_with_backoff,
        reraise=True,
    )
    async def _get_with_auth(
        self, client: httpx.AsyncClient, url: str, params: Optional[Dict[str, Any]] = None
    ) -> Dict:
        """Make authenticated GET request to Attio API with rate limit handling.

        Args:
            client: HTTP client
            url: API endpoint URL
            params: Optional query parameters

        Returns:
            JSON response data

        Raises:
            httpx.HTTPStatusError: On HTTP errors (except 429, which is retried)
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
        }

        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = await client.get(url, headers=headers, params=params, timeout=20.0)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:
                    # Rate limited - respect Retry-After header
                    retry_after = e.response.headers.get("Retry-After")

                    if retry_after:
                        try:
                            # Try parsing as HTTP date
                            retry_date = parsedate_to_datetime(retry_after)
                            wait_seconds = max(
                                0, (retry_date - datetime.now(retry_date.tzinfo)).total_seconds()
                            )
                        except (ValueError, TypeError):
                            # Fall back to treating as seconds
                            try:
                                wait_seconds = float(retry_after)
                            except (ValueError, TypeError):
                                wait_seconds = 1.0  # Default wait
                    else:
                        wait_seconds = 1.0  # Default to 1 second if no header

                    if attempt < max_retries - 1:
                        self.logger.warning(
                            f"Rate limited (429) on {url}, waiting {wait_seconds:.1f}s "
                            f"(attempt {attempt + 1}/{max_retries})"
                        )
                        await asyncio.sleep(wait_seconds)
                        continue
                    else:
                        self.logger.error(
                            f"Rate limit exceeded after {max_retries} attempts for {url}"
                        )
                        raise
                else:
                    # Non-429 error - log and raise immediately
                    self.logger.error(
                        f"HTTP error from Attio API: {e.response.status_code} for {url}"
                    )
                    raise
            except Exception as e:
                self.logger.error(f"Unexpected error accessing Attio API: {url}, {str(e)}")
                raise

    @retry(
        stop=stop_after_attempt(5),
        retry=retry_if_rate_limit_or_timeout,
        wait=wait_rate_limit_with_backoff,
        reraise=True,
    )
    async def _post_with_auth(
        self, client: httpx.AsyncClient, url: str, json_data: Optional[Dict[str, Any]] = None
    ) -> Dict:
        """Make authenticated POST request to Attio API.

        Args:
            client: HTTP client
            url: API endpoint URL
            json_data: Optional JSON body

        Returns:
            JSON response data

        Raises:
            httpx.HTTPStatusError: On HTTP errors
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        try:
            response = await client.post(url, headers=headers, json=json_data or {}, timeout=20.0)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            self.logger.error(f"HTTP error from Attio API: {e.response.status_code} for {url}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error accessing Attio API: {url}, {str(e)}")
            raise

    async def _get_all_pages(
        self, client: httpx.AsyncClient, url: str, data_key: str = "data"
    ) -> List[Dict]:
        """Fetch all pages from a paginated Attio endpoint (GET).

        Args:
            client: HTTP client
            url: Base API endpoint URL
            data_key: Key in response containing the data array

        Returns:
            List of all items across all pages
        """
        all_items = []
        offset = 0
        limit = 100

        while True:
            params = {"offset": offset, "limit": limit}
            response = await self._get_with_auth(client, url, params)

            items = response.get(data_key, [])
            if not items:
                break

            all_items.extend(items)

            # Check if we've reached the end
            if len(items) < limit:
                break

            offset += limit

        return all_items

    async def _query_all_pages(
        self, client: httpx.AsyncClient, url: str, data_key: str = "data"
    ) -> List[Dict]:
        """Fetch all pages from a paginated Attio endpoint (POST query).

        Args:
            client: HTTP client
            url: Query API endpoint URL
            data_key: Key in response containing the data array

        Returns:
            List of all items across all pages
        """
        all_items = []
        offset = 0
        limit = 100

        while True:
            query_body = {"offset": offset, "limit": limit}
            response = await self._post_with_auth(client, url, query_body)

            items = response.get(data_key, [])
            if not items:
                break

            all_items.extend(items)

            # Check if we've reached the end
            if len(items) < limit:
                break

            offset += limit

        return all_items

    async def _query_all_pages_optional(
        self, client: httpx.AsyncClient, url: str, data_key: str = "data"
    ) -> List[Dict]:
        """Fetch all pages from optional nested resources (notes/comments).

        Returns empty list on 404 without retrying.

        Args:
            client: HTTP client
            url: Query API endpoint URL
            data_key: Key in response containing the data array

        Returns:
            List of all items across all pages, or empty list if not found
        """
        all_items = []
        offset = 0
        limit = 100

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        while True:
            query_body = {"offset": offset, "limit": limit}

            try:
                response = await client.post(url, headers=headers, json=query_body, timeout=20.0)
                response.raise_for_status()
                data = response.json()
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    # No notes/comments for this resource, return empty
                    return []
                self.logger.error(f"HTTP error from Attio API: {e.response.status_code} for {url}")
                raise
            except Exception as e:
                self.logger.error(f"Unexpected error accessing Attio API: {url}, {str(e)}")
                raise

            items = data.get(data_key, [])
            if not items:
                break

            all_items.extend(items)

            # Check if we've reached the end
            if len(items) < limit:
                break

            offset += limit

        return all_items

    async def _generate_object_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate Attio Object entities (Companies, People, Deals, etc.).

        Yields:
            AttioObjectEntity instances
        """
        self.logger.info("Fetching Attio objects...")
        url = f"{self.BASE_URL}/objects"
        objects = await self._get_all_pages(client, url, data_key="data")

        for obj in objects:
            object_id = obj.get("id", {}).get("object_id")
            if not object_id:
                continue

            self.logger.debug(f"Generating object entity: {object_id}")

            singular_noun = obj.get("singular_noun", "")

            display_name = singular_noun or object_id

            yield AttioObjectEntity(
                object_id=object_id,
                breadcrumbs=[],
                name=display_name,
                created_at=obj.get("created_at"),
                singular_noun=display_name,
                plural_noun=obj.get("plural_noun", display_name + "s"),
                api_slug=obj.get("api_slug", object_id),
                icon=obj.get("icon"),
            )

    async def _generate_list_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate Attio List entities.

        Yields:
            AttioListEntity instances
        """
        self.logger.info("Fetching Attio lists...")
        url = f"{self.BASE_URL}/lists"
        lists = await self._get_all_pages(client, url, data_key="data")

        for lst in lists:
            list_id = lst.get("id", {}).get("list_id")
            if not list_id:
                continue

            self.logger.debug(f"Generating list entity: {list_id}")

            # Handle parent_object - API returns list, but we need string
            parent_object = lst.get("parent_object")
            if isinstance(parent_object, list):
                parent_object = ", ".join(parent_object) if parent_object else None

            list_name = lst.get("name", list_id)

            yield AttioListEntity(
                list_id=list_id,
                breadcrumbs=[],
                name=list_name,
                created_at=lst.get("created_at"),
                workspace_id=lst.get("workspace_id", ""),
                parent_object=parent_object,
            )

    async def _generate_record_entities_for_object(  # noqa: C901
        self,
        client: httpx.AsyncClient,
        object_slug: str,
        object_name: str,
        object_breadcrumb: Breadcrumb,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate record entities for a specific object.

        Args:
            client: HTTP client
            object_slug: API slug of the object (e.g., 'companies', 'people')
            object_name: Name of the object
            object_breadcrumb: Breadcrumb for the parent object

        Yields:
            AttioRecordEntity instances
        """
        self.logger.debug(f"Fetching records for object: {object_slug}")
        url = f"{self.BASE_URL}/objects/{object_slug}/records/query"

        try:
            records = await self._query_all_pages(client, url, data_key="data")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                self.logger.warning(f"Object {object_slug} not found or not accessible, skipping")
                return
            raise

        for record in records:
            record_id = record.get("id", {}).get("record_id")
            if not record_id:
                continue

            # Skip deleted records (deleted but still returned by API in some cases)
            if record.get("deleted_at"):
                self.logger.info(f"Skipping deleted record: {record_id}")
                continue

            # Extract attributes from the values field
            values = record.get("values", {})

            # Try to extract common fields
            name = None
            description = None
            email_addresses = []
            phone_numbers = []
            domains = []
            categories = []
            attributes = {}

            for attr_key, attr_values in values.items():
                if not attr_values:
                    continue

                # Extract first value for common fields
                first_val = attr_values[0] if isinstance(attr_values, list) else attr_values

                # Detect field types by name
                if "name" in attr_key.lower() or "title" in attr_key.lower():
                    if isinstance(first_val, dict):
                        name = first_val.get("value") or first_val.get("text")
                    else:
                        name = str(first_val)

                elif "description" in attr_key.lower() or "notes" in attr_key.lower():
                    if isinstance(first_val, dict):
                        description = first_val.get("value") or first_val.get("text")
                    else:
                        description = str(first_val)

                elif "email" in attr_key.lower():
                    # Keep as dicts, filter out None/empty
                    email_addresses = [
                        v for v in attr_values if v is not None and isinstance(v, dict)
                    ]

                elif "phone" in attr_key.lower():
                    # Keep as dicts, filter out None/empty
                    phone_numbers = [
                        v for v in attr_values if v is not None and isinstance(v, dict)
                    ]

                elif "domain" in attr_key.lower():
                    # Extract strings from dicts or use strings directly
                    domains = [
                        v.get("domain") if isinstance(v, dict) else v
                        for v in attr_values
                        if v is not None
                        and (isinstance(v, dict) and v.get("domain") or isinstance(v, str))
                    ]

                elif "category" in attr_key.lower() or "tag" in attr_key.lower():
                    # Extract strings from dicts or use strings directly
                    categories = [
                        v.get("value") if isinstance(v, dict) else v
                        for v in attr_values
                        if v is not None
                        and (isinstance(v, dict) and v.get("value") or isinstance(v, str))
                    ]

                # Store all attributes for searchability
                attributes[attr_key] = attr_values

            # Create record name from name attribute or record ID
            record_name = name or record_id

            yield AttioRecordEntity(
                record_id=record_id,
                breadcrumbs=[object_breadcrumb],
                name=record_name,
                created_at=record.get("created_at"),
                updated_at=record.get("updated_at"),
                object_id=object_slug,
                list_id=None,  # This is an object record, not a list record
                parent_object_name=object_name,
                description=description,
                email_addresses=email_addresses,
                phone_numbers=phone_numbers,
                domains=domains,
                categories=categories,
                attributes=attributes,
                permalink_url=None,  # Not provided by API for records
            )

    async def _generate_record_entities_for_list(  # noqa: C901
        self,
        client: httpx.AsyncClient,
        list_id: str,
        list_name: str,
        list_breadcrumb: Breadcrumb,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate record entities for a specific list.

        Args:
            client: HTTP client
            list_id: ID of the list
            list_name: Name of the list
            list_breadcrumb: Breadcrumb for the parent list

        Yields:
            AttioRecordEntity instances
        """
        self.logger.debug(f"Fetching records for list: {list_id}")
        url = f"{self.BASE_URL}/lists/{list_id}/records/query"

        # Use optional query to handle 404s gracefully without error logs
        records = await self._query_all_pages_optional(client, url, data_key="data")

        if not records:
            self.logger.debug(f"List {list_id} has no records or is not accessible")
            return

        for record in records:
            record_id = record.get("id", {}).get("record_id")
            if not record_id:
                continue

            # Skip deleted records (deleted but still returned by API in some cases)
            if record.get("deleted_at"):
                self.logger.info(f"Skipping deleted list record: {record_id}")
                continue

            # Extract attributes from the values field
            values = record.get("values", {})

            # Try to extract common fields (same logic as objects)
            name = None
            description = None
            attributes = {}

            for attr_key, attr_values in values.items():
                if not attr_values:
                    continue

                first_val = attr_values[0] if isinstance(attr_values, list) else attr_values

                if "name" in attr_key.lower() or "title" in attr_key.lower():
                    if isinstance(first_val, dict):
                        name = first_val.get("value") or first_val.get("text")
                    else:
                        name = str(first_val)

                elif "description" in attr_key.lower():
                    if isinstance(first_val, dict):
                        description = first_val.get("value") or first_val.get("text")
                    else:
                        description = str(first_val)

                attributes[attr_key] = attr_values

            # Create record name from name attribute or record ID
            record_name = name or record_id

            yield AttioRecordEntity(
                record_id=record_id,
                breadcrumbs=[list_breadcrumb],
                name=record_name,
                created_at=record.get("created_at"),
                updated_at=record.get("updated_at"),
                object_id=None,  # This is a list record, not an object record
                list_id=list_id,
                parent_object_name=list_name,
                description=description,
                email_addresses=[],  # List records might not have these fields
                phone_numbers=[],  # List records might not have these fields
                domains=[],  # List records might not have these fields
                categories=[],  # List records might not have these fields
                attributes=attributes,
                permalink_url=None,  # Not provided by API for records
            )

    async def _generate_note_entities_for_record(  # noqa: C901
        self,
        client: httpx.AsyncClient,
        parent_object_or_list_id: str,
        record_id: str,
        record_breadcrumbs: List[Breadcrumb],
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate note entities for a specific record.

        Args:
            client: HTTP client
            parent_object_or_list_id: ID of parent object or list
            record_id: ID of the record
            record_breadcrumbs: Breadcrumbs leading to this record

        Yields:
            AttioNoteEntity instances
        """
        self.logger.debug(
            f"🔍 Attempting to fetch notes for record {record_id} "
            f"(parent: {parent_object_or_list_id})"
        )

        # According to Attio API docs, use GET /v2/notes with query parameters
        # Reference: https://docs.attio.com/rest-api/endpoint-reference/notes/list-notes
        url = f"{self.BASE_URL}/notes"

        params = {
            "parent_object": parent_object_or_list_id,
            "parent_record_id": record_id,
            "limit": 50,  # Maximum allowed by API
        }

        notes = []
        try:
            # Use GET with query parameters
            response = await self._get_with_auth(client, url, params=params)
            notes = response.get("data", [])
            if notes:
                self.logger.info(
                    f"✅ Found {len(notes)} notes for record {record_id} "
                    f"(parent: {parent_object_or_list_id})"
                )
            else:
                self.logger.debug(f"No notes found for record {record_id}")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                # Notes endpoint might not exist or no notes found
                self.logger.warning(f"⚠️ Notes endpoint returned 404 for record {record_id}")
                return
            else:
                self.logger.warning(
                    f"❌ Error fetching notes for record {record_id}: HTTP {e.response.status_code}"
                )
                return
        except Exception as e:
            self.logger.warning(
                f"❌ Exception fetching notes for record {record_id}: {e}", exc_info=True
            )

        for note in notes:
            note_id = note.get("id", {}).get("note_id")
            if not note_id:
                continue

            # Create note name from title or content preview
            title = note.get("title")
            content = note.get("content", "")
            if title:
                note_name = title
            else:
                # Use content preview if no title
                note_name = content[:50] + "..." if len(content) > 50 else content
                if not note_name:
                    note_name = f"Note {note_id}"

            yield AttioNoteEntity(
                note_id=note_id,
                breadcrumbs=record_breadcrumbs,
                name=note_name,
                created_at=note.get("created_at"),
                updated_at=note.get("updated_at"),
                parent_record_id=record_id,
                parent_object=parent_object_or_list_id,
                title=title,
                content=content,
                format=note.get("format"),
                author=note.get("author"),
                permalink_url=None,  # Not provided by API for notes
            )

    async def generate_entities(self) -> AsyncGenerator[BaseEntity, None]:  # noqa: C901
        """Generate all entities from Attio.

        This is the main entry point called by the sync engine.

        Yields:
            All Attio entities (objects, lists, records, notes)
        """
        self.logger.info("Starting Attio sync...")

        try:
            async with self.http_client() as client:
                # Generate objects first
                object_map = {}  # Store objects for later use
                async for obj in self._generate_object_entities(client):
                    yield obj
                    object_map[obj.object_id] = obj

                # Generate lists
                list_map = {}  # Store lists for later use
                async for lst in self._generate_list_entities(client):
                    yield lst
                    list_map[lst.list_id] = lst

                # Generate records for each object (with concurrent note fetching)
                for object_id, obj in object_map.items():
                    try:
                        object_breadcrumb = Breadcrumb(
                            entity_id=object_id,
                            name=obj.name,
                            entity_type="AttioObjectEntity",
                        )

                        # Create a worker that processes a record and its notes concurrently
                        # Bind loop variables to avoid closure issues
                        async def _record_worker(record, _obj=obj, _breadcrumb=object_breadcrumb):
                            # Yield the record first
                            yield record

                            # Generate notes for this record
                            try:
                                record_breadcrumb = Breadcrumb(
                                    entity_id=record.record_id,
                                    name=record.name,
                                    entity_type="AttioRecordEntity",
                                )
                                record_breadcrumbs = [_breadcrumb, record_breadcrumb]

                                note_count = 0
                                async for note in self._generate_note_entities_for_record(
                                    client, _obj.api_slug, record.record_id, record_breadcrumbs
                                ):
                                    note_count += 1
                                    yield note

                                if note_count > 0:
                                    self.logger.info(
                                        f"✅ Yielded {note_count} notes for "
                                        f"record {record.record_id}"
                                    )
                            except Exception as e:
                                self.logger.warning(
                                    f"❌ Error fetching notes for record {record.record_id}: {e}",
                                    exc_info=True,
                                )

                        # Collect all records for this object first
                        records = []
                        async for record in self._generate_record_entities_for_object(
                            client, obj.api_slug, obj.singular_noun, object_breadcrumb
                        ):
                            records.append(record)

                        # Process records concurrently
                        # batch_size=10 to respect Attio's 100 req/sec rate limit
                        # (each record = 1 record fetch + potential notes fetch)
                        async for entity in self.process_entities_concurrent(
                            items=records,
                            worker=_record_worker,
                            batch_size=getattr(self, "batch_size", 10),
                            preserve_order=False,
                            stop_on_error=False,
                        ):
                            yield entity

                    except Exception as e:
                        self.logger.warning(f"Error processing object {obj.api_slug}: {e}")
                        continue

                # Generate records for each list (with concurrent note fetching)
                for list_id, lst in list_map.items():
                    try:
                        list_breadcrumb = Breadcrumb(
                            entity_id=list_id,
                            name=lst.name,
                            entity_type="AttioListEntity",
                        )

                        # Create a worker that processes a record and its notes concurrently
                        # Bind loop variables to avoid closure issues
                        async def _list_record_worker(
                            record, _list_id=list_id, _breadcrumb=list_breadcrumb
                        ):
                            # Yield the record first
                            yield record

                            # Generate notes for this record
                            try:
                                record_breadcrumb = Breadcrumb(
                                    entity_id=record.record_id,
                                    name=record.name,
                                    entity_type="AttioRecordEntity",
                                )
                                record_breadcrumbs = [_breadcrumb, record_breadcrumb]

                                note_count = 0
                                async for note in self._generate_note_entities_for_record(
                                    client, _list_id, record.record_id, record_breadcrumbs
                                ):
                                    note_count += 1
                                    yield note

                                if note_count > 0:
                                    self.logger.info(
                                        f"✅ Yielded {note_count} notes for "
                                        f"record {record.record_id}"
                                    )
                            except Exception as e:
                                self.logger.warning(
                                    f"❌ Error fetching notes for record {record.record_id}: {e}",
                                    exc_info=True,
                                )

                        # Collect all records for this list first
                        records = []
                        async for record in self._generate_record_entities_for_list(
                            client, list_id, lst.name, list_breadcrumb
                        ):
                            records.append(record)

                        # Process records concurrently
                        # batch_size=10 to respect Attio's 100 req/sec rate limit
                        async for entity in self.process_entities_concurrent(
                            items=records,
                            worker=_list_record_worker,
                            batch_size=getattr(self, "batch_size", 10),
                            preserve_order=False,
                            stop_on_error=False,
                        ):
                            yield entity

                    except Exception as e:
                        self.logger.warning(f"Error processing list {list_id}: {e}")
                        continue

            self.logger.info("Attio sync completed successfully")
        except asyncio.CancelledError:
            self.logger.info("Attio sync was cancelled")
            raise
        except Exception as e:
            self.logger.error(f"Error during Attio sync: {e}", exc_info=True)
            raise

    async def validate(self) -> bool:
        """Verify credentials by pinging the Attio API.

        Returns:
            True if credentials are valid, False otherwise
        """
        try:
            async with self.http_client() as client:
                # Test by fetching objects (should work with any valid API key)
                url = f"{self.BASE_URL}/objects"
                await self._get_with_auth(client, url, params={"limit": 1})
                return True
        except Exception as e:
            self.logger.error(f"Attio credential validation failed: {str(e)}")
            return False
