"""Alembic environment file."""

from __future__ import annotations

import logging
import re
import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config, pool, text

from alembic import context

config = context.config

fileConfig(config.config_file_name)

current_dir = Path(__file__).parent.parent.absolute()
if str(current_dir) not in sys.path:
    sys.path.append(str(current_dir))

from airweave.core.config import settings  # noqa: E402
from airweave.models._base import Base  # noqa: E402

target_metadata = Base.metadata

VERSIONS_DIR = Path(__file__).parent / "versions"


def _next_revision_id() -> str:
    """Return the next zero-padded revision ID (e.g. '0001') based on existing files."""
    highest = -1
    for path in VERSIONS_DIR.glob("*.py"):
        match = re.match(r"^(\d+)_", path.name)
        if match:
            highest = max(highest, int(match.group(1)))
    return f"{highest + 1:04d}"


def _set_incremental_rev_id(context, revision, directives):  # noqa: ARG001
    """Alembic process_revision_directives callback.

    Replaces the random hex revision ID with an incremental counter
    (0001, 0002, ...) derived from existing files in versions/.
    """
    if directives:
        script = directives[0]
        script.rev_id = _next_revision_id()


_INCREMENTAL_REV = re.compile(r"^\d{4}$")


def _stamp_legacy_revisions(connection) -> None:
    """Transition from legacy Alembic revisions to the squashed baseline.

    The migration history was squashed from 144 files into a single '0000'
    baseline.  Existing databases still carry the old revision IDs in
    ``alembic_version``.  This helper detects that and re-stamps to '0000'
    so ``alembic upgrade head`` can proceed.
    """
    log = logging.getLogger("alembic.runtime.migration")

    has_table = connection.execute(
        text(
            "SELECT EXISTS("
            "  SELECT 1 FROM information_schema.tables"
            "  WHERE table_name = 'alembic_version'"
            ")"
        )
    ).scalar()
    if not has_table:
        return  # fresh database — alembic will create the table

    rows = connection.execute(text("SELECT version_num FROM alembic_version")).fetchall()

    versions = [r[0] for r in rows]
    if not versions:
        return

    legacy = [v for v in versions if not _INCREMENTAL_REV.match(v)]
    if not legacy:
        return

    log.info("Detected legacy revisions %s — stamping to baseline '0000'", legacy)
    connection.execute(text("DELETE FROM alembic_version"))
    connection.execute(text("INSERT INTO alembic_version (version_num) VALUES ('0000')"))
    connection.commit()


def get_url() -> str:
    """Get the sync database URL for Alembic (strips +asyncpg from the async URI)."""
    url = str(settings.SQLALCHEMY_ASYNC_DATABASE_URI)
    return url.replace("+asyncpg", "")


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = get_url()
    context.configure(
        url=url, target_metadata=target_metadata, literal_binds=True, compare_type=True
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    configuration = config.get_section(config.config_ini_section)
    if "sqlalchemy.url" not in configuration:
        configuration["sqlalchemy.url"] = get_url()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        _stamp_legacy_revisions(connection)

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            process_revision_directives=_set_incremental_rev_id,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
