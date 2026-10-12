"""The bot's users: their Telegram account, the group they picked, and what a programmer did about abuse.

There is no student list. Whoever writes to the bot gets a `BotUser` row (kept fresh with what Telegram tells about
them). They pick a group - course › specialty › group - only so the survey shows their own teachers. Ratings are
anonymous to the faculty; programmer accounts see the account (Foydalanuvchilar page) and can block it, suspend it
for a while or warn it. The flood guard suspends anyone who floods the bot by itself.
"""
import re
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone

from aiogram.types import User
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.bot.i18n import DEFAULT_LANG, LANGUAGE_NAMES, t
from app.faculty import group_code, specialty_name
from app.models import BotUser, Group, Semester, TeachingAssignment

FLOOD_COUNT, FLOOD_SECONDS = 20, 10   # more than 20 messages / taps in 10 seconds ...
FLOOD_PAUSE = timedelta(minutes=10)    # ... and the bot ignores the person for 10 minutes
_recent: dict[int, deque] = defaultdict(deque)


def bot_language(code: str | None) -> str:
    """The bot's language for a Telegram app language ('ru', 'en-US', ...): ours if we have it, else Uzbek."""
    code = (code or "").split("-")[0].lower()
    return code if code in LANGUAGE_NAMES else DEFAULT_LANG


async def get(session: AsyncSession, user_id: int) -> BotUser | None:
    return await session.scalar(select(BotUser).options(selectinload(BotUser.group)).where(BotUser.id == user_id))


async def seen(session: AsyncSession, tg: User, count: bool = True, extra: dict | None = None) -> BotUser:
    """The account of this Telegram user - created the first time - with Telegram's latest name, username and
    other details. count=False: not a message to the bot (the Mini App opened). `extra`: more of what Telegram told
    (the Mini App's user: photo_url, allows_write_to_pm, ...), kept in `profile`."""
    now = datetime.now(timezone.utc)
    await session.execute(pg_insert(BotUser).values(id=tg.id, language=bot_language(tg.language_code))
                          .on_conflict_do_nothing())
    user = await get(session, tg.id)
    fresh = {"first_name": (tg.first_name or "")[:128] or None, "last_name": (tg.last_name or "")[:128] or None,
             "username": (tg.username or "")[:64] or None, "tg_language": (tg.language_code or "")[:16] or None,
             "is_premium": bool(tg.is_premium)}
    for key, value in fresh.items():
        if getattr(user, key) != value:
            setattr(user, key, value)
    told = {**(user.profile or {}), "user": tg.model_dump(exclude_none=True, mode="json"), **(extra or {})}
    if told != user.profile:
        user.profile = told
    if count:
        user.updates = (user.updates or 0) + 1
    if count or now - user.last_seen_at > timedelta(minutes=1):
        user.last_seen_at = now
    return user


# ---------------------------------------------------------------- moderation

def restriction(user: BotUser | None, now: datetime | None = None) -> str | None:
    """'blocked', 'suspended' or None."""
    if user is None:
        return None
    if user.blocked:
        return "blocked"
    if user.suspended_until and user.suspended_until > (now or datetime.now(timezone.utc)):
        return "suspended"
    return None


def flooding(user_id: int, now: float | None = None) -> bool:
    """Count one message / tap; True when this person sends more than the flood guard allows."""
    now = time.monotonic() if now is None else now
    recent = _recent[user_id]
    recent.append(now)
    while recent and now - recent[0] > FLOOD_SECONDS:
        recent.popleft()
    if len(_recent) > 5000:  # forget people who went quiet
        for uid in [u for u, q in _recent.items() if not q or now - q[-1] > FLOOD_SECONDS]:
            _recent.pop(uid, None)
    return len(recent) > FLOOD_COUNT


def stop_flood(user: BotUser, now: datetime | None = None) -> None:
    """The flood guard's pause; the programmer sees it on the user's page."""
    now = now or datetime.now(timezone.utc)
    user.suspended_until = now + FLOOD_PAUSE
    user.floods = (user.floods or 0) + 1
    _recent.pop(user.id, None)


# ---------------------------------------------------------------- picking a group: course › specialty › group

async def selectable_groups(session: AsyncSession) -> list[Group]:
    """Groups a student can pick: those with teachers this semester (so the survey has someone to rate); with no
    teaching data yet, every group that has a course."""
    taught = select(TeachingAssignment.group_id).join(Semester).where(Semester.is_current)
    groups = list((await session.execute(select(Group).where(Group.id.in_(taught), Group.course.is_not(None))
                                         .order_by(Group.name))).scalars())
    if not groups:
        groups = list((await session.execute(select(Group).where(Group.course.is_not(None))
                                             .order_by(Group.name))).scalars())
    return groups


def group_name(group: Group | None, lang: str) -> str:
    """How students see a group (bot, survey): "302-guruh" once an admin has typed in its number, else its name."""
    if group is None:
        return t(lang, "no_group")
    return t(lang, "group_n", n=group.number) if group.number else group.name


def courses(groups: list[Group]) -> list[int]:
    return sorted({g.course for g in groups if g.course})


def specialties(groups: list[Group], course: int, lang: str) -> list[tuple[str, str]]:
    """(code, name) of the specialties that have groups in this course, by name."""
    codes = {group_code(g.name) or (g.code or "") for g in groups if g.course == course}
    return sorted(((c, specialty_name(c, lang)) for c in codes if c), key=lambda x: x[1].lower())


def groups_of(groups: list[Group], course: int, code: str) -> list[Group]:
    """The groups to pick from; by number (302, 306, ...) where admins have typed one in, then by name."""
    found = [g for g in groups if g.course == course and (group_code(g.name) or g.code or "") == code]
    return sorted(found, key=lambda g: (g.number is None, _natural(g.number or g.name)))


def _natural(text: str) -> list:
    """"302" before "1002", "25-9" before "25-10"."""
    return [(0, int(part), "") if part.isdigit() else (1, 0, part.lower()) for part in re.split(r"(\d+)", text) if part]
