"""Alembic environment file."""

from __future__ import annotations

import re
import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config, pool

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
