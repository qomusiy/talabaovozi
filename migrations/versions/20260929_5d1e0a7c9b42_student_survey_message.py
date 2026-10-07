"""student survey message

Revision ID: 5d1e0a7c9b42
Revises: c3278b740d03
Create Date: 2026-09-29 09:45:00
"""
from alembic import op
import sqlalchemy as sa

revision = '5d1e0a7c9b42'
down_revision = 'c3278b740d03'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("students", sa.Column("survey_message_id", sa.BigInteger(), nullable=True))


def downgrade() -> None:
    op.drop_column("students", "survey_message_id")
