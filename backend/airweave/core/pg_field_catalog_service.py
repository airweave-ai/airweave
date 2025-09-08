"""Service for maintaining PostgreSQL field catalog per source connection."""

from __future__ import annotations

from typing import Any, Dict, List
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from airweave.core.logging import ContextualLogger
from airweave.models.pg_field_catalog import PgFieldCatalogColumn, PgFieldCatalogTable


async def overwrite_catalog(
    db: AsyncSession,
    organization_id: UUID,
    source_connection_id: UUID,
    snapshot: List[Dict[str, Any]],
    logger: ContextualLogger | None = None,
) -> None:
    """Overwrite the catalog for a given source connection with a fresh snapshot.

    Args:
        db: Async SQLAlchemy session
        organization_id: Tenant organization ID
        source_connection_id: The source connection that owns this catalog
        snapshot: List of table snapshots with columns/keys, produced by the source
        logger: Optional logger
    """
    if logger:
        logger.info(
            "Refreshing Postgres field catalog (tables=%d) for source_connection=%s",
            len(snapshot),
            str(source_connection_id),
        )

    # Delete existing tables for this scope (cascade will remove columns)
    existing_ids = await db.scalars(
        select(PgFieldCatalogTable.id).where(
            PgFieldCatalogTable.organization_id == organization_id,
            PgFieldCatalogTable.source_connection_id == source_connection_id,
        )
    )
    ids = list(existing_ids)
    if ids:
        await db.execute(delete(PgFieldCatalogTable).where(PgFieldCatalogTable.id.in_(ids)))
        await db.flush()

    # Insert new snapshot
    for table in snapshot:
        table_row = PgFieldCatalogTable(
            organization_id=organization_id,
            source_connection_id=source_connection_id,
            schema_name=table["schema_name"],
            table_name=table["table_name"],
            recency_column=table.get("recency_column"),
            primary_keys=table.get("primary_keys"),
            foreign_keys=table.get("foreign_keys"),
        )
        db.add(table_row)
        await db.flush()  # ensure table_row.id is available

        for col in table.get("columns", []):
            db.add(
                PgFieldCatalogColumn(
                    organization_id=organization_id,
                    table_id=table_row.id,
                    column_name=col["column_name"],
                    data_type=col.get("data_type"),
                    udt_name=col.get("udt_name"),
                    is_nullable=bool(col.get("is_nullable", True)),
                    default_value=col.get("default_value"),
                    ordinal_position=col.get("ordinal_position"),
                    is_primary_key=bool(col.get("is_primary_key", False)),
                    is_foreign_key=bool(col.get("is_foreign_key", False)),
                    ref_schema=col.get("ref_schema"),
                    ref_table=col.get("ref_table"),
                    ref_column=col.get("ref_column"),
                    enum_values=col.get("enum_values"),
                    is_filterable=bool(col.get("is_filterable", True)),
                )
            )

    await db.flush()
    if logger:
        logger.info("Postgres field catalog refresh complete")
