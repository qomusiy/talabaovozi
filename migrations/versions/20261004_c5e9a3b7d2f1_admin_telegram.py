"""dashboard accounts linked to Telegram (the bot's admin menu)

Revision ID: c5e9a3b7d2f1
Revises: b4d8f2a6c1e9
Create Date: 2026-10-04 10:00:00
"""
import sqlalchemy as sa
from alembic import op

revision = 'c5e9a3b7d2f1'
down_revision = 'b4d8f2a6c1e9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("admins", sa.Column("telegram_id", sa.BigInteger()))
    op.add_column("admins", sa.Column("telegram_username", sa.String(64)))
    op.add_column("admins", sa.Column("telegram_name", sa.String(128)))
    op.add_column("admins", sa.Column("tg_link_token", sa.String(32)))
    op.add_column("admins", sa.Column("tg_link_until", sa.DateTime(timezone=True)))
    op.create_unique_constraint("admins_telegram_id_key", "admins", ["telegram_id"])


def downgrade() -> None:
    op.drop_constraint("admins_telegram_id_key", "admins", type_="unique")
    for col in ("tg_link_until", "tg_link_token", "telegram_name", "telegram_username", "telegram_id"):
        op.drop_column("admins", col)
