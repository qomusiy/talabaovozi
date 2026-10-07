"""Keeps every "open survey" button in Telegram pointing at the current survey URL.

During development the URL is a Cloudflare quick tunnel, which gets a new address whenever it is reopened.
Telegram keeps whatever address a button was created with, so an old button would open a dead page
("Error 1033"). This module moves the chat menu button and the buttons on already-sent survey messages
to the new address.
"""
import asyncio
import logging
import time
from datetime import datetime, timezone

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramRetryAfter
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, MenuButtonCommands, MenuButtonWebApp, WebAppInfo
from sqlalchemy import select

from app import settings_store
from app.bot import chatlog
from app.bot import keyboards as kb
from app.bot.i18n import t
from app.db import session_scope
from app.config import get_settings
from app.models import Admin, Student
from app.runtime import webapp_url
from app.services.students import active_campaign

log = logging.getLogger("bot")
_current: str | None = None
_set_at = 0.0  # when the menu button was last changed (time.monotonic)
CHECK_AFTER = 30.0  # Telegram can take ~20 s before it shows a menu button change


async def sync_menu_button(bot: Bot) -> str:
    """Update the menu button if the survey URL changed. Returns the current URL ("" if none)."""
    global _current, _set_at
    url = webapp_url()
    if url == _current:
        return url
    try:
        if url:
            await bot.set_chat_menu_button(menu_button=MenuButtonWebApp(
                text="📝 Baholash", web_app=WebAppInfo(url=f"{url}/survey")))
            log.info("Survey Mini App: %s/survey", url)
        else:
            await bot.set_chat_menu_button(menu_button=MenuButtonCommands())
            log.warning("No public survey URL - the survey can't open in Telegram. Start with scripts/dev.sh "
                        "(Cloudflare tunnel) or set WEBAPP_URL in .env.")
        _current, _set_at = url, time.monotonic()
    except TelegramAPIError as e:
        log.warning("Could not set the menu button: %s", e)
    return url


async def published_url(bot: Bot) -> str | None:
    """The survey URL Telegram currently has on the menu button ("" if it has none, None if unknown)."""
    try:
        button = await bot.get_chat_menu_button()
    except TelegramAPIError:
        return None
    web_app = getattr(button, "web_app", None)
    return web_app.url.removesuffix("/survey") if web_app else ""


async def _edit(bot: Bot, chat_id: int, message_id: int, markup) -> None:
    for _ in range(3):
        try:
            await bot.edit_message_reply_markup(chat_id=chat_id, message_id=message_id, reply_markup=markup)
            return
        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after)
        except TelegramAPIError:  # deleted message, blocked bot, "not modified", ...
            return


async def refresh_survey_buttons(bot: Bot, url: str) -> int:
    """Point the survey button on every student's latest home card at `url` (no survey button if there is no
    address or no open survey; the card's other buttons stay)."""
    async with session_scope() as session:
        rows = (await session.execute(
            select(Student.telegram_id, Student.survey_message_id, Student.language)
            .where(Student.telegram_id.is_not(None), Student.survey_message_id.is_not(None)))).all()
        survey_open = await active_campaign(session) is not None
        channel = (await settings_store.load(session))["channel_url"]
    for chat_id, message_id, lang in rows:
        await _edit(bot, chat_id, message_id, kb.home(lang, url, survey=survey_open and bool(url), channel=channel))
        await asyncio.sleep(0.05)  # stay well under Telegram's ~30 requests/second
    if rows:
        log.info("Moved %d survey button(s) to %s", len(rows), url or "(none)")
    return len(rows)


async def admin_chats(session) -> set[int]:
    """Who is told when the address changes: dashboard accounts linked to Telegram (unless they switched it off
    in the bot's admin menu), plus any extra ids typed on the Bot page."""
    ids = set(await settings_store.get(session, "admin_telegram_ids"))
    rows = (await session.execute(select(Admin.telegram_id, Admin.prefs).where(
        Admin.is_active, Admin.telegram_id.is_not(None)))).all()
    return ids | {tid for tid, prefs in rows if (prefs or {}).get("tg_notify", True)}


async def notify_admins(bot: Bot, url: str) -> None:
    """Send the new public address to the admins, with buttons to open it."""
    async with session_scope() as session:
        ids = await admin_chats(session)
        online = not get_settings().admin_local_only or await settings_store.get(session, "admin_online")
    buttons = [InlineKeyboardButton(text="📝 So‘rovnoma", web_app=WebAppInfo(url=f"{url}/survey"))]
    if online:
        buttons.insert(0, InlineKeyboardButton(text="📊 Admin sayt", url=f"{url}/admin"))
    markup = InlineKeyboardMarkup(inline_keyboard=[buttons])
    for chat_id in ids:
        try:
            await bot.send_message(chat_id, t("uz", "admin_new_address", url=url), reply_markup=markup)
        except TelegramAPIError as e:
            log.warning("Could not tell admin %s the new address: %s", chat_id, e)


async def heartbeat(username: str) -> None:
    """Lets the dashboard show whether the bot is running."""
    async with session_scope() as session:
        await settings_store.save(session, bot_seen_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                  bot_username=username)


async def follow_survey_url(bot: Bot, published: str | None, username: str = "", every: float = 5.0) -> None:
    """Runs next to polling: whenever the survey URL changes, move the menu button and old survey buttons.
    Also reports to the dashboard that the bot is alive (about once a minute)."""
    global _current
    chatlog.origin.set("system")
    buttons_url = published
    checked_at = time.monotonic()
    beat_at = -60.0
    while True:
        url = await sync_menu_button(bot)
        if url != buttons_url:
            try:
                await refresh_survey_buttons(bot, url)
                if url:
                    await notify_admins(bot, url)
                buttons_url = url
            except Exception:  # DB hiccup: try again on the next round
                log.exception("Could not refresh survey buttons")
        if time.monotonic() - beat_at >= 60:
            try:
                await heartbeat(username)
                beat_at = time.monotonic()
            except Exception:
                log.exception("Could not write the heartbeat")
        # Telegram answers "ok" to a menu button change but sometimes applies it late or drops it,
        # so check now and then what it really shows, and set it again if that is still the old address.
        if time.monotonic() - max(_set_at, checked_at) >= CHECK_AFTER:
            checked_at = time.monotonic()
            if (shown := await published_url(bot)) not in (None, url):
                log.info("Telegram still shows %s on the menu button - setting it again", shown or "no survey")
                _current = None
        await asyncio.sleep(every)
