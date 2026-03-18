"""add oauth claim token fields

Revision ID: 8bdd5dcf7837
Revises: a1b2c3d4e5f7
Create Date: 2026-03-13 13:28:16.019661

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "8bdd5dcf7837"
down_revision = "a1b2c3d4e5f7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "connection_init_session",
        sa.Column(
            "initiator_user_id",
            sa.Uuid(),
            sa.ForeignKey("user.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "connection_init_session",
        sa.Column("initiator_session_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "connection_init_session",
        sa.Column("claim_token_hash", sa.String(64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("connection_init_session", "claim_token_hash")
    op.drop_column("connection_init_session", "initiator_session_id")
    op.drop_column("connection_init_session", "initiator_user_id")
