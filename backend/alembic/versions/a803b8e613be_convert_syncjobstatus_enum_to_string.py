"""convert_syncjobstatus_enum_to_string

Revision ID: a803b8e613be
Revises: 51f41d4cb9db
Create Date: 2025-09-22 17:22:19.462000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "a803b8e613be"
down_revision = "51f41d4cb9db"
branch_labels = None
depends_on = None


def upgrade():
    """Convert syncjobstatus enum to string column for flexibility.

    The enum approach has caused issues with mismatched values between Python and database.
    Converting to string allows more flexibility and avoids enum value synchronization issues.
    """
    # Step 1: Add a temporary column with string type
    op.add_column("sync_job", sa.Column("status_temp", sa.String(50), nullable=True))

    # Step 2: Copy and map the enum values to string values
    # Map database enum values to Python enum values (lowercase)
    # Note: CREATED doesn't exist in the current database enum
    op.execute(
        """
        UPDATE sync_job
        SET status_temp = CASE
            WHEN status = 'PENDING' THEN 'pending'
            WHEN status = 'IN_PROGRESS' THEN 'running'
            WHEN status = 'COMPLETED' THEN 'completed'
            WHEN status = 'FAILED' THEN 'failed'
            WHEN status = 'CANCELLED' THEN 'cancelled'
            ELSE LOWER(status::text)
        END
    """
    )

    # Step 3: Drop the old enum column
    op.drop_column("sync_job", "status")

    # Step 4: Rename the temporary column to status
    op.alter_column("sync_job", "status_temp", new_column_name="status")

    # Step 5: Set NOT NULL constraint and default value
    op.alter_column("sync_job", "status", nullable=False)
    op.execute("ALTER TABLE sync_job ALTER COLUMN status SET DEFAULT 'pending'")

    # Step 6: Drop the enum type since it's no longer used
    op.execute("DROP TYPE IF EXISTS syncjobstatus CASCADE")


def downgrade():
    """Convert string column back to enum type.

    This recreates the enum and converts the string values back.
    """
    # Step 1: Create the enum type
    op.execute(
        """
        CREATE TYPE syncjobstatus AS ENUM (
            'PENDING',
            'IN_PROGRESS',
            'COMPLETED',
            'FAILED',
            'CANCELLED'
        )
    """
    )

    # Step 2: Add temporary enum column
    op.execute(
        """
        ALTER TABLE sync_job
        ADD COLUMN status_enum syncjobstatus
    """
    )

    # Step 3: Map string values back to enum values
    op.execute(
        """
        UPDATE sync_job
        SET status_enum = CASE
            WHEN status = 'pending' THEN 'PENDING'::syncjobstatus
            WHEN status = 'running' THEN 'IN_PROGRESS'::syncjobstatus
            WHEN status = 'completed' THEN 'COMPLETED'::syncjobstatus
            WHEN status = 'failed' THEN 'FAILED'::syncjobstatus
            WHEN status = 'cancelled' THEN 'CANCELLED'::syncjobstatus
            WHEN status = 'created' THEN 'PENDING'::syncjobstatus
            ELSE 'PENDING'::syncjobstatus
        END
    """
    )

    # Step 4: Drop the string column
    op.drop_column("sync_job", "status")

    # Step 5: Rename enum column to status
    op.alter_column("sync_job", "status_enum", new_column_name="status")

    # Step 6: Set NOT NULL and default
    op.alter_column("sync_job", "status", nullable=False)
    op.execute("ALTER TABLE sync_job ALTER COLUMN status SET DEFAULT 'PENDING'::syncjobstatus")
