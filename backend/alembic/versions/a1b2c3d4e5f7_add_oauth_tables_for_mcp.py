"""add oauth tables for mcp

Revision ID: a1b2c3d4e5f7
Revises: p2q3r4s5t6u7
Create Date: 2026-01-29 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f7"
down_revision = "p2q3r4s5t6u7"  # Update this to the actual latest revision
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create OAuth 2.1 tables for MCP authorization server."""
    
    # Create oauth_client table
    op.create_table(
        "oauth_client",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("modified_at", sa.DateTime(), nullable=False),
        sa.Column("client_id", sa.String(), nullable=False),
        sa.Column("client_secret_hash", sa.String(), nullable=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("redirect_uris", postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column("grant_types", postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column("client_type", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("client_id"),
    )
    op.create_index(op.f("ix_oauth_client_client_id"), "oauth_client", ["client_id"], unique=False)
    
    # Create oauth_authorization_code table
    op.create_table(
        "oauth_authorization_code",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("modified_at", sa.DateTime(), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by_email", sa.String(), nullable=True),
        sa.Column("modified_by_email", sa.String(), nullable=True),
        sa.Column("code_hash", sa.String(), nullable=False),
        sa.Column("client_id", sa.String(), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("collection_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("redirect_uri", sa.String(), nullable=False),
        sa.Column("scope", sa.String(), nullable=False),
        sa.Column("code_challenge", sa.String(), nullable=True),
        sa.Column("code_challenge_method", sa.String(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["client_id"], ["oauth_client.client_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["collection_id"], ["collection.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organization.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code_hash"),
    )
    op.create_index(
        op.f("ix_oauth_authorization_code_client_id"),
        "oauth_authorization_code",
        ["client_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_oauth_authorization_code_code_hash"),
        "oauth_authorization_code",
        ["code_hash"],
        unique=False,
    )
    op.create_index(
        op.f("ix_oauth_authorization_code_collection_id"),
        "oauth_authorization_code",
        ["collection_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_oauth_authorization_code_expires_at"),
        "oauth_authorization_code",
        ["expires_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_oauth_authorization_code_organization_id"),
        "oauth_authorization_code",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_oauth_authorization_code_user_id"),
        "oauth_authorization_code",
        ["user_id"],
        unique=False,
    )
    
    # Create oauth_access_token table
    op.create_table(
        "oauth_access_token",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("modified_at", sa.DateTime(), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by_email", sa.String(), nullable=True),
        sa.Column("modified_by_email", sa.String(), nullable=True),
        sa.Column("token_hash", sa.String(), nullable=False),
        sa.Column("client_id", sa.String(), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("collection_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scope", sa.String(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["client_id"], ["oauth_client.client_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["collection_id"], ["collection.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organization.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index(
        op.f("ix_oauth_access_token_client_id"),
        "oauth_access_token",
        ["client_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_oauth_access_token_collection_id"),
        "oauth_access_token",
        ["collection_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_oauth_access_token_expires_at"),
        "oauth_access_token",
        ["expires_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_oauth_access_token_organization_id"),
        "oauth_access_token",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_oauth_access_token_revoked_at"),
        "oauth_access_token",
        ["revoked_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_oauth_access_token_token_hash"),
        "oauth_access_token",
        ["token_hash"],
        unique=False,
    )
    op.create_index(
        op.f("ix_oauth_access_token_user_id"), "oauth_access_token", ["user_id"], unique=False
    )
    
    # Create oauth_refresh_token table (for future use)
    op.create_table(
        "oauth_refresh_token",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("modified_at", sa.DateTime(), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by_email", sa.String(), nullable=True),
        sa.Column("modified_by_email", sa.String(), nullable=True),
        sa.Column("token_hash", sa.String(), nullable=False),
        sa.Column("access_token_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("client_id", sa.String(), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["access_token_id"], ["oauth_access_token.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["client_id"], ["oauth_client.client_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organization.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index(
        op.f("ix_oauth_refresh_token_access_token_id"),
        "oauth_refresh_token",
        ["access_token_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_oauth_refresh_token_client_id"),
        "oauth_refresh_token",
        ["client_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_oauth_refresh_token_expires_at"),
        "oauth_refresh_token",
        ["expires_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_oauth_refresh_token_organization_id"),
        "oauth_refresh_token",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_oauth_refresh_token_revoked_at"),
        "oauth_refresh_token",
        ["revoked_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_oauth_refresh_token_token_hash"),
        "oauth_refresh_token",
        ["token_hash"],
        unique=False,
    )
    op.create_index(
        op.f("ix_oauth_refresh_token_user_id"), "oauth_refresh_token", ["user_id"], unique=False
    )


def downgrade() -> None:
    """Drop OAuth 2.1 tables."""
    op.drop_index(op.f("ix_oauth_refresh_token_user_id"), table_name="oauth_refresh_token")
    op.drop_index(op.f("ix_oauth_refresh_token_token_hash"), table_name="oauth_refresh_token")
    op.drop_index(op.f("ix_oauth_refresh_token_revoked_at"), table_name="oauth_refresh_token")
    op.drop_index(
        op.f("ix_oauth_refresh_token_organization_id"), table_name="oauth_refresh_token"
    )
    op.drop_index(op.f("ix_oauth_refresh_token_expires_at"), table_name="oauth_refresh_token")
    op.drop_index(op.f("ix_oauth_refresh_token_client_id"), table_name="oauth_refresh_token")
    op.drop_index(
        op.f("ix_oauth_refresh_token_access_token_id"), table_name="oauth_refresh_token"
    )
    op.drop_table("oauth_refresh_token")
    
    op.drop_index(op.f("ix_oauth_access_token_user_id"), table_name="oauth_access_token")
    op.drop_index(op.f("ix_oauth_access_token_token_hash"), table_name="oauth_access_token")
    op.drop_index(op.f("ix_oauth_access_token_revoked_at"), table_name="oauth_access_token")
    op.drop_index(op.f("ix_oauth_access_token_organization_id"), table_name="oauth_access_token")
    op.drop_index(op.f("ix_oauth_access_token_expires_at"), table_name="oauth_access_token")
    op.drop_index(op.f("ix_oauth_access_token_collection_id"), table_name="oauth_access_token")
    op.drop_index(op.f("ix_oauth_access_token_client_id"), table_name="oauth_access_token")
    op.drop_table("oauth_access_token")
    
    op.drop_index(op.f("ix_oauth_authorization_code_user_id"), table_name="oauth_authorization_code")
    op.drop_index(
        op.f("ix_oauth_authorization_code_organization_id"), table_name="oauth_authorization_code"
    )
    op.drop_index(
        op.f("ix_oauth_authorization_code_expires_at"), table_name="oauth_authorization_code"
    )
    op.drop_index(
        op.f("ix_oauth_authorization_code_collection_id"), table_name="oauth_authorization_code"
    )
    op.drop_index(
        op.f("ix_oauth_authorization_code_code_hash"), table_name="oauth_authorization_code"
    )
    op.drop_index(
        op.f("ix_oauth_authorization_code_client_id"), table_name="oauth_authorization_code"
    )
    op.drop_table("oauth_authorization_code")
    
    op.drop_index(op.f("ix_oauth_client_client_id"), table_name="oauth_client")
    op.drop_table("oauth_client")
