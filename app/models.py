"""Database schema.

Key design decisions (see README for the reasoning):
- Who teaches whom lives in `teaching_assignments` (teacher + group + subject + semester),
  not in the Teacher table: one teacher teaches many groups and subjects.
- The survey is anonymous: there is no list of students. Whoever uses the bot is a `bot_users` row (their Telegram
  account) and picks a group, which decides whose teachers they see. A rating is linked to that account - only
  programmer accounts can see it, to stop abuse - and a unique (campaign, user, teacher) constraint stops duplicates.
- How many students a group has is a number on the group (`student_count`), for "X of Y took part".
"""
from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

LESSON_TYPES = ("lecture", "practice", "lab", "seminar", "other")
# Survey criteria, each rated 1-10: teaching quality, fair assessment, professionalism & respect for students.
RATING_CRITERIA = ("teaching", "fairness", "professionalism")


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Department(Base):
    """Kafedra."""

    __tablename__ = "departments"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True)
    faculty: Mapped[str | None] = mapped_column(String(128))  # "Iqtisodiyot"; other faculties' kafedras teach here too

    teachers: Mapped[list["Teacher"]] = relationship(back_populates="department")


class Group(TimestampMixin, Base):
    __tablename__ = "groups"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)  # e.g. "25-16 IQT (ru)", as in the timetable
    # Matching key without language/notes: "25-16 IQT". HEMIS and EduPage spell the same group differently
    # ("26-01-IQT uz" / "26-01 IQT"), the key is what they have in common. See app.faculty.group_key.
    key: Mapped[str | None] = mapped_column(String(32), unique=True)
    code: Mapped[str | None] = mapped_column(String(16), index=True)  # specialty code: IQT, BXA, FTO'IT, ...
    course: Mapped[int | None] = mapped_column(SmallInteger)  # year of study, 1-4
    specialty: Mapped[str | None] = mapped_column(String(255))
    language: Mapped[str | None] = mapped_column(String(8))  # language of instruction
    edupage_id: Mapped[str | None] = mapped_column(String(32), unique=True)
    # How many students study in the group (HEMIS export, or typed in on the Edit data page): "X of Y took part".
    student_count: Mapped[int | None] = mapped_column(Integer)
    # The name students know the group by ("302"); the bot shows it instead of `name` once an admin has typed it in.
    number: Mapped[str | None] = mapped_column(String(16))


class BotUser(Base):
    """Someone who uses the bot: their Telegram account. Anonymous to the faculty - only programmer accounts see who
    rated (Foydalanuvchilar page), to find and stop abuse. Demo data uses negative ids (no real account)."""

    __tablename__ = "bot_users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)  # the Telegram user id
    # As Telegram shows the person (refreshed on every message).
    first_name: Mapped[str | None] = mapped_column(String(128))
    last_name: Mapped[str | None] = mapped_column(String(128))
    username: Mapped[str | None] = mapped_column(String(64), index=True)
    tg_language: Mapped[str | None] = mapped_column(String(16))   # the language of their Telegram app
    is_premium: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    photo_file_id: Mapped[str | None] = mapped_column(String(255))  # newest profile picture (Telegram file id)
    # Everything else Telegram told: the user object, the Mini App's user (photo_url), getChat (bio, birthdate, ...).
    profile: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")

    language: Mapped[str] = mapped_column(String(2), default="uz", server_default="uz")  # the bot's language
    group_id: Mapped[int | None] = mapped_column(ForeignKey("groups.id", ondelete="SET NULL"), index=True)
    # Finished the introduction: picked a group (accounts from before may have gone on without one).
    onboarded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    updates: Mapped[int] = mapped_column(Integer, default=0, server_default="0")  # messages and button taps
    # The bot's latest home card; its survey button is moved along if the survey URL changes.
    survey_message_id: Mapped[int | None] = mapped_column(BigInteger)

    # Set by a programmer (or the flood guard): the bot and the survey ignore a blocked user, or one suspended until.
    blocked: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    suspended_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    floods: Mapped[int] = mapped_column(Integer, default=0, server_default="0")  # times the flood guard stopped them
    warnings: Mapped[int] = mapped_column(Integer, default=0, server_default="0")  # warnings sent from the dashboard
    note: Mapped[str | None] = mapped_column(Text)  # the programmer's note (why blocked, ...)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    group: Mapped[Group | None] = relationship()

    @property
    def name(self) -> str:
        return " ".join(x for x in (self.first_name, self.last_name) if x) or (
            f"Demo #{-self.id}" if self.id < 0 else str(self.id))


