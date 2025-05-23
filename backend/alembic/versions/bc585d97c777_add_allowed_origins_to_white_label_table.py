"""Add allowed_origins to white_label table

Revision ID: bc585d97c777
Revises: 63360ed39480
Create Date: 2025-05-18 19:58:08.334609

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'bc585d97c777'
down_revision = '63360ed39480'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('white_label', sa.Column('allowed_origins', sa.String(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('white_label', 'allowed_origins')
    # ### end Alembic commands ###
