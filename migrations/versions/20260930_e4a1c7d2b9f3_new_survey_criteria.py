"""new survey criteria: teaching, fairness, professionalism

Revision ID: e4a1c7d2b9f3
Revises: b7e3d91a2c55
Create Date: 2026-09-30 10:00:00

The three 1-10 ratings are renamed in place. Only demo feedback existed when this ran, so the old values
simply carry over under the new names.
"""
from alembic import op

revision = 'e4a1c7d2b9f3'
down_revision = 'b7e3d91a2c55'
branch_labels = None
depends_on = None

RENAMES = [("teaching_quality", "teaching"), ("knowledge_relevance", "fairness"), ("student_support", "professionalism")]


def upgrade() -> None:
    for old, new in RENAMES:
        op.alter_column("feedback", old, new_column_name=new)
        op.execute(f"ALTER TABLE feedback RENAME CONSTRAINT {old}_range TO {new}_range")


def downgrade() -> None:
    for old, new in RENAMES:
        op.execute(f"ALTER TABLE feedback RENAME CONSTRAINT {new}_range TO {old}_range")
        op.alter_column("feedback", new, new_column_name=old)
