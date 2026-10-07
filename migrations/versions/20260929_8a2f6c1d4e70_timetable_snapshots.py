"""timetable snapshots

Revision ID: 8a2f6c1d4e70
Revises: 5d1e0a7c9b42
Create Date: 2026-09-29 11:00:00
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '8a2f6c1d4e70'
down_revision = '5d1e0a7c9b42'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "timetable_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source", sa.String(255), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("faculty", sa.String(128), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("data", postgresql.JSONB(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("timetable_snapshots")
