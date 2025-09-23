"""Add yearly prepay fields to organization_billing

Revision ID: add_yearly_prepay_001
Revises: add_entity_count
Create Date: 2025-09-21 12:35:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_yearly_prepay_001'
down_revision = 'add_entity_count'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add yearly prepay tracking columns to organization_billing table
    op.add_column('organization_billing',
        sa.Column('has_yearly_prepay', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('organization_billing',
        sa.Column('yearly_prepay_started_at', sa.DateTime(), nullable=True))
    op.add_column('organization_billing',
        sa.Column('yearly_prepay_expires_at', sa.DateTime(), nullable=True))
    op.add_column('organization_billing',
        sa.Column('yearly_prepay_amount_cents', sa.Integer(), nullable=True))
    op.add_column('organization_billing',
        sa.Column('yearly_prepay_coupon_id', sa.String(), nullable=True))
    op.add_column('organization_billing',
        sa.Column('yearly_prepay_payment_intent_id', sa.String(), nullable=True))


def downgrade() -> None:
    # Remove yearly prepay tracking columns from organization_billing table
    op.drop_column('organization_billing', 'yearly_prepay_payment_intent_id')
    op.drop_column('organization_billing', 'yearly_prepay_coupon_id')
    op.drop_column('organization_billing', 'yearly_prepay_amount_cents')
    op.drop_column('organization_billing', 'yearly_prepay_expires_at')
    op.drop_column('organization_billing', 'yearly_prepay_started_at')
    op.drop_column('organization_billing', 'has_yearly_prepay')
