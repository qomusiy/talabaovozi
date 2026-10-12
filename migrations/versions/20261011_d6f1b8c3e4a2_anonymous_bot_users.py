"""anonymous survey: bot users instead of the student list

Students no longer log in with HEMIS + passport: whoever uses the bot is a bot_users row (their Telegram account)
and picks a group. Ratings move from the student to that account; the students table is deleted, and each group
keeps only how many students it has (groups.student_count).

Revision ID: d6f1b8c3e4a2
Revises: c5e9a3b7d2f1
Create Date: 2026-10-11 12:00:00
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = 'd6f1b8c3e4a2'
down_revision = 'c5e9a3b7d2f1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Group sizes, counted from the student list before it goes.
    op.add_column("groups", sa.Column("student_count", sa.Integer()))
    op.execute("""
        UPDATE groups g SET student_count = s.n
        FROM (SELECT group_id, count(*) AS n FROM students WHERE is_active AND group_id IS NOT NULL GROUP BY group_id) s
        WHERE s.group_id = g.id""")

    # 2. The bot's users.
    op.create_table(
        "bot_users",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=False),
        sa.Column("first_name", sa.String(128)),
        sa.Column("last_name", sa.String(128)),
        sa.Column("username", sa.String(64)),
        sa.Column("tg_language", sa.String(16)),
        sa.Column("is_premium", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("photo_file_id", sa.String(255)),
        sa.Column("profile", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column("language", sa.String(2), server_default="uz", nullable=False),
        sa.Column("group_id", sa.Integer(), sa.ForeignKey("groups.id", ondelete="SET NULL")),
        sa.Column("onboarded_at", sa.DateTime(timezone=True)),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updates", sa.Integer(), server_default="0", nullable=False),
        sa.Column("survey_message_id", sa.BigInteger()),
        sa.Column("blocked", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("suspended_until", sa.DateTime(timezone=True)),
        sa.Column("floods", sa.Integer(), server_default="0", nullable=False),
        sa.Column("warnings", sa.Integer(), server_default="0", nullable=False),
        sa.Column("note", sa.Text()),
        sa.Column("is_demo", sa.Boolean(), server_default="false", nullable=False),
    )
    op.create_index("ix_bot_users_group_id", "bot_users", ["group_id"])
    op.create_index("ix_bot_users_username", "bot_users", ["username"])
    op.create_index("ix_bot_users_last_seen_at", "bot_users", ["last_seen_at"])

    # Everyone who wrote to the bot.
    op.execute("""
        INSERT INTO bot_users (id, first_name, username, first_seen_at, last_seen_at)
        SELECT chat_id, left(name, 128), username, first_at, last_at FROM bot_chats WHERE chat_id > 0""")
    # Each student who used the bot or has ratings becomes an account: their Telegram id (or the one they used
    # before logging out), else - demo data - a negative id. Logged-in students keep their group and language.
    op.execute("""
        CREATE TEMP TABLE student_account ON COMMIT DROP AS
        WITH raw AS (
            SELECT s.id AS sid, s.language, s.group_id, s.registered_at, s.created_at, s.survey_message_id,
                   s.telegram_id IS NOT NULL AS linked,
                   coalesce(s.telegram_id, (SELECT c.chat_id FROM bot_chats c WHERE c.student_id = s.id
                                            ORDER BY c.last_at DESC LIMIT 1)) AS tg,
                   EXISTS (SELECT 1 FROM feedback f JOIN survey_campaigns c ON c.id = f.campaign_id
                           WHERE f.student_id = s.id AND NOT c.is_demo) AS real_ratings,
                   EXISTS (SELECT 1 FROM feedback f WHERE f.student_id = s.id) AS any_ratings
            FROM students s)
        SELECT r.*, CASE WHEN r.tg IS NOT NULL
                          AND row_number() OVER (PARTITION BY r.tg ORDER BY r.linked DESC, r.sid) = 1
                         THEN r.tg ELSE -r.sid END AS uid
        FROM raw r WHERE r.tg IS NOT NULL OR r.any_ratings""")
    op.execute("""
        INSERT INTO bot_users (id, language, group_id, onboarded_at, first_seen_at, last_seen_at, survey_message_id,
                               is_demo)
        SELECT uid, language, group_id,
               CASE WHEN linked THEN coalesce(registered_at, now())
                    WHEN uid < 0 THEN coalesce(registered_at, created_at) END,
               coalesce(registered_at, created_at), coalesce(registered_at, created_at),
               CASE WHEN linked THEN survey_message_id END, uid < 0 AND NOT real_ratings
        FROM student_account
        ON CONFLICT (id) DO UPDATE SET language = excluded.language, group_id = excluded.group_id,
            onboarded_at = excluded.onboarded_at, survey_message_id = excluded.survey_message_id""")

    # 3. Ratings belong to the account.
    op.add_column("feedback", sa.Column("user_id", sa.BigInteger()))
    op.execute("UPDATE feedback f SET user_id = a.uid FROM student_account a WHERE a.sid = f.student_id")
    op.alter_column("feedback", "user_id", nullable=False)
    op.drop_constraint("feedback_campaign_id_student_id_teacher_id_key", "feedback", type_="unique")
    op.drop_column("feedback", "student_id")
    op.create_foreign_key("feedback_user_id_fkey", "feedback", "bot_users", ["user_id"], ["id"], ondelete="CASCADE")
    op.create_index("ix_feedback_user_id", "feedback", ["user_id"])
    op.create_unique_constraint("feedback_campaign_id_user_id_teacher_id_key", "feedback",
                                ["campaign_id", "user_id", "teacher_id"])

    # 4. The student list and what only it needed.
    op.drop_column("bot_chats", "student_id")
    op.drop_column("admins", "show_identity")
    op.drop_table("students")
    op.execute("DELETE FROM app_settings WHERE key IN ('login_open', 'admin_telegram_ids')")


def downgrade() -> None:
    raise NotImplementedError("The student list was deleted - restore a backup from before this update instead "
                              "(scripts/server.sh restore, or scripts\\server.bat restore).")
