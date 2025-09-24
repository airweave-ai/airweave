"""Add search_queries table

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2025-01-27 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'b2c3d4e5f6a7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create search_queries table
    op.create_table(
        'search_queries',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('modified_at', sa.DateTime(), nullable=False),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_by_email', sa.String(), nullable=True),
        sa.Column('modified_by_email', sa.String(), nullable=True),
        
        # Collection relationship
        sa.Column('collection_id', postgresql.UUID(as_uuid=True), nullable=False),
        
        # User context (nullable for API key searches)
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
        
        # API key context (nullable for user searches)
        sa.Column('api_key_id', postgresql.UUID(as_uuid=True), nullable=True),
        
        # Search query details
        sa.Column('query_text', sa.Text(), nullable=False),
        sa.Column('query_length', sa.Integer(), nullable=False),
        
        # Search type and response configuration
        sa.Column('search_type', sa.String(length=20), nullable=False),
        sa.Column('response_type', sa.String(length=20), nullable=True),
        
        # Search parameters
        sa.Column('limit', sa.Integer(), nullable=True),
        sa.Column('offset', sa.Integer(), nullable=True),
        sa.Column('score_threshold', sa.Float(), nullable=True),
        sa.Column('recency_bias', sa.Float(), nullable=True),
        sa.Column('search_method', sa.String(length=20), nullable=True),
        
        # Performance metrics
        sa.Column('duration_ms', sa.Integer(), nullable=False),
        sa.Column('results_count', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        
        # Search configuration flags
        sa.Column('query_expansion_enabled', sa.Boolean(), nullable=True),
        sa.Column('reranking_enabled', sa.Boolean(), nullable=True),
        sa.Column('query_interpretation_enabled', sa.Boolean(), nullable=True),
        
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['organization_id'], ['organization.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['collection_id'], ['collection.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['api_key_id'], ['api_key.id'], ondelete='SET NULL'),
    )
    
    # Create indexes for performance
    op.create_index('ix_search_queries_org_created', 'search_queries', ['organization_id', 'created_at'])
    op.create_index('ix_search_queries_collection_created', 'search_queries', ['collection_id', 'created_at'])
    op.create_index('ix_search_queries_user_created', 'search_queries', ['user_id', 'created_at'])
    op.create_index('ix_search_queries_api_key_created', 'search_queries', ['api_key_id', 'created_at'])
    op.create_index('ix_search_queries_status', 'search_queries', ['status'])
    op.create_index('ix_search_queries_search_type', 'search_queries', ['search_type'])
    op.create_index('ix_search_queries_query_text', 'search_queries', ['query_text'])
    op.create_index('ix_search_queries_duration', 'search_queries', ['duration_ms'])
    op.create_index('ix_search_queries_results_count', 'search_queries', ['results_count'])


def downgrade() -> None:
    # Drop indexes first
    op.drop_index('ix_search_queries_results_count', table_name='search_queries')
    op.drop_index('ix_search_queries_duration', table_name='search_queries')
    op.drop_index('ix_search_queries_query_text', table_name='search_queries')
    op.drop_index('ix_search_queries_search_type', table_name='search_queries')
    op.drop_index('ix_search_queries_status', table_name='search_queries')
    op.drop_index('ix_search_queries_api_key_created', table_name='search_queries')
    op.drop_index('ix_search_queries_user_created', table_name='search_queries')
    op.drop_index('ix_search_queries_collection_created', table_name='search_queries')
    op.drop_index('ix_search_queries_org_created', table_name='search_queries')
    
    # Drop table
    op.drop_table('search_queries')
