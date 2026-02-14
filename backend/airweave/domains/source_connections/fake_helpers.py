"""Fake source connection helpers for testing."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from unittest.mock import MagicMock
from uuid import UUID, uuid4


class FakeSourceConnectionHelpers:
    """In-memory fake for SourceConnectionHelpersProtocol.

    Stopgap: returns minimal mocks for each helper method.
    """

    def __init__(self, should_raise: Optional[Exception] = None) -> None:
        self._should_raise = should_raise
        self.calls: list[dict] = []

    def _maybe_raise(self) -> None:
        if self._should_raise:
            raise self._should_raise

    def _track(self, method: str, **kwargs: Any) -> None:
        self.calls.append({"method": method, **kwargs})

    async def update_auth_fields(
        self, db: Any, source_conn: Any, auth_fields: Any, ctx: Any, uow: Any
    ) -> None:
        self._maybe_raise()
        self._track("update_auth_fields")

    async def get_connection_for_source_connection(
        self, db: Any, source_connection: Any, ctx: Any
    ) -> Any:
        self._maybe_raise()
        self._track("get_connection_for_source_connection")
        conn = MagicMock(spec=[])
        conn.id = uuid4()
        conn.short_name = getattr(source_connection, "short_name", "test")
        conn.readable_id = f"conn-{conn.id}"
        return conn

    async def update_sync_schedule(
        self, db: Any, sync_id: UUID, cron_schedule: Optional[str], ctx: Any, uow: Any
    ) -> None:
        self._maybe_raise()
        self._track("update_sync_schedule", sync_id=sync_id, cron=cron_schedule)

    async def create_sync_without_schedule(
        self,
        db: Any,
        name: str,
        connection_id: UUID,
        collection_id: UUID,
        collection_readable_id: str,
        cron_schedule: Optional[str],
        run_immediately: bool,
        ctx: Any,
        uow: Any,
    ) -> Tuple[Any, Optional[Any]]:
        self._maybe_raise()
        self._track("create_sync_without_schedule")
        sync = MagicMock(spec=[])
        sync.id = uuid4()
        sync_job = MagicMock(spec=[]) if run_immediately else None
        if sync_job:
            sync_job.id = uuid4()
            sync_job.status = "pending"
            sync_job.sync_id = sync.id
        return sync, sync_job

    async def reconstruct_context_from_session(self, db: Any, init_session: Any) -> Any:
        self._maybe_raise()
        self._track("reconstruct_context_from_session")
        from airweave.api.context import ApiContext
        from airweave.core.logging import logger
        from airweave.core.shared_models import AuthMethod
        from airweave.schemas.organization import Organization

        now = datetime.now(timezone.utc)
        org = Organization(
            id=getattr(init_session, "organization_id", uuid4()),
            name="Test Org",
            created_at=now,
            modified_at=now,
        )
        return ApiContext(
            request_id="fake-ctx",
            organization=org,
            auth_method=AuthMethod.SYSTEM,
            auth_metadata={},
            logger=logger,
        )

    async def complete_oauth1_connection(
        self, db: Any, source_conn_shell: Any, init_session: Any, token_response: Any, ctx: Any
    ) -> Any:
        self._maybe_raise()
        self._track("complete_oauth1_connection")
        source_conn_shell.is_authenticated = True
        return source_conn_shell

    async def complete_oauth2_connection(
        self, db: Any, source_conn_shell: Any, init_session: Any, token_response: Any, ctx: Any
    ) -> Any:
        self._maybe_raise()
        self._track("complete_oauth2_connection")
        source_conn_shell.is_authenticated = True
        return source_conn_shell

    async def create_connection(
        self, db: Any, name: str, source: Any, credential_id: Optional[UUID], ctx: Any, uow: Any
    ) -> Any:
        self._maybe_raise()
        self._track("create_connection")
        conn = MagicMock(spec=[])
        conn.id = uuid4()
        return conn

    async def create_source_connection(
        self,
        db: Any,
        obj_in: Any,
        connection_id: Optional[UUID],
        collection_id: str,
        sync_id: Optional[UUID],
        config_fields: Optional[Dict[str, Any]],
        is_authenticated: bool,
        ctx: Any,
        uow: Any,
        auth_provider_id: Optional[str] = None,
        auth_provider_config: Optional[Dict[str, Any]] = None,
    ) -> Any:
        self._maybe_raise()
        self._track("create_source_connection")
        sc = MagicMock(spec=[])
        sc.id = uuid4()
        sc.organization_id = uuid4()
        sc.name = getattr(obj_in, "name", "Test")
        sc.description = None
        sc.short_name = getattr(obj_in, "short_name", "test")
        sc.readable_collection_id = collection_id
        sc.sync_id = sync_id
        sc.connection_id = connection_id
        sc.is_authenticated = is_authenticated
        sc.config_fields = config_fields
        sc.created_at = datetime.now(timezone.utc)
        sc.modified_at = datetime.now(timezone.utc)
        sc.connection_init_session_id = None
        sc.authentication_url = None
        sc.authentication_url_expiry = None
        sc.readable_auth_provider_id = auth_provider_id
        sc.is_active = True
        return sc

    async def get_collection(self, db: Any, collection_id: str, ctx: Any) -> Any:
        self._maybe_raise()
        self._track("get_collection")
        coll = MagicMock(spec=[])
        coll.id = uuid4()
        coll.readable_id = collection_id
        coll.organization_id = uuid4()
        coll.name = f"Collection {collection_id}"
        return coll

    def set_should_raise(self, exc: Optional[Exception]) -> None:
        self._should_raise = exc

    def clear(self) -> None:
        self._should_raise = None
        self.calls.clear()
