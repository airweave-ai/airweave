"""Template implementation for a Postgres connector bongo."""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from typing import Any, Dict, List, Optional

import asyncpg

from monke.bongos.base_bongo import BaseBongo
from monke.utils.logging import get_logger


class PostgresBongo(BaseBongo):
    """Bongo that exercises a Postgres database by creating/updating rows.

    This template mirrors the structure of other bongos so you can flesh out the
    actual SQL that fits your schema. The key responsibilities are:

    1. Ensure a workspace table exists that can be freely mutated in tests.
    2. Create a handful of rows embedding short verification tokens.
    3. Update and delete those rows while respecting rate limits.
    4. Track everything in ``self.created_entities`` for deterministic cleanup.
    """

    connector_type = "postgresql"

    def __init__(self, credentials: Dict[str, Any], **kwargs: Any) -> None:
        super().__init__(credentials)
        # Connection info: prefer DSN, fall back to discrete fields
        self.connection_dsn: Optional[str] = credentials.get("connection_string")
        self.host: Optional[str] = credentials.get("host")
        self.port: int = int(credentials.get("port", 5432))
        self.database: str = credentials.get("database", "postgres")
        self.user: Optional[str] = credentials.get("user")
        self.password: Optional[str] = credentials.get("password")

        # Runtime configuration
        self.entity_count: int = int(kwargs.get("entity_count", 3))
        self.schema: str = kwargs.get("schema", "public")
        self.table_name: str = kwargs.get("table_name", "monke_test_entities")
        self.max_concurrency: int = int(kwargs.get("max_concurrency", 2))
        self.update_count: int = int(kwargs.get("update_count", 3))

        rate_limit_ms = int(kwargs.get("rate_limit_delay_ms", 200))
        self.rate_limit_delay: float = rate_limit_ms / 1000.0
        self._rate_limit_lock = asyncio.Lock()
        self.last_request_time = 0.0

        # Connection options (ssl, prepared statements, etc.)
        raw_ssl_mode = credentials.get("ssl_mode") or kwargs.get("ssl_mode")
        if isinstance(raw_ssl_mode, str):
            raw_ssl_mode = raw_ssl_mode.strip() or None
        self.ssl_mode: Optional[str] = raw_ssl_mode

        raw_ssl = credentials.get("ssl")
        if isinstance(raw_ssl, str):
            lowered = raw_ssl.strip().lower()
            if lowered in {"false", "0", "no", "disable"}:
                raw_ssl = False
            elif lowered in {"true", "1", "yes", "require"}:
                raw_ssl = True
        self.ssl = raw_ssl

        self.options: Dict[str, Any] = kwargs.get("options", {})

        # Runtime state
        self._pool: Optional[asyncpg.Pool] = None
        self._records: List[Dict[str, Any]] = []

        self.logger = get_logger("postgres_bongo")

    async def create_entities(self) -> List[Dict[str, Any]]:
        """Insert synthetic entities into Postgres."""

        self.logger.info(
            f"🥁 Creating {self.entity_count} Postgres rows in {self.schema}.{self.table_name}"
        )

        await self._ensure_pool()
        await self._ensure_table()

        entities: List[Dict[str, Any]] = []
        for _ in range(self.entity_count):
            await self._rate_limit()
            token = uuid.uuid4().hex[:8]
            entity = await self._create_row(token)
            entities.append(entity)
            self.created_entities.append(entity)
            self._records.append(entity)

        return entities

    async def update_entities(self) -> List[Dict[str, Any]]:
        """Update a subset of rows by regenerating their payload."""

        await self._ensure_pool()

        if not self._records:
            self.logger.warning("⚠️ No Postgres rows cached; call create_entities first")
            return []

        count = min(self.update_count, len(self._records))
        self.logger.info(f"📝 Updating {count} Postgres rows")

        updated: List[Dict[str, Any]] = []
        for record in self._records[:count]:
            await self._rate_limit()
            entity = await self._update_row(record)
            updated.append(entity)

        return updated

    async def delete_entities(self) -> List[str]:
        """Delete every row that was created by this bongo."""

        self.logger.info("🗑️ Deleting all Postgres rows created by this run")
        return await self.delete_specific_entities(self.created_entities)

    async def delete_specific_entities(self, entities: List[Dict[str, Any]]) -> List[str]:
        """Delete a provided set of rows."""

        if not entities:
            self.logger.info("[DELETE TRACE] delete_specific_entities: no entities provided")
            return []

        await self._ensure_pool()
        deleted: List[str] = []

        self.logger.info(
            "[DELETE TRACE] delete_specific_entities: starting delete for %d entities",
            len(entities),
        )

        for entity in entities:
            await self._rate_limit()

            # Try to log what we *think* the primary key is
            candidate_id = (
                entity.get("id")
                or entity.get("parent_id")
                or entity.get("document_id")
            )
            self.logger.info(
                "[DELETE TRACE] delete_specific_entities: attempting delete for entity=%s raw=%s",
                candidate_id,
                entity,
            )

            deleted_id = await self._delete_row(entity)

            self.logger.info(
                "[DELETE TRACE] delete_specific_entities: _delete_row returned deleted_id=%s "
                "for candidate_id=%s",
                deleted_id,
                candidate_id,
            )

            if deleted_id:
                deleted.append(deleted_id)
            else:
                self.logger.warning(
                    "[DELETE TRACE] delete_specific_entities: no id returned from _delete_row "
                    "for candidate_id=%s",
                    candidate_id,
                )

        self.logger.info(
            "[DELETE TRACE] delete_specific_entities: finished. deleted_ids=%s",
            deleted,
        )
        return deleted

    async def cleanup(self) -> None:
        """Emergency cleanup hook (e.g., drop table)."""

        await self._ensure_pool()
        self.logger.info("🧹 Cleaning up Postgres workspace table")
        await self._cleanup_table()

    # Helper methods -------------------------------------------------
    async def _ensure_pool(self) -> None:
        if self._pool:
            return

        dsn = self.connection_dsn or self._build_dsn()
        pool_kwargs = {
            "dsn": dsn,
            "min_size": 1,
            "max_size": self.max_concurrency,
        }
        pool_kwargs.update(self._pool_options())
        self._pool = await asyncpg.create_pool(**pool_kwargs)

    async def _ensure_table(self) -> None:
        assert self._pool is not None
        create_sql = f"""
        CREATE TABLE IF NOT EXISTS {self._qualified_table()} (
            id UUID PRIMARY KEY,
            token TEXT NOT NULL UNIQUE,
            payload JSONB NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            deleted_at TIMESTAMPTZ
        );
        """
        async with self._pool.acquire() as conn:
            await conn.execute(create_sql)

    async def _create_row(self, token: str) -> Dict[str, Any]:
        assert self._pool is not None
        payload = {"token": token, "notes": "TODO: domain-specific fields"}
        payload_json = json.dumps(payload)
        row_id = uuid.uuid4()
        insert_sql = f"""
        INSERT INTO {self._qualified_table()} (id, token, payload)
        VALUES ($1, $2, $3::jsonb)
        RETURNING id, token, payload, created_at;
        """
        async with self._pool.acquire() as conn:
            record = await conn.fetchrow(insert_sql, row_id, token, payload_json)
        record_payload = record["payload"]
        if isinstance(record_payload, str):
            record_payload = json.loads(record_payload)
        entity = {
            "type": "row",
            "id": str(record["id"]),
            "token": record["token"],
            "expected_content": record["token"],
            "payload": dict(record_payload),
        }
        self.logger.info(f"✅ Inserted Postgres row {entity['id']}")
        return entity

    async def _update_row(self, entity: Dict[str, Any]) -> Dict[str, Any]:
        assert self._pool is not None
        new_notes = f"updated-{uuid.uuid4().hex[:4]}"
        update_sql = f"""
        UPDATE {self._qualified_table()}
        SET payload = payload || jsonb_build_object('notes', $2::text),
            updated_at = NOW()
        WHERE id = $1
        RETURNING id, token, payload, updated_at;
        """
        async with self._pool.acquire() as conn:
            record = await conn.fetchrow(update_sql, entity["id"], new_notes)
        record_payload = record["payload"]
        if isinstance(record_payload, str):
            record_payload = json.loads(record_payload)
        updated_entity = {
            "type": "row",
            "id": str(record["id"]),
            "token": record["token"],
            "expected_content": record["token"],
            "payload": dict(record_payload),
        }
        self.logger.info(f"📝 Updated Postgres row {updated_entity['id']}")
        return updated_entity

    async def _delete_row(self, entity: Dict[str, Any]) -> Optional[str]:
        assert self._pool is not None
        delete_sql = f"DELETE FROM {self._qualified_table()} WHERE id = $1 RETURNING id;"
        async with self._pool.acquire() as conn:
            record = await conn.fetchrow(delete_sql, entity["id"])
        if record:
            self.logger.info(f"🗑️ Deleted Postgres row {record['id']}")
            return str(record["id"])
        return None

    async def _cleanup_table(self) -> None:
        assert self._pool is not None
        truncate_sql = f"TRUNCATE {self._qualified_table()}"
        async with self._pool.acquire() as conn:
            await conn.execute(truncate_sql)

    async def _rate_limit(self) -> None:
        async with self._rate_limit_lock:
            now = time.time()
            delta = now - self.last_request_time
            if delta < self.rate_limit_delay:
                await asyncio.sleep(self.rate_limit_delay - delta)
            self.last_request_time = time.time()

    def _qualified_table(self) -> str:
        return f"{self.schema}.{self.table_name}"

    def _pool_options(self) -> Dict[str, Any]:
        opts = dict(self.options)
        if self.ssl is not None:
            opts["ssl"] = self.ssl
        elif self.ssl_mode:
            mode = self.ssl_mode.lower()
            if mode == "disable":
                opts["ssl"] = False
            elif mode == "require":
                opts["ssl"] = True
        return opts

    def _build_dsn(self) -> str:
        if not self.host or not self.user:
            raise ValueError("Postgres credentials need host/user or connection_string")
        password = self.password or ""
        base = (
            f"postgresql://{self.user}:{password}@{self.host}:{self.port}/{self.database}"
        )
        if self.ssl is False:
            return f"{base}?sslmode=disable"
        if self.ssl_mode:
            return f"{base}?sslmode={self.ssl_mode}"
        return base