class Teacher(TimestampMixin, Base):
    __tablename__ = "teachers"

    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(String(255))
    short_name: Mapped[str | None] = mapped_column(String(128), index=True)  # as in timetable: "Qodirov RS"
    department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id", ondelete="SET NULL"))
    position: Mapped[str | None] = mapped_column(String(128))  # dotsent, professor, ...
    room_number: Mapped[str | None] = mapped_column(String(32))
    external_id: Mapped[str | None] = mapped_column(String(64), unique=True)  # id from the teachers Excel
    edupage_id: Mapped[str | None] = mapped_column(String(32), unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")

    department: Mapped[Department | None] = relationship(back_populates="teachers")


class Subject(Base):
    __tablename__ = "subjects"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True)


class Semester(Base):
    __tablename__ = "semesters"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)  # "2026-2027 Fall"
    starts_on: Mapped[date]
    ends_on: Mapped[date]
    is_current: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")


class TeachingAssignment(Base):
    """Teacher X teaches subject Y to group Z in semester S. This is what decides whom a student may rate."""

    __tablename__ = "teaching_assignments"
    __table_args__ = (
        UniqueConstraint("semester_id", "teacher_id", "group_id", "subject_id", "lesson_type"),
        CheckConstraint(f"lesson_type IN {LESSON_TYPES}", name="lesson_type_valid"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    semester_id: Mapped[int] = mapped_column(ForeignKey("semesters.id", ondelete="CASCADE"), index=True)
    teacher_id: Mapped[int] = mapped_column(ForeignKey("teachers.id", ondelete="CASCADE"), index=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"), index=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id", ondelete="CASCADE"))
    lesson_type: Mapped[str] = mapped_column(String(16), default="other", server_default="other")

    teacher: Mapped[Teacher] = relationship()
    group: Mapped[Group] = relationship()
    subject: Mapped[Subject] = relationship()
    semester: Mapped[Semester] = relationship()


class SurveyCampaign(TimestampMixin, Base):
    """One survey round, e.g. 'Mid-semester 2026 Fall'. Several rounds per semester give trends over time."""

    __tablename__ = "survey_campaigns"
    __table_args__ = (CheckConstraint("closes_at > opens_at", name="campaign_dates_valid"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    semester_id: Mapped[int] = mapped_column(ForeignKey("semesters.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(255))
    opens_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    closes_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # Demo rounds hold generated feedback; "Delete demo data" in the dashboard removes them.
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    semester: Mapped[Semester] = relationship()


class Feedback(TimestampMixin, Base):
    """A rating of one teacher in one survey campaign by one bot user. One row per (campaign, user, teacher)."""

    __tablename__ = "feedback"
    __table_args__ = (
        UniqueConstraint("campaign_id", "user_id", "teacher_id"),
        *(CheckConstraint(f"{c} BETWEEN 1 AND 10", name=f"{c}_range") for c in RATING_CRITERIA),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("survey_campaigns.id", ondelete="CASCADE"), index=True)
    # Deleting a user (an attacker) deletes their ratings too.
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("bot_users.id", ondelete="CASCADE"), index=True)
    teacher_id: Mapped[int] = mapped_column(ForeignKey("teachers.id", ondelete="CASCADE"), index=True)
    # The user's group at the time of submission (None: rated without a group), so stats stay correct if they change
    # group later.
    group_id: Mapped[int | None] = mapped_column(ForeignKey("groups.id", ondelete="SET NULL"), index=True)

    teaching: Mapped[int] = mapped_column(SmallInteger)  # explains the subject clearly, effectively, practically
    fairness: Mapped[int] = mapped_column(SmallInteger)  # objective, transparent grading
    professionalism: Mapped[int] = mapped_column(SmallInteger)  # responsible, prepared, respectful to students
    comment: Mapped[str | None] = mapped_column(Text)

    campaign: Mapped[SurveyCampaign] = relationship()
    user: Mapped[BotUser] = relationship()
    teacher: Mapped[Teacher] = relationship()
    group: Mapped[Group | None] = relationship()


ADMIN_ROLES = ("programmer", "superadmin", "viewer")


class Admin(TimestampMixin, Base):
    """Dashboard accounts. viewer: analytics only; superadmin: also runs the system; programmer: also sees the
    activity log, the data structure and can change ratings - and is not shown to the others."""

    __tablename__ = "admins"
    __table_args__ = (CheckConstraint(f"role IN {ADMIN_ROLES}", name="admin_role_valid"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(16), default="viewer", server_default="viewer")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    # How the dashboard looks to this person (text size, theme, contrast, ...): app.web.admin.display;
    # also the bot's admin menu switches (tg_server: server status messages, tg_daily: the daily report).
    prefs: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    # Telegram: the bot knows this account by its Telegram ID (app.services.admin_link). Linked with a one-time
    # link from "My account", or - the first time - by the @username entered here; the ID is kept after that,
    # so a later username change doesn't matter.
    telegram_id: Mapped[int | None] = mapped_column(BigInteger, unique=True)
    telegram_username: Mapped[str | None] = mapped_column(String(64))
    telegram_name: Mapped[str | None] = mapped_column(String(128))
    tg_link_token: Mapped[str | None] = mapped_column(String(32))
    tg_link_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    @property
    def is_super(self) -> bool:
        return self.role in ("superadmin", "programmer")

    @property
    def is_programmer(self) -> bool:
        return self.role == "programmer"

    @property
    def sees_identity(self) -> bool:
        """May this person's pages show which Telegram account gave a rating? Programmer accounts only (to find
        abuse) - unless they hid it from their own panel (Ko‘rinish › "Hide who rated"), e.g. to show the screen."""
        return self.is_programmer and not (self.prefs or {}).get("hide_names")


class AuditLog(Base):
    """What happened in the dashboard: logins, pages opened, changes made (with old -> new values), errors.
    Written by app.audit for every dashboard request; only programmer accounts can read it."""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    admin_id: Mapped[int | None] = mapped_column(ForeignKey("admins.id", ondelete="SET NULL"), index=True)
    username: Mapped[str | None] = mapped_column(String(64))  # kept if the account is deleted later
    role: Mapped[str | None] = mapped_column(String(16))
    sid: Mapped[str | None] = mapped_column(String(32), index=True)  # one login = one session
    kind: Mapped[str] = mapped_column(String(16), index=True)  # login, login_failed, logout, view, action, export, denied, error
    method: Mapped[str] = mapped_column(String(8))
    path: Mapped[str] = mapped_column(String(255))
    query: Mapped[str | None] = mapped_column(String(500))
    title: Mapped[str | None] = mapped_column(String(255))    # the page, as its breadcrumbs read
    outcome: Mapped[str | None] = mapped_column(Text)          # the message shown after an action, or the error
    status: Mapped[int] = mapped_column(SmallInteger)
    ms: Mapped[int] = mapped_column(Integer)                   # how long the server took
    ip: Mapped[str | None] = mapped_column(String(64))
    agent: Mapped[str | None] = mapped_column(String(255))
    details: Mapped[dict | None] = mapped_column(JSONB)        # form fields (no passwords), changes: old -> new


class ImportLog(Base):
    """History of Excel uploads, shown in the admin panel."""

    __tablename__ = "import_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(32))  # students / teachers / assignments / timetable
    filename: Mapped[str] = mapped_column(String(255))
    created: Mapped[int] = mapped_column(Integer, default=0)
    updated: Mapped[int] = mapped_column(Integer, default=0)
    errors: Mapped[int] = mapped_column(Integer, default=0)
    note: Mapped[str | None] = mapped_column(Text)  # summary and the first errors, shown in the dashboard
    admin: Mapped[str | None] = mapped_column(String(64))  # who uploaded it ("system" for automatic syncs)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TimetableSnapshot(Base):
    """The faculty's weekly timetable as downloaded from EduPage (see app/timetable). The newest one is shown."""

    __tablename__ = "timetable_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(255))
    title: Mapped[str] = mapped_column(String(255))  # '"TIIAME" MTU 2026/2027 (07. 09. 2026 - 12. 06. 2027)'
    faculty: Mapped[str] = mapped_column(String(128))
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    data: Mapped[dict] = mapped_column(JSONB)  # periods, days, groups, teachers, lessons


class AppSetting(Base):
    """Settings changed from the dashboard (bot, survey, data sync). Defaults live in app.settings_store."""

    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[object] = mapped_column(JSONB)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(),
                                                 onupdate=func.now())


class Broadcast(TimestampMixin, Base):
    """A message sent to the bot's users from the dashboard."""

    __tablename__ = "broadcasts"

    id: Mapped[int] = mapped_column(primary_key=True)
    text: Mapped[str] = mapped_column(Text)
    audience: Mapped[str] = mapped_column(String(32))  # all / course / group / department / specialty / unfinished
    audience_value: Mapped[str | None] = mapped_column(String(64))  # (older messages) course number or group id
    # Who exactly: {"values": [course numbers, group ids, department ids or specialty codes], "survey": "unfinished"}
    filters: Mapped[dict | None] = mapped_column(JSONB)
    media_kind: Mapped[str | None] = mapped_column(String(8))    # photo / video / document, sent with the text
    media_name: Mapped[str | None] = mapped_column(String(255))  # the file in data/media/broadcasts
    survey_button: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    status: Mapped[str] = mapped_column(String(16), default="queued", server_default="queued")  # queued/sending/done
    total: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    sent: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    failed: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    created_by: Mapped[str | None] = mapped_column(String(64))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class BotChat(Base):
    """Someone who wrote to the bot (or got a message from it): the list on the programmer's Conversations page."""

    __tablename__ = "bot_chats"

    chat_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    name: Mapped[str | None] = mapped_column(String(255))       # as in Telegram
    username: Mapped[str | None] = mapped_column(String(64))
    first_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    last_text: Mapped[str | None] = mapped_column(String(255))
    last_dir: Mapped[str | None] = mapped_column(String(4))
    blocked: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")  # stopped the bot


class BotMessage(Base):
    """One message in a bot conversation, both ways (app.bot.chatlog). Edits change the row, as they change the
    message in Telegram; a button press is a row of its own ("tap")."""

    __tablename__ = "bot_messages"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    chat_id: Mapped[int] = mapped_column(BigInteger)
    message_id: Mapped[int | None] = mapped_column(BigInteger)
    dir: Mapped[str] = mapped_column(String(4))             # in (from the person) / out (from the bot) / tap
    kind: Mapped[str] = mapped_column(String(16))           # text, photo, video, document, sticker, voice, ...
    text: Mapped[str | None] = mapped_column(Text)          # Telegram HTML
    file_id: Mapped[str | None] = mapped_column(String(255))
    buttons: Mapped[list | None] = mapped_column(JSONB)     # rows of {"t": label, "k": cb/url/app}
    origin: Mapped[str | None] = mapped_column(String(32))  # bot, broadcast:12, reminder, panel, system
    admin_id: Mapped[int | None] = mapped_column(ForeignKey("admins.id", ondelete="SET NULL"))  # sent from the panel
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    reaction: Mapped[str | None] = mapped_column(String(16))  # the bot's emoji reaction to a message
