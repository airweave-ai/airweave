"""Add sync_config columns to collection, sync, and sync_job.

Renames execution_config_json -> sync_config on sync_job.
Adds sync_config JSONB column to collection and sync tables.
Migrates existing data from flat to nested structure.

Revision ID: n7o8p9q0r1s2
Revises: m6n7o8p9q0r1
Create Date: 2026-01-10 14:00:00.000000

"""

import json

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = "n7o8p9q0r1s2"
down_revision = "m6n7o8p9q0r1"
branch_labels = None
depends_on = None


def upgrade():
    """Add sync_config columns and migrate data structure."""
    # Step 1: Rename execution_config_json -> sync_config on sync_job
    op.alter_column(
        "sync_job",
        "execution_config_json",
        new_column_name="sync_config",
    )

    # Step 2: Clean up JSON null values and migrate data structure
    connection = op.get_bind()
    
    # First, convert JSON null values to SQL NULL
    connection.execute(
        sa.text("UPDATE sync_job SET sync_config = NULL WHERE jsonb_typeof(sync_config) = 'null'")
    )
    
    # Get all sync_jobs with actual config objects
    result = connection.execute(
        sa.text("SELECT id, sync_config FROM sync_job WHERE sync_config IS NOT NULL")
    )
    
    for row in result:
        job_id, old_config = row
        if not old_config:
            continue
            
        # Check if already in new format (has nested keys)
        if any(key in old_config for key in ["destinations", "handlers", "cursor", "behavior"]):
            # Already migrated, skip
            continue
        
        # Transform flat structure to nested structure
        new_config = {
            "destinations": {
                "skip_qdrant": old_config.get("skip_qdrant", False),
                "skip_vespa": old_config.get("skip_vespa", False),
                "target_destinations": old_config.get("target_destinations"),
                "exclude_destinations": old_config.get("exclude_destinations"),
            },
            "handlers": {
                "enable_vector_handlers": old_config.get("enable_vector_handlers", True),
                "enable_raw_data_handler": old_config.get("enable_raw_data_handler", True),
                "enable_postgres_handler": old_config.get("enable_postgres_handler", True),
            },
            "cursor": {
                "skip_load": old_config.get("skip_cursor_load", False),
                "skip_updates": old_config.get("skip_cursor_updates", False),
            },
            "behavior": {
                "skip_hash_comparison": old_config.get("skip_hash_comparison", False),
                "replay_from_arf": old_config.get("replay_from_arf", False),
            },
        }
        
        # Update the row with new structure
        connection.execute(
            sa.text("UPDATE sync_job SET sync_config = :config WHERE id = :id"),
            {"config": json.dumps(new_config), "id": str(job_id)}
        )

    # Step 3: Add sync_config to collection
    op.add_column(
        "collection",
        sa.Column("sync_config", postgresql.JSONB(), nullable=True),
    )

    # Step 4: Add sync_config to sync
    op.add_column(
        "sync",
        sa.Column("sync_config", postgresql.JSONB(), nullable=True),
    )


def downgrade():
    """Remove sync_config columns and revert data structure."""
    # Step 1: Migrate sync_job data from nested to flat structure
    connection = op.get_bind()
    
    result = connection.execute(
        sa.text("SELECT id, sync_config FROM sync_job WHERE sync_config IS NOT NULL")
    )
    
    for row in result:
        job_id, new_config = row
        if not new_config:
            continue
            
        # Check if already in old format (flat keys)
        if "destinations" not in new_config:
            # Already in old format, skip
            continue
        
        # Transform nested structure back to flat structure
        destinations = new_config.get("destinations", {})
        handlers = new_config.get("handlers", {})
        cursor = new_config.get("cursor", {})
        behavior = new_config.get("behavior", {})
        
        old_config = {
            "skip_qdrant": destinations.get("skip_qdrant", False),
            "skip_vespa": destinations.get("skip_vespa", False),
            "target_destinations": destinations.get("target_destinations"),
            "exclude_destinations": destinations.get("exclude_destinations"),
            "enable_vector_handlers": handlers.get("enable_vector_handlers", True),
            "enable_raw_data_handler": handlers.get("enable_raw_data_handler", True),
            "enable_postgres_handler": handlers.get("enable_postgres_handler", True),
            "skip_cursor_load": cursor.get("skip_load", False),
            "skip_cursor_updates": cursor.get("skip_updates", False),
            "skip_hash_comparison": behavior.get("skip_hash_comparison", False),
            "replay_from_arf": behavior.get("replay_from_arf", False),
        }
        
        connection.execute(
            sa.text("UPDATE sync_job SET sync_config = :config WHERE id = :id"),
            {"config": json.dumps(old_config), "id": str(job_id)}
        )

    # Step 2: Remove sync_config from sync
    op.drop_column("sync", "sync_config")

    # Step 3: Remove sync_config from collection
    op.drop_column("collection", "sync_config")

    # Step 4: Rename sync_config -> execution_config_json on sync_job
    op.alter_column(
        "sync_job",
        "sync_config",
        new_column_name="execution_config_json",
    )
