"""group numbers: the name students know a group by ("302"), next to its name in the university's systems

Revision ID: e7a2c4d9f3b1
Revises: d6f1b8c3e4a2
Create Date: 2026-10-12 12:00:00
"""
import sqlalchemy as sa
from alembic import op

revision = 'e7a2c4d9f3b1'
down_revision = 'd6f1b8c3e4a2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("groups", sa.Column("number", sa.String(16)))


def downgrade() -> None:
    op.drop_column("groups", "number")
