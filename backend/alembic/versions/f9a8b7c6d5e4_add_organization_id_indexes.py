"""Add organization_id indexes to org-scoped tables

Revision ID: f9a8b7c6d5e4
Revises: cb4843afd172
Create Date: 2025-01-12 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = 'f9a8b7c6d5e4'
down_revision = '90780c02944e' 
branch_labels = None
depends_on = None


# Tables that inherit from OrganizationBase and should get the index
# Entity is explicitly excluded (too large, better indexes on sync_id)
# Built from: grep "class.*OrganizationBase" airweave/models/*.py
TABLES_TO_INDEX = [
    'api_key',                      # APIKey
    'collection',                   # Collection
    'connection_init_session',      # ConnectionInitSession
    'integration_credential',       # IntegrationCredential
    'pg_field_catalog_table',       # PgFieldCatalogTable
    'pg_field_catalog_column',      # PgFieldCatalogColumn
    'redirect_session',             # RedirectSession
    'search_queries',               # SearchQuery (note: plural tablename)
    'source_connection',            # SourceConnection
    'source_rate_limits',           # SourceRateLimit (note: plural tablename)
    'sync',                         # Sync
    'sync_cursor',                  # SyncCursor
    'sync_job',                     # SyncJob
    'usage',                        # Usage
    'user_organization',            # UserOrganization (has org_id too)
]


def upgrade() -> None:
    """Add organization_id indexes for efficient org-scoped queries."""
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_tables = inspector.get_table_names()
    
    for table_name in TABLES_TO_INDEX:
        # Skip if table doesn't exist
        if table_name not in existing_tables:
            print(f"Skipping {table_name} - table does not exist")
            continue
            
        index_name = f'ix_{table_name}_organization_id'
        
        # Check if index already exists
        existing_indexes = [idx['name'] for idx in inspector.get_indexes(table_name)]
        if index_name in existing_indexes:
            print(f"Skipping {index_name} - index already exists")
            continue
            
        print(f"Creating index {index_name} on {table_name}.organization_id")
        op.create_index(
            index_name,
            table_name,
            ['organization_id'],
            unique=False,
            postgresql_using='btree'
        )


def downgrade() -> None:
    """Remove organization_id indexes."""
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_tables = inspector.get_table_names()
    
    for table_name in TABLES_TO_INDEX:
        if table_name not in existing_tables:
            continue
            
        index_name = f'ix_{table_name}_organization_id'
        existing_indexes = [idx['name'] for idx in inspector.get_indexes(table_name)]
        
        if index_name in existing_indexes:
            op.drop_index(index_name, table_name=table_name)

