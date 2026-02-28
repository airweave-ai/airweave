"""resolve_migration_conflicts_and_apply_changes

This migration resolves the conflicts between multiple migration branches and applies
all the necessary changes to bring the database to the correct state.

The conflicts were caused by:
1. Multiple migration branches trying to modify the same tables
2. Search queries table being refactored while other migrations tried to alter it
3. Overlapping revision dependencies

This migration consolidates all the necessary changes:
- Applies the search_queries refactoring (from d4e5f6g7h8i9 and d1e2f3g4h5i6)
- Adds is_admin column to user table (from 9a977647c5a4)
- Fixes connection cascade constraints (from 9a977647c5a4)
- Applies other necessary schema changes

Revision ID: ab5c202f5d68
Revises: c60291fb2129
Create Date: 2025-10-07 16:10:25.859371

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = 'ab5c202f5d68'
down_revision = 'c60291fb2129'  # Start from the last known good migration
branch_labels = None
depends_on = None


def upgrade():
    """Apply all necessary changes to resolve migration conflicts."""

    # 1. Apply search_queries refactoring (from d4e5f6g7h8i9 and d1e2f3g4h5i6)
    # First, check if the search_queries table exists and what columns it has
    connection = op.get_bind()

    # Check if search_queries table exists
    result = connection.execute(sa.text("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_name = 'search_queries'
        );
    """))
    table_exists = result.scalar()

    if table_exists:
        # Check what columns exist
        result = connection.execute(sa.text("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'search_queries'
            ORDER BY ordinal_position;
        """))
        existing_columns = [row[0] for row in result.fetchall()]

        # If old columns exist, apply the refactoring
        if 'search_type' in existing_columns:
            print("Applying search_queries refactoring...")

            # Drop old indexes
            try:
                op.drop_index('ix_search_queries_status', table_name='search_queries')
            except Exception:
                pass
            try:
                op.drop_index('ix_search_queries_search_type', table_name='search_queries')
            except Exception:
                pass

            # Add new columns with defaults for existing rows
            op.add_column('search_queries', sa.Column('is_streaming', sa.Boolean(), nullable=False, server_default='false'))
            op.add_column('search_queries', sa.Column('retrieval_strategy', sa.String(length=20), nullable=True))
            op.add_column('search_queries', sa.Column('temporal_relevance', sa.Float(), nullable=True))
            op.add_column('search_queries', sa.Column('expand_query', sa.Boolean(), nullable=True))
            op.add_column('search_queries', sa.Column('interpret_filters', sa.Boolean(), nullable=True))
            op.add_column('search_queries', sa.Column('rerank', sa.Boolean(), nullable=True))
            op.add_column('search_queries', sa.Column('generate_answer', sa.Boolean(), nullable=True))

            # Migrate data from old columns to new columns where possible
            op.execute("""
                UPDATE search_queries
                SET retrieval_strategy = search_method
                WHERE search_method IS NOT NULL
            """)

            op.execute("""
                UPDATE search_queries
                SET temporal_relevance = recency_bias
                WHERE recency_bias IS NOT NULL
            """)

            op.execute("""
                UPDATE search_queries
                SET expand_query = query_expansion_enabled
                WHERE query_expansion_enabled IS NOT NULL
            """)

            op.execute("""
                UPDATE search_queries
                SET rerank = reranking_enabled
                WHERE reranking_enabled IS NOT NULL
            """)

            op.execute("""
                UPDATE search_queries
                SET interpret_filters = query_interpretation_enabled
                WHERE query_interpretation_enabled IS NOT NULL
            """)

            op.execute("""
                UPDATE search_queries
                SET generate_answer = CASE
                    WHEN response_type = 'completion' THEN true
                    WHEN response_type = 'raw' THEN false
                    ELSE NULL
                END
                WHERE response_type IS NOT NULL
            """)

            # Drop old columns
            op.drop_column('search_queries', 'search_type')
            op.drop_column('search_queries', 'response_type')
            op.drop_column('search_queries', 'score_threshold')
            op.drop_column('search_queries', 'recency_bias')
            op.drop_column('search_queries', 'search_method')
            op.drop_column('search_queries', 'status')
            op.drop_column('search_queries', 'query_expansion_enabled')
            op.drop_column('search_queries', 'reranking_enabled')
            op.drop_column('search_queries', 'query_interpretation_enabled')

            # Create new indexes
            op.create_index('ix_search_queries_is_streaming', 'search_queries', ['is_streaming'])
            op.create_index('ix_search_queries_retrieval_strategy', 'search_queries', ['retrieval_strategy'])

        # Add the filter column if it doesn't exist
        if 'filter' not in existing_columns:
            op.add_column('search_queries', sa.Column('filter', sa.JSON(), nullable=True))

        # Set defaults for existing NULL values and make columns NOT NULL
        op.execute("""
            UPDATE search_queries
            SET
                retrieval_strategy = COALESCE(retrieval_strategy, 'hybrid'),
                temporal_relevance = COALESCE(temporal_relevance, 0.3),
                expand_query = COALESCE(expand_query, true),
                interpret_filters = COALESCE(interpret_filters, false),
                rerank = COALESCE(rerank, true),
                generate_answer = COALESCE(generate_answer, false),
                "limit" = COALESCE("limit", 1000),
                "offset" = COALESCE("offset", 0)
        """)

        # Make columns NOT NULL (except filter which is truly optional)
        op.alter_column('search_queries', 'retrieval_strategy',
                        existing_type=sa.String(length=20),
                        nullable=False)
        op.alter_column('search_queries', 'temporal_relevance',
                        existing_type=sa.Float(),
                        nullable=False)
        op.alter_column('search_queries', 'expand_query',
                        existing_type=sa.Boolean(),
                        nullable=False)
        op.alter_column('search_queries', 'interpret_filters',
                        existing_type=sa.Boolean(),
                        nullable=False)
        op.alter_column('search_queries', 'rerank',
                        existing_type=sa.Boolean(),
                        nullable=False)
        op.alter_column('search_queries', 'generate_answer',
                        existing_type=sa.Boolean(),
                        nullable=False)

        # Make limit and offset NOT NULL
        op.alter_column('search_queries', 'limit',
                        existing_type=sa.Integer(),
                        nullable=False)
        op.alter_column('search_queries', 'offset',
                        existing_type=sa.Integer(),
                        nullable=False)

    # 2. Add is_admin column to user table (from 9a977647c5a4)
    # Check if is_admin column already exists
    result = connection.execute(sa.text("""
        SELECT EXISTS (
            SELECT FROM information_schema.columns
            WHERE table_schema = 'public'
            AND table_name = 'user'
            AND column_name = 'is_admin'
        );
    """))
    is_admin_exists = result.scalar()

    if not is_admin_exists:
        print("Adding is_admin column to user table...")
        # Add is_admin column as nullable first
        op.add_column('user', sa.Column('is_admin', sa.Boolean(), nullable=True))

        # Set default values based on email domain
        # First, set all users to is_admin = false
        op.execute("UPDATE \"user\" SET is_admin = false")

        # Then, set users with @airweave.ai email to is_admin = true
        op.execute("UPDATE \"user\" SET is_admin = true WHERE email LIKE '%@airweave.ai' OR email = 'admin@example.com'")

        # Now make the column NOT NULL
        op.alter_column('user', 'is_admin', nullable=False)

    # 3. Fix connection cascade constraints (from 9a977647c5a4)
    print("Fixing connection cascade constraints...")
    try:
        # Check if the constraint exists before trying to drop it
        result = connection.execute(sa.text("""
            SELECT EXISTS (
                SELECT FROM information_schema.table_constraints
                WHERE constraint_name = 'connection_organization_id_fkey'
                AND table_name = 'connection'
            );
        """))
        constraint_exists = result.scalar()

        if constraint_exists:
            op.drop_constraint(op.f('connection_organization_id_fkey'), 'connection', type_='foreignkey')
            print("Dropped existing connection constraint")

        op.create_foreign_key(None, 'connection', 'organization', ['organization_id'], ['id'], ondelete='CASCADE')
        print("Created new connection constraint with CASCADE")
    except Exception as e:
        print(f"Warning: Could not fix connection constraints: {e}")
        pass

    # 4. Fix connection_init_session index (from 9a977647c5a4)
    try:
        # Check if the index exists before trying to drop it
        result = connection.execute(sa.text("""
            SELECT EXISTS (
                SELECT FROM pg_indexes
                WHERE indexname = 'idx_connection_init_session_redirect_session_id'
            );
        """))
        index_exists = result.scalar()

        if index_exists:
            op.drop_index(op.f('idx_connection_init_session_redirect_session_id'), table_name='connection_init_session')
            print("Dropped connection_init_session index")
    except Exception as e:
        print(f"Warning: Could not drop connection_init_session index: {e}")
        pass


def downgrade():
    """Reverse the changes made in upgrade."""

    # Remove is_admin column
    try:
        op.drop_column('user', 'is_admin')
    except Exception:
        pass

    # Restore connection constraints
    try:
        op.drop_constraint(op.f('connection_organization_id_fkey'), 'connection', type_='foreignkey')
        op.create_foreign_key(op.f('connection_organization_id_fkey'), 'connection', 'organization', ['organization_id'], ['id'])
    except Exception:
        pass

    # Restore connection_init_session index
    try:
        op.create_index(op.f('idx_connection_init_session_redirect_session_id'), 'connection_init_session', ['redirect_session_id'], unique=False)
    except Exception:
        pass

    # Note: We don't downgrade the search_queries changes as they represent a major refactoring
    # that would be complex to reverse and may not be necessary
