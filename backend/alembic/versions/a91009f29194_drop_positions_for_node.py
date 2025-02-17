"""drop positions for node

Revision ID: a91009f29194
Revises: 52e0072a0691
Create Date: 2025-02-17 17:22:36.496691

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a91009f29194'
down_revision = '52e0072a0691'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('dag_node', 'position_y')
    op.drop_column('dag_node', 'position_x')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('dag_node', sa.Column('position_x', sa.VARCHAR(), autoincrement=False, nullable=True))
    op.add_column('dag_node', sa.Column('position_y', sa.VARCHAR(), autoincrement=False, nullable=True))
    # ### end Alembic commands ###
