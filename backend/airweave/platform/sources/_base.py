"""Base source class."""

import base64  # for JWT payload peek
import json  # for JWT payload peek
import re  # for URL cleaning
import time  # for exp checks
from abc import abstractmethod
from contextlib import asynccontextmanager
from typing import (
    Any,
    AsyncGenerator,
    AsyncIterable,
    Callable,
    ClassVar,
    Dict,
    Iterable,
    Optional,
    Union,
)

import httpx
from pydantic import BaseModel

from airweave.core.logging import logger
from airweave.platform.entities._base import FileEntity
from airweave.schemas.source_connection import AuthenticationMethod, OAuthType


class BaseSource:
    """Base class for all sources."""

    _labels: ClassVar[list[str]] = []
    _auth_methods: ClassVar[list[AuthenticationMethod]] = []
    _oauth_type: ClassVar[Optional[OAuthType]] = None
    _requires_byoc: ClassVar[bool] = False
    _auth_config_class: ClassVar[Optional[str]] = None

    def __init__(self):
        """Initialize the base source."""
        self._logger: Optional[Any] = None  # Store contextual logger as instance variable
        self._token_manager: Optional[Any] = None  # Store token manager for OAuth sources
        self._http_client_factory: Optional[Callable] = None  # Factory for creating HTTP clients
        self._file_downloader: Optional[Any] = None  # File download service
        # Optional sync identifiers for multi-tenant scoped helpers
        self._organization_id: Optional[str] = None
        self._source_connection_id: Optional[str] = None

    @property
    def logger(self):
        """Get the logger for this source, falling back to default if not set."""
        if self._logger is not None:
            return self._logger
        # Fall back to default logger
        return logger

    def set_logger(self, logger) -> None:
        """Set a contextual logger for this source."""
        self._logger = logger

    def set_sync_identifiers(self, organization_id: str, source_connection_id: str) -> None:
        """Set sync-scoped identifiers for this source instance.

        These identifiers can be used by sources to persist auxiliary metadata
        (e.g., schema catalogs) scoped to the current tenant/connection.
        """
        self._organization_id = organization_id
        self._source_connection_id = source_connection_id

    @property
    def token_manager(self):
        """Get the token manager for this source."""
        return self._token_manager

    def set_token_manager(self, token_manager) -> None:
        """Set a token manager for this source.

        Args:
            token_manager: TokenManager instance for handling OAuth token refresh
        """
        self._token_manager = token_manager

    def set_http_client_factory(self, factory: Optional[Callable]) -> None:
        """Set the HTTP client factory for creating HTTP clients.

        Args:
            factory: Callable that creates HTTP clients, or None for vanilla httpx
        """
        self._http_client_factory = factory
        if factory:
            self.logger.debug("HTTP client factory configured")

    @property
    def file_downloader(self):
        """Get the file downloader for this source."""
        return self._file_downloader

    def set_file_downloader(self, downloader) -> None:
        """Set file downloader service for this source.

        Args:
            downloader: FileDownloadService instance for downloading files
        """
        self._file_downloader = downloader

    @asynccontextmanager
    async def http_client(self, **kwargs):
        """Get HTTP client with proper lifecycle management.

        Args:
            **kwargs: Standard httpx.AsyncClient parameters

        Usage:
            async with self.http_client() as client:
                response = await client.get(url, headers=headers)

        Yields:
            HTTP client (either vanilla httpx or Pipedream proxy)
        """
        if self._http_client_factory:
            # Use factory-provided client (could be Pipedream proxy)
            client = self._http_client_factory(**kwargs)
            if hasattr(client, "__aenter__"):
                # Client supports context management
                async with client as managed_client:
                    yield managed_client
            else:
                # Client doesn't need context management
                try:
                    yield client
                finally:
                    if hasattr(client, "aclose"):
                        await client.aclose()
        else:
            # Use vanilla httpx
            async with httpx.AsyncClient(**kwargs) as client:
                yield client

    def set_cursor(self, cursor) -> None:
        """Set the cursor for this source.

        Args:
            cursor: SyncCursor instance for tracking sync progress
        """
        self._cursor = cursor

    @property
    def cursor(self):
        """Get the cursor for this source."""
        return getattr(self, "_cursor", None)

    def get_default_cursor_field(self) -> Optional[str]:
        """Get the default cursor field for this source.

        Override this in subclasses to provide a default cursor field.
        Return None if the source doesn't have a default (requires user to specify).

        Returns:
            The default cursor field name, or None if no default
        """
        return None

    @classmethod
    def supports_auth_method(cls, method: AuthenticationMethod) -> bool:
        """Check if source supports a given authentication method."""
        methods = cls.get_supported_auth_methods()
        return method in methods

    @classmethod
    def get_supported_auth_methods(cls) -> list[AuthenticationMethod]:
        """Get all supported authentication methods."""
        # Always include BYOC if OAUTH_BROWSER is supported
        methods = list(cls._auth_methods)
        if (
            AuthenticationMethod.OAUTH_BROWSER in methods
            and AuthenticationMethod.OAUTH_BYOC not in methods
        ):
            methods.append(AuthenticationMethod.OAUTH_BYOC)
        return methods

    @classmethod
    def get_oauth_type(cls) -> Optional[OAuthType]:
        """Get OAuth token type if this is an OAuth source."""
        return cls._oauth_type

    @classmethod
    def is_oauth_source(cls) -> bool:
        """Check if this is an OAuth-based source."""
        return AuthenticationMethod.OAUTH_BROWSER in cls._auth_methods

    @classmethod
    def requires_refresh_token(cls) -> bool:
        """Check if source requires refresh token."""
        return cls._oauth_type in [OAuthType.WITH_REFRESH, OAuthType.WITH_ROTATING_REFRESH]

    @classmethod
    def requires_byoc(cls) -> bool:
        """Check if source requires user to bring their own OAuth client credentials."""
        return cls._requires_byoc

    def get_effective_cursor_field(self) -> Optional[str]:
        """Get the cursor field to use for this sync.

        Returns the user-specified cursor field if available,
        otherwise falls back to the source's default.

        Returns:
            The cursor field to use, or None if no cursor field is defined
        """
        # Use cursor field from cursor if specified
        if self.cursor and hasattr(self, "cursor_field") and self.cursor.cursor_field:
            return self.cursor.cursor_field

        # Fall back to source default
        return self.get_default_cursor_field()

    def validate_cursor_field(self, cursor_field: str) -> None:
        """Validate if the given cursor field is valid for this source.

        Override this method in sources that have specific cursor field requirements.
        By default, any cursor field is considered valid (sources like PostgreSQL
        can use any column as cursor).

        Args:
            cursor_field: The cursor field to validate

        Raises:
            ValueError: If the cursor field is invalid for this source
        """
        # By default, accept any cursor field (e.g., for database sources)
        # Sources with specific requirements should override this
        pass

    async def get_access_token(self) -> Optional[str]:
        """Get a valid access token using the token manager.

        Returns:
            A valid access token if token manager is set and source uses OAuth,
            None otherwise
        """
        if self._token_manager:
            return await self._token_manager.get_valid_token()

        # Fallback to instance access_token if no token manager
        return getattr(self, "access_token", None)

    async def refresh_on_unauthorized(self) -> Optional[str]:
        """Refresh token after receiving a 401 error.

        Returns:
            New access token if refresh was successful, None otherwise
        """
        if self._token_manager:
            return await self._token_manager.refresh_on_unauthorized()
        return None

    @classmethod
    @abstractmethod
    async def create(
        cls, credentials: Optional[Any] = None, config: Optional[Dict[str, Any]] = None
    ) -> "BaseSource":
        """Create a new source instance.

        Args:
            credentials: Optional credentials for authenticated sources.
                       For sources without authentication, this can be None.
            config: Optional configuration parameters

        Returns:
            A configured source instance
        """
        pass

    @abstractmethod
    async def generate_entities(self) -> AsyncGenerator[BaseEntity, None]:
        """Generate entities for the source."""
        pass

    async def process_file_entity(
        self, file_entity: FileEntity, download_url=None, access_token=None, headers=None
    ) -> Optional[BaseEntity]:
        """Process a file entity using the file download service.

        Args:
            file_entity: The FileEntity to process
            download_url: Override the download URL (uses entity.download_url if None)
            access_token: OAuth token for authentication
            headers: Custom headers for the download

        Returns:
            The processed entity if it should be included, None if it should be skipped
        """
        if not self.file_downloader:
            raise ValueError("FileDownloader not configured for this source")

        # Override download URL if provided
        if download_url:
            file_entity.download_url = download_url

        # Create token provider that uses parameter or instance token
        async def token_provider():
            return access_token or await self.get_access_token()

        # Download and enrich entity using downloader service
        return await self.file_downloader.download(
            entity=file_entity,
            http_client_factory=self.http_client,
            access_token_provider=token_provider,
            logger=self.logger,
        )

    async def process_file_entity_with_bytes(
        self, file_entity: FileEntity, content: bytes, metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[BaseEntity]:
        """Process a file entity with content already in memory.

        Used when content is already in memory from API response (e.g., Gmail attachments,
        Confluence HTML). Writes bytes directly to disk for conversion pipeline.

        Args:
            file_entity: FileEntity to process
            content: File content as bytes (already in memory)
            metadata: Optional metadata to add to entity

        Returns:
            Processed FileEntity or None if processing failed
        """
        if not self.file_downloader:
            raise ValueError("FileDownloader not configured for this source")

        self.logger.debug(f"Processing file entity with in-memory bytes: {file_entity.name}")

        # Save bytes using downloader (most efficient path)
        processed_entity = await self.file_downloader.save_bytes(
            entity=file_entity,
            content=content,
            logger=self.logger,
        )

        # Add any additional metadata
        if metadata and processed_entity:
            if not hasattr(processed_entity, "metadata") or processed_entity.metadata is None:
                processed_entity.metadata = {}
            processed_entity.metadata.update(metadata)

        return processed_entity

    @abstractmethod
    async def validate(self) -> bool:
        """Validate that this source is reachable and credentials are usable."""
        raise NotImplementedError

    async def search(self, query: str, limit: int) -> AsyncGenerator[BaseEntity, None]:
        """Search the source for entities matching the query.

        This method is used for federated search where the source provides search
        functionality instead of syncing all data. Sources with federated_search=True
        must implement this method.

        Args:
            query: Search query string
            limit: Maximum number of results to return

        Returns:
            AsyncGenerator yielding BaseEntity objects matching the query

        Raises:
            NotImplementedError: If source does not support federated search
        """
        if not getattr(self.__class__, "_federated_search", False):
            raise NotImplementedError(
                f"Source {self.__class__.__name__} does not support federated search"
            )
        raise NotImplementedError(
            f"Source {self.__class__.__name__} has federated_search=True but "
            "search() method is not implemented"
        )

    def clean_content_for_embedding(self, content: str) -> str:
        """Clean content for embedding by removing huge URLs and cleaning up formatting.

        This is especially important for content from sources like Notion, Confluence,
        and Google Docs which often contain:
        - Massive pre-signed S3/GCS URLs for images
        - Excessive query parameters in URLs
        - Tracking parameters
        - Redundant whitespace

        Args:
            content: Raw content that may contain large URLs

        Returns:
            Cleaned content suitable for embedding with shortened URLs
        """
        if not content:
            return ""

        # First, handle image markdown - these have ! prefix
        # Match images with URLs that have query strings (S3/GCS pre-signed URLs)
        pattern_images_query = r"!\[([^\]]*)\]\([^\?\)]+\?[^\)]+\)"
        content = re.sub(pattern_images_query, r"[Image: \1]", content)

        # Also handle images with very long URLs even without query params
        pattern_images_long = r"!\[([^\]]*)\]\([^\)]{200,}\)"
        content = re.sub(pattern_images_long, r"[Image: \1]", content)

        # Then handle regular links with excessive query parameters
        pattern_links = r"\[([^\]]+)\]\(https?://[^\s\)]+\?[^\)]{100,}\)"
        content = re.sub(pattern_links, r"[\1]", content)

        # Also handle bare URLs that are extremely long (no markdown formatting)
        pattern_bare = r"(https?://[^\s]+\?[^\s]{100,})"
        content = re.sub(pattern_bare, "[link]", content)

        # Remove multiple consecutive blank lines
        content = re.sub(r"\n{3,}", "\n\n", content)

        # Trim whitespace
        content = content.strip()

        return content

    async def _validate_oauth2(  # noqa: C901
        self,
        *,
        # Option A: RFC 7662 token introspection
        introspection_url: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        # Option B: Minimal authenticated ping
        ping_url: Optional[str] = None,
        # Overrides
        access_token: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: float = 10.0,
    ) -> bool:
        """Generic OAuth2 validation: introspection and/or a bearer ping.

        You can supply either:
          - `introspection_url` (+ `client_id` and `client_secret`) for RFC 7662,
          - or `ping_url` for a simple authorized GET using the access token,
          - or both (introspection first, then ping).

        Token refresh is attempted automatically on 401 via `token_manager`.

        Returns:
            True if the token is active and the endpoint(s) respond as expected; otherwise False.
        """
        token = access_token or await self.get_access_token()
        if not token:
            self.logger.error("OAuth2 validation failed: no access token available.")
            return False

        # Helper: safe JWT 'exp' peek (no signature verification).
        def _is_jwt_unexpired(tok: str) -> Optional[bool]:
            try:
                parts = tok.split(".")
                if len(parts) != 3:
                    return None
                # base64url decode payload
                pad = "=" * (-len(parts[1]) % 4)
                payload_bytes = base64.urlsafe_b64decode(parts[1] + pad)
                payload = json.loads(payload_bytes.decode("utf-8"))
                exp = payload.get("exp")
                if exp is None:
                    return None
                return time.time() < float(exp)
            except Exception:
                return None

        async def _do_ping(bearer: str) -> bool:
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    hdrs = {"Authorization": f"Bearer {bearer}"}
                    if headers:
                        hdrs.update(headers)
                    resp = await client.get(ping_url, headers=hdrs)
                    if 200 <= resp.status_code < 300:
                        return True
                    if resp.status_code == 401:
                        self.logger.info("Ping unauthorized (401); attempting token refresh.")
                        new_token = await self.refresh_on_unauthorized()
                        if new_token:
                            hdrs["Authorization"] = f"Bearer {new_token}"
                            resp = await client.get(ping_url, headers=hdrs)
                            return 200 <= resp.status_code < 300
                    self.logger.warning(f"Ping failed: HTTP {resp.status_code} - {resp.text[:200]}")
                    return False
            except httpx.RequestError as e:
                self.logger.error(f"Ping request error: {e}")
                return False

        # 1) Try RFC 7662 introspection if configured
        if introspection_url:
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    auth = (client_id, client_secret) if client_id and client_secret else None
                    data = {"token": token, "token_type_hint": "access_token"}
                    resp = await client.post(
                        introspection_url,
                        data=data,
                        auth=auth,
                        headers={"Accept": "application/json", **(headers or {})},
                    )
                    # Handle unauthorized by refreshing once
                    if resp.status_code == 401:
                        self.logger.info(
                            "Introspection unauthorized (401); attempting token refresh."
                        )
                        new_token = await self.refresh_on_unauthorized()
                        if new_token:
                            data["token"] = new_token
                            resp = await client.post(
                                introspection_url,
                                data=data,
                                auth=auth,
                                headers={"Accept": "application/json", **(headers or {})},
                            )

                    resp.raise_for_status()
                    body = resp.json()
                    active = bool(body.get("active", False))

                    # If the server returns exp, double-check it
                    exp = body.get("exp")
                    if exp is not None:
                        try:
                            if time.time() >= float(exp):
                                active = False
                        except Exception:
                            pass

                    if active:
                        return True

                    # If introspection says inactive, do one last lightweight check:
                    # peek exp from JWT (if it is a JWT) to avoid false negatives
                    # on non-standard servers.
                    peek = _is_jwt_unexpired(token)
                    if peek is True:
                        self.logger.debug(
                            "Token appears unexpired by JWT payload, "
                            "but introspection returned inactive."
                        )
                    else:
                        self.logger.warning("Token reported inactive by introspection.")
                    # Fall through to optional ping if provided
            except httpx.HTTPStatusError as e:
                status = e.response.status_code if getattr(e, "response", None) else "N/A"
                self.logger.error(f"Introspection HTTP error {status}: {e}")
            except httpx.RequestError as e:
                self.logger.error(f"Introspection request error: {e}")
            except Exception as e:
                self.logger.error(f"Unexpected introspection error: {e}")

        # 2) Try an authenticated ping if configured
        if ping_url:
            return await _do_ping(token)

        # 3) Last resort: if neither endpoint provided, do a best-effort JWT exp peek
        peek = _is_jwt_unexpired(token)
        if peek is not None:
            self.logger.debug("Validated via JWT 'exp' claim peek.")
            return peek

        self.logger.warning(
            "OAuth2 validation inconclusive: no endpoints provided and token format is opaque."
        )
        return False

    # ------------------------------
    # Concurrency / batching helpers
    # ------------------------------
    async def process_entities_concurrent(
        self,
        items: Union[Iterable[Any], AsyncIterable[Any]],
        worker: Callable[[Any], AsyncIterable[BaseEntity]],
        *,
        batch_size: int = 10,
        preserve_order: bool = False,
        stop_on_error: bool = False,
        max_queue_size: int = 100,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generic bounded-concurrency driver.

        Returns:
            True if the source is healthy/authorized; False otherwise.

        Notes:
            OAuth2-based sources should generally implement this by calling
            `await self._validate_oauth2(...)` with the appropriate endpoints/
            credentials from their config.
        - `items`: async iterator (or iterable) of units of work.
        - `worker(item)`: async generator yielding 0..N BaseEntity objects for that item.
        - `batch_size`: max concurrent workers.
        - `preserve_order`: if True, buffers per-item results and yields in input order.
        - `stop_on_error`: if True, cancels remaining work on first error.
        """
        results, tasks, total_workers, sentinel = await self._start_entity_workers(
            items=items,
            worker=worker,
            batch_size=batch_size,
            max_queue_size=max_queue_size,
        )

        try:
            if preserve_order:
                async for ent in self._drain_results_preserve_order(
                    results, tasks, total_workers, stop_on_error, sentinel
                ):
                    yield ent
            else:
                async for ent in self._drain_results_unordered(
                    results, tasks, total_workers, stop_on_error, sentinel
                ):
                    yield ent
        finally:
            # Ensure all tasks are cleaned up even if consumer stops early
            import asyncio as _asyncio

            await _asyncio.gather(*tasks, return_exceptions=True)

    async def _start_entity_workers(
        self,
        items: Union[Iterable[Any], AsyncIterable[Any]],
        worker: Callable[[Any], AsyncIterable[BaseEntity]],
        *,
        batch_size: int,
        max_queue_size: int,
    ):
        """Spin up worker tasks and return (results_queue, tasks, total_workers, sentinel)."""
        import asyncio as _asyncio

        semaphore = _asyncio.Semaphore(batch_size)
        results: _asyncio.Queue = _asyncio.Queue(maxsize=max_queue_size)
        sentinel = object()

        async def run_worker(idx: int, item: Any) -> None:
            await semaphore.acquire()
            try:
                agen = worker(item)
                if not hasattr(agen, "__aiter__"):
                    raise TypeError("worker(item) must return an async iterator (async generator).")
                async for entity in agen:
                    await results.put((idx, entity, None))
            except BaseException as e:  # propagate cancellation & capture other errors
                await results.put((idx, None, e))
            finally:
                await results.put((idx, sentinel, None))  # signal completion for idx
                semaphore.release()

        tasks: list[_asyncio.Task] = []
        idx = 0

        if hasattr(items, "__aiter__"):
            async for item in items:  # type: ignore[truthy-bool]
                tasks.append(_asyncio.create_task(run_worker(idx, item)))
                idx += 1
        else:
            for item in items:  # type: ignore[arg-type]
                tasks.append(_asyncio.create_task(run_worker(idx, item)))
                idx += 1

        return results, tasks, idx, sentinel

    async def _drain_results_unordered(
        self,
        results,
        tasks,
        total_workers: int,
        stop_on_error: bool,
        sentinel: object,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Yield results as they arrive; stop early on error if requested."""
        done_workers = 0
        while done_workers < total_workers:
            i, payload, err = await results.get()
            if payload is sentinel:
                done_workers += 1
                continue
            if err:
                self.logger.error(f"Worker {i} error: {err}", exc_info=True)
                if stop_on_error:
                    for t in tasks:
                        t.cancel()
                    raise err
                continue
            yield payload  # type: ignore[misc]

    async def _drain_results_preserve_order(
        self,
        results,
        tasks,
        total_workers: int,
        stop_on_error: bool,
        sentinel: object,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Buffer per-item results and yield in input order."""
        buffers: Dict[int, list[BaseEntity]] = {}
        finished: set[int] = set()
        next_idx = 0
        done_workers = 0

        while done_workers < total_workers:
            i, payload, err = await results.get()
            if payload is sentinel:
                finished.add(i)
                done_workers += 1
            elif err:
                self.logger.error(f"Worker {i} error: {err}", exc_info=True)
                if stop_on_error:
                    for t in tasks:
                        t.cancel()
                    raise err
                # We'll still wait for this worker's sentinel to preserve ordering.
            else:
                buffers.setdefault(i, []).append(payload)  # type: ignore[arg-type]

            while next_idx in finished:
                for ent in buffers.pop(next_idx, []):
                    yield ent
                next_idx += 1


class Relation(BaseModel):
    """A relation between two entities."""

    source_entity_type: type[BaseEntity]
    source_entity_id_attribute: str
    target_entity_type: type[BaseEntity]
    target_entity_id_attribute: str
    relation_type: str
