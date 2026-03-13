"""Alembic environment file."""

from __future__ import with_statement

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool, text

from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
fileConfig(config.config_file_name)

# Get the absolute path of the current directory
current_dir = Path(__file__).parent.parent.absolute()

# Add the current directory to sys.path
if str(current_dir) not in sys.path:
    sys.path.append(str(current_dir))

from airweave.core.config import settings  # Import settings
from airweave.models._base import Base  # noqa

target_metadata = Base.metadata


def get_url() -> str:
    """Get the database URL from the environment variables.

    Returns:
    -------
        str: The database URL.

    """
    # Remove load_dotenv since config.py handles this
    # Convert the async URL to sync URL for alembic
    url = str(settings.SQLALCHEMY_ASYNC_DATABASE_URI)
    return url.replace("+asyncpg", "")


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = get_url()

    print(url)
    context.configure(
        url=url, target_metadata=target_metadata, literal_binds=True, compare_type=True
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    The config file is used to dress it with the right address; in particular the port
    for parallel testing purposes.
    """
    configuration = config.get_section(config.config_ini_section)
    if "sqlalchemy.url" not in configuration:  # if the url is not in the configuration
        configuration["sqlalchemy.url"] = get_url()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)

        with context.begin_transaction():
            connection.execute(text("SET lock_timeout = '10s'"))
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
