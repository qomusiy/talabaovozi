"""open feedback with three criteria

Revision ID: c3278b740d03
Revises: c3be06237d68
Create Date: 2026-09-28 09:39:56.605359
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'c3278b740d03'
down_revision = 'c3be06237d68'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Feedback was empty when this ran, so the table is simply recreated.
    op.drop_table("submissions")
    op.drop_table("feedback")
    op.create_table(
        "feedback",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("campaign_id", sa.Integer(), sa.ForeignKey("survey_campaigns.id", ondelete="CASCADE"), nullable=False),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("teacher_id", sa.Integer(), sa.ForeignKey("teachers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("group_id", sa.Integer(), sa.ForeignKey("groups.id", ondelete="SET NULL"), nullable=True),
        sa.Column("teaching_quality", sa.SmallInteger(), nullable=False),
        sa.Column("knowledge_relevance", sa.SmallInteger(), nullable=False),
        sa.Column("student_support", sa.SmallInteger(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("campaign_id", "student_id", "teacher_id"),
        sa.CheckConstraint("teaching_quality BETWEEN 1 AND 10", name="teaching_quality_range"),
        sa.CheckConstraint("knowledge_relevance BETWEEN 1 AND 10", name="knowledge_relevance_range"),
        sa.CheckConstraint("student_support BETWEEN 1 AND 10", name="student_support_range"),
    )
    for col in ("campaign_id", "student_id", "teacher_id", "group_id"):
        op.create_index(f"ix_feedback_{col}", "feedback", [col])


def downgrade() -> None:
    raise NotImplementedError("One-way migration")
