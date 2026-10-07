"""bot conversations log, photos/videos in messages to students, display preferences

Revision ID: b4d8f2a6c1e9
Revises: a7c3e9f1b2d4
Create Date: 2026-10-03 10:00:00
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = 'b4d8f2a6c1e9'
down_revision = 'a7c3e9f1b2d4'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("admins", sa.Column("prefs", postgresql.JSONB(), server_default="{}", nullable=False))
    op.add_column("broadcasts", sa.Column("media_kind", sa.String(8)))
    op.add_column("broadcasts", sa.Column("media_name", sa.String(255)))
    op.add_column("broadcasts", sa.Column("filters", postgresql.JSONB()))
    op.create_table(
        "bot_chats",
        sa.Column("chat_id", sa.BigInteger(), primary_key=True, autoincrement=False),
        sa.Column("name", sa.String(255)),
        sa.Column("username", sa.String(64)),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("students.id", ondelete="SET NULL"), nullable=True),
        sa.Column("first_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_text", sa.String(255)),
        sa.Column("last_dir", sa.String(4)),
        sa.Column("blocked", sa.Boolean(), server_default="false", nullable=False),
    )
    op.create_index("ix_bot_chats_last_at", "bot_chats", ["last_at"])
    op.create_table(
        "bot_messages",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("message_id", sa.BigInteger()),
        sa.Column("dir", sa.String(4), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("text", sa.Text()),
        sa.Column("file_id", sa.String(255)),
        sa.Column("buttons", postgresql.JSONB()),
        sa.Column("origin", sa.String(32)),
        sa.Column("admin_id", sa.Integer(), sa.ForeignKey("admins.id", ondelete="SET NULL"), nullable=True),
        sa.Column("at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("edited_at", sa.DateTime(timezone=True)),
        sa.Column("deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("reaction", sa.String(16)),
    )
    op.create_index("ix_bot_messages_chat", "bot_messages", ["chat_id", "id"])
    op.create_index("ix_bot_messages_message", "bot_messages", ["chat_id", "message_id"])
    op.create_index("ix_bot_messages_at", "bot_messages", ["at"])


def downgrade() -> None:
    op.drop_table("bot_messages")
    op.drop_table("bot_chats")
    op.drop_column("broadcasts", "filters")
    op.drop_column("broadcasts", "media_name")
    op.drop_column("broadcasts", "media_kind")
    op.drop_column("admins", "prefs")
