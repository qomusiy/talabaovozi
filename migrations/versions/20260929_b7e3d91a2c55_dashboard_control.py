"""dashboard control: settings, broadcasts, group key, temporary passports, demo rounds

Revision ID: b7e3d91a2c55
Revises: 8a2f6c1d4e70
Create Date: 2026-09-29 13:00:00
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'b7e3d91a2c55'
down_revision = '8a2f6c1d4e70'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("groups", sa.Column("key", sa.String(32), nullable=True))
    op.create_unique_constraint("groups_key_key", "groups", ["key"])
    op.add_column("groups", sa.Column("code", sa.String(16), nullable=True))
    op.create_index("ix_groups_code", "groups", ["code"])
    op.add_column("students", sa.Column("passport_temporary", sa.Boolean(), server_default="false", nullable=False))
    op.add_column("survey_campaigns", sa.Column("is_demo", sa.Boolean(), server_default="false", nullable=False))
    op.add_column("import_logs", sa.Column("note", sa.Text(), nullable=True))
    op.add_column("import_logs", sa.Column("admin", sa.String(64), nullable=True))
    op.create_table(
        "app_settings",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("value", postgresql.JSONB(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "broadcasts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("audience", sa.String(32), nullable=False),
        sa.Column("audience_value", sa.String(64), nullable=True),
        sa.Column("survey_button", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("status", sa.String(16), server_default="queued", nullable=False),
        sa.Column("total", sa.Integer(), server_default="0", nullable=False),
        sa.Column("sent", sa.Integer(), server_default="0", nullable=False),
        sa.Column("failed", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_by", sa.String(64), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("broadcasts")
    op.drop_table("app_settings")
    op.drop_column("import_logs", "admin")
    op.drop_column("import_logs", "note")
    op.drop_column("survey_campaigns", "is_demo")
    op.drop_column("students", "passport_temporary")
    op.drop_index("ix_groups_code", "groups")
    op.drop_column("groups", "code")
    op.drop_constraint("groups_key_key", "groups")
    op.drop_column("groups", "key")
