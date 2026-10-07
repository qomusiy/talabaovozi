"""Automatic reminders (dashboard: Telegram bot › "Avtomatik eslatmalar"): 3 days and 1 day before an open survey
ends, students who haven't rated all their teachers get a friendly, personal message with the survey button.
Each reminder goes once per survey; it is listed with the other messages to students on the Bot page."""
import asyncio
import logging
from datetime import datetime, timedelta, timezone

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramRetryAfter
from sqlalchemy import select

from app import settings_store
from app.bot import chatlog
from app.bot import keyboards as kb
from app.bot.handlers.menu import first_name
from app.bot.i18n import t
from app.db import session_scope
from app.models import Broadcast, Student
from app.runtime import webapp_url
from app.services import broadcast
from app.services.students import active_campaign

log = logging.getLogger("reminders")
CHECK_EVERY = 600  # seconds
# (mark, how long before the end, not later than) - a reminder is skipped if the survey ends too soon after it.
SCHEDULE = (("3", timedelta(days=3), timedelta(days=1, hours=12)), ("1", timedelta(days=1), timedelta(hours=3)))


async def due(now: datetime | None = None) -> tuple | None:
    """(campaign, mark) of a reminder that should go now, or None."""
    now = now or datetime.now(timezone.utc)
    async with session_scope() as session:
        values = await settings_store.load(session, fresh=True)
        if not values["reminders"]:
            return None
        campaign = await active_campaign(session)
        if campaign is None or now - campaign.opens_at < timedelta(days=1):  # not right after it opened
            return None
        left = campaign.closes_at - now
        sent = values["reminders_sent"].get(str(campaign.id), [])
        for mark, before, latest in SCHEDULE:
            if mark not in sent and latest < left <= before:
                return campaign, mark
    return None


async def send(bot: Bot, campaign, mark: str) -> int:
    async with session_scope() as session:
        people = await broadcast.recipients(session, "unfinished")
        names = dict((await session.execute(select(Student.telegram_id, Student.full_name).where(
            Student.telegram_id.in_([tid for tid, _ in people])))).all())
        values = await settings_store.load(session, fresh=True)
        sent_marks = dict(values["reminders_sent"])
        sent_marks[str(campaign.id)] = [*sent_marks.get(str(campaign.id), []), mark]
        await settings_store.save(session, reminders_sent=sent_marks)   # once, even if sending fails half-way
        record = Broadcast(text=t("uz", f"reminder_{mark}", name="…"), audience="unfinished", survey_button=True,
                           status="sending", total=len(people), created_by="system")
        session.add(record)
        await session.flush()
        record_id = record.id
    url = webapp_url()
    delivered = failed = 0
    for chat_id, lang in people:
        markup = kb.open_survey(lang, f"{url}/survey") if url else None
        for _attempt in range(3):
            try:
                await bot.send_message(chat_id, t(lang, f"reminder_{mark}", name=first_name(names.get(chat_id, ""))),
                                       reply_markup=markup)
                delivered += 1
                break
            except TelegramRetryAfter as e:
                await asyncio.sleep(e.retry_after + 1)
            except TelegramAPIError:
                failed += 1
                break
        await asyncio.sleep(1 / broadcast.PER_SECOND)
    async with session_scope() as session:
        b = await session.get(Broadcast, record_id)
        b.sent, b.failed, b.status, b.finished_at = delivered, failed, "done", datetime.now(timezone.utc)
    log.info("Reminder %s for survey %s: %d sent, %d failed", mark, campaign.id, delivered, failed)
    return delivered


async def reminder_loop(bot: Bot) -> None:
    chatlog.origin.set("reminder")
    while True:
        try:
            if found := await due():
                await send(bot, *found)
        except Exception:
            log.exception("Reminder check failed")
        await asyncio.sleep(CHECK_EVERY)
