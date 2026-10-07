"""programmer accounts, viewers without student names, activity log

Revision ID: a7c3e9f1b2d4
Revises: f2b8d4e6a1c3
Create Date: 2026-10-02 10:00:00
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = 'a7c3e9f1b2d4'
down_revision = 'f2b8d4e6a1c3'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("admin_role_valid", "admins", type_="check")
    op.create_check_constraint("admin_role_valid", "admins", "role IN ('programmer', 'superadmin', 'viewer')")
    op.add_column("admins", sa.Column("show_identity", sa.Boolean(), server_default="true", nullable=False))
    op.create_table(
        "audit_log",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("admin_id", sa.Integer(), sa.ForeignKey("admins.id", ondelete="SET NULL"), nullable=True),
        sa.Column("username", sa.String(64)),
        sa.Column("role", sa.String(16)),
        sa.Column("sid", sa.String(32)),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("method", sa.String(8), nullable=False),
        sa.Column("path", sa.String(255), nullable=False),
        sa.Column("query", sa.String(500)),
        sa.Column("title", sa.String(255)),
        sa.Column("outcome", sa.Text()),
        sa.Column("status", sa.SmallInteger(), nullable=False),
        sa.Column("ms", sa.Integer(), nullable=False),
        sa.Column("ip", sa.String(64)),
        sa.Column("agent", sa.String(255)),
        sa.Column("details", postgresql.JSONB()),
    )
    for col in ("at", "admin_id", "sid", "kind"):
        op.create_index(f"ix_audit_log_{col}", "audit_log", [col])


def downgrade() -> None:
    op.drop_table("audit_log")
    op.drop_column("admins", "show_identity")
    op.execute("DELETE FROM admins WHERE role = 'programmer'")
    op.drop_constraint("admin_role_valid", "admins", type_="check")
    op.create_check_constraint("admin_role_valid", "admins", "role IN ('superadmin', 'viewer')")
