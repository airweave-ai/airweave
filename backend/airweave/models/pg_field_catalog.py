"""Models for per-source-connection PostgreSQL field catalog."""

from sqlalchemy import JSON, UUID, Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from airweave.models._base import OrganizationBase


class PgFieldCatalogTable(OrganizationBase):
    """Catalog of PostgreSQL tables for a specific source connection.

    Rows are scoped by organization and `source_connection_id` to maintain
    multi-tenant isolation. We keep a single row per (source_connection, schema, table).
    """

    __tablename__ = "pg_field_catalog_table"

    # Link back to the source connection that owns this schema snapshot
    source_connection_id: Mapped[UUID] = mapped_column(
        UUID, ForeignKey("source_connection.id", ondelete="CASCADE"), nullable=False
    )

    schema_name: Mapped[str] = mapped_column(String, nullable=False)
    table_name: Mapped[str] = mapped_column(String, nullable=False)

    # Optional: name of the column selected to act as recency cursor for this table
    recency_column: Mapped[str | None] = mapped_column(String, nullable=True)

    # Primary key columns for convenience (duplicated from columns for easy lookup)
    primary_keys: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)

    # Foreign keys as a list of objects: {column, ref_schema, ref_table, ref_column}
    foreign_keys: Mapped[list[dict] | None] = mapped_column(JSON, nullable=True)

    # Relationship to columns
    columns: Mapped[list["PgFieldCatalogColumn"]] = relationship(
        "PgFieldCatalogColumn",
        back_populates="table",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "source_connection_id",
            "schema_name",
            "table_name",
            name="uq_pg_field_catalog_table_scope",
        ),
    )


class PgFieldCatalogColumn(OrganizationBase):
    """Catalog of columns belonging to a `PgFieldCatalogTable`."""

    __tablename__ = "pg_field_catalog_column"

    table_id: Mapped[UUID] = mapped_column(
        UUID, ForeignKey("pg_field_catalog_table.id", ondelete="CASCADE"), nullable=False
    )

    column_name: Mapped[str] = mapped_column(String, nullable=False)

    # information_schema types
    data_type: Mapped[str | None] = mapped_column(String, nullable=True)
    udt_name: Mapped[str | None] = mapped_column(String, nullable=True)

    is_nullable: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    default_value: Mapped[str | None] = mapped_column(String, nullable=True)
    ordinal_position: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Flags / relationships
    is_primary_key: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_foreign_key: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ref_schema: Mapped[str | None] = mapped_column(String, nullable=True)
    ref_table: Mapped[str | None] = mapped_column(String, nullable=True)
    ref_column: Mapped[str | None] = mapped_column(String, nullable=True)

    # For enums (USER-DEFINED types), keep the value set if available
    enum_values: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)

    # Heuristic flag for UI/LLM to prefer columns for filtering
    is_filterable: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationship back to table
    table: Mapped[PgFieldCatalogTable] = relationship(
        PgFieldCatalogTable, back_populates="columns", lazy="noload"
    )

    __table_args__ = (
        UniqueConstraint("table_id", "column_name", name="uq_pg_field_catalog_column_name"),
    )
