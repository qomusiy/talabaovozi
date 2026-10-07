"""departments: which faculty a kafedra belongs to

Revision ID: f2b8d4e6a1c3
Revises: e4a1c7d2b9f3
Create Date: 2026-10-01 10:00:00

Some of the faculty's teachers belong to other faculties' kafedras (Oliy matematika, Gumanitar fanlar, ...);
the dashboard groups kafedras by faculty.
"""
import sqlalchemy as sa
from alembic import op

revision = 'f2b8d4e6a1c3'
down_revision = 'e4a1c7d2b9f3'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("departments", sa.Column("faculty", sa.String(128), nullable=True))


def downgrade() -> None:
    op.drop_column("departments", "faculty")
