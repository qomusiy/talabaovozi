"""Settings that admins change in the dashboard; the bot and the web app read them from the database.

Every setting has a default here, so an empty table works. Each process caches the values for a few
seconds, so a change made in the dashboard reaches the running bot within ~10 s - no restart needed.
"""
import time
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app import audit
from app.config import get_settings
from app.models import AppSetting

DEFAULTS: dict[str, Any] = {
    # Bot
    "login_open": True,           # new students can log in (logged-in students are not affected)
    "support_contact": "",        # "" = the value from .env
    "tech_contact": "",
    "admin_telegram_ids": [],     # Telegram accounts told the new dashboard address when it changes
    "channel_url": "https://t.me/iqtisodiyot_uz1",  # the faculty's channel: a button on the bot's menu ("" = none)
    "bot_reactions": True,        # the bot puts an emoji reaction on students' messages (👀 🔥 ❤ ...)
    # Survey
    "survey_comments": True,      # show the comment box
    "survey_comment_required": False,  # a rating can't be sent without a comment (at least 10 characters)
    "survey_edit": True,          # a submitted rating can be changed while the round is open
    "survey_notice": "",          # short note shown at the top of the survey
    # Teaching data
    "timetable_auto_sync": True,  # check EduPage for timetable changes
    "timetable_sync_hours": 6,
    "assignments_source": "timetable",  # who-teaches-whom: "timetable" (automatic) or "excel" (uploaded)
    "excluded_subjects": ["Kelajak soati"],  # not rated in the survey
    "reminders": False,           # automatic reminders to students who haven't finished (3 days and 1 day before the end)
    "reminders_sent": {},         # campaign id -> reminders already sent ("3", "1")
    # Dashboard
    "admin_online": False,        # the dashboard can also be opened through the public address (not only here)
    # Written by the system, shown on the dashboard
    "timetable_checked_at": "", "timetable_error": "", "bot_seen_at": "", "bot_username": "",
    "daily_report_sent": "",      # the day (YYYY-MM-DD) the admins' daily report last went out
}
SYSTEM_KEYS = {"timetable_checked_at", "timetable_error", "bot_seen_at", "bot_username", "reminders_sent",
               "daily_report_sent"}
TTL = 10.0
_cache: dict[str, Any] = {}
_loaded_at = -TTL


def reset_cache() -> None:
    global _loaded_at
    _cache.clear()
    _loaded_at = -TTL


async def load(session: AsyncSession, fresh: bool = False) -> dict[str, Any]:
    global _loaded_at
    if fresh or time.monotonic() - _loaded_at > TTL:
        rows = (await session.execute(select(AppSetting.key, AppSetting.value))).all()
        _cache.clear()
        _cache.update({k: v for k, v in rows if k in DEFAULTS})
        _loaded_at = time.monotonic()
    return DEFAULTS | _cache


async def get(session: AsyncSession, key: str) -> Any:
    return (await load(session))[key]


async def save(session: AsyncSession, **values: Any) -> None:
    before = await load(session)
    for key, value in values.items():
        if key not in DEFAULTS:
            raise KeyError(key)
        if key not in SYSTEM_KEYS:
            audit.note("setting", key, key, before.get(key), value)
        stmt = pg_insert(AppSetting).values(key=key, value=value)
        await session.execute(stmt.on_conflict_do_update(index_elements=["key"],
                                                         set_={"value": value, "updated_at": func.now()}))
    _cache.update(values)  # this process sees the change at once


def contacts(values: dict[str, Any]) -> tuple[str, str]:
    """(support, tech) Telegram contacts: the dashboard value, else .env."""
    env = get_settings()
    return values["support_contact"] or env.support_contact, values["tech_contact"] or env.tech_contact
