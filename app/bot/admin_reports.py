"""The admins' daily report: while a survey is open, at 20:00 (Tashkent) the bot sends a short summary to every
linked dashboard account that switched it on in the bot's admin menu (📬 Kunlik hisobot)."""
import asyncio
import logging
from datetime import datetime, time
from zoneinfo import ZoneInfo

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from sqlalchemy import select

from app import settings_store
from app.bot import chatlog
from app.db import session_scope
from app.models import Admin

log = logging.getLogger("reports")
TASHKENT = ZoneInfo("Asia/Tashkent")
REPORT_AT = time(20, 0)
CHECK_EVERY = 600  # seconds


async def send_daily(bot: Bot, now: datetime | None = None) -> int:
    from app.bot.handlers.admin import daily_report_text
    now = now or datetime.now(TASHKENT)
    if now.time() < REPORT_AT:
        return 0
    async with session_scope() as session:
        if (await settings_store.load(session, fresh=True))["daily_report_sent"] == now.date().isoformat():
            return 0
        admins = (await session.execute(select(Admin).where(Admin.is_active, Admin.telegram_id.is_not(None)))).scalars()
        targets = [a.telegram_id for a in admins if (a.prefs or {}).get("tg_daily")]
        text = await daily_report_text(session, "uz") if targets else None
        await settings_store.save(session, daily_report_sent=now.date().isoformat())  # once a day, whatever happens
    sent = 0
    for chat_id in targets if text else []:
        try:
            await bot.send_message(chat_id, text)
            sent += 1
        except TelegramAPIError as e:
            log.warning("Daily report to %s failed: %s", chat_id, e)
        await asyncio.sleep(0.1)
    return sent


async def daily_loop(bot: Bot) -> None:
    chatlog.origin.set("report")
    while True:
        try:
            await send_daily(bot)
        except Exception:
            log.exception("Daily report failed")
        await asyncio.sleep(CHECK_EVERY)
