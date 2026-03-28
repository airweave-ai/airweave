"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""
from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

# revision identifiers, used by Alembic.
revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}

# --- DDL safety checklist (remove before committing) ---
#
# [ ] lock_timeout: env.py sets a 10s default. Override per-statement
#     with op.execute("SET lock_timeout = '30s'") if needed.
#
# [ ] CREATE INDEX CONCURRENTLY: requires autocommit (non-transactional)
#     mode. Use:
#         with op.get_context().autocommit_block():
#             op.create_index(..., postgresql_concurrently=True)
#
# [ ] ADD COLUMN with DEFAULT: PG 11+ handles non-volatile defaults
#     (literals, immutable functions) as metadata-only. Volatile
#     defaults (e.g. clock_timestamp()) still rewrite the table.
#
# [ ] Breaking schema changes: use expand-contract. Deploy the new
#     schema (expand) first, migrate data/code, then drop the old
#     schema (contract) in a later migration.
# ---


def upgrade():
    ${upgrades if upgrades else "pass"}


def downgrade():
    ${downgrades if downgrades else "pass"}
