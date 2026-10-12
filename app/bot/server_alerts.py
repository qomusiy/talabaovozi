"""Server status messages for the admins who switched them on (bot admin menu › 🔔 Server xabarlari - off by default).

When the server starts, or the public address changes, each of them gets ONE message: when the server started, the
bot, whether the site answers on its public address, whether a survey is open, where the dashboard is. The bot then
edits that same message as things change - until everything works, or 15 minutes have passed - instead of sending
a new message for every change.
"""
import asyncio
import logging
import time
from datetime import datetime
from html import escape
from zoneinfo import ZoneInfo

import httpx
from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from sqlalchemy import select

from app import settings_store
from app.bot import chatlog
from app.bot.admin_i18n import ta
from app.config import get_settings
from app.db import session_scope
from app.models import Admin, BotUser
from app.runtime import server_status, webapp_url
from app.services.survey import active_campaign

log = logging.getLogger("bot")
TASHKENT = ZoneInfo("Asia/Tashkent")
BOT_STARTED = int(time.time())
LIVE_FOR = 15 * 60   # seconds a message is kept up to date
EVERY = 10           # seconds between checks while it is


def pref(admin: Admin) -> bool:
    return bool((admin.prefs or {}).get("tg_server"))


async def targets(session) -> dict[int, str]:
    """Telegram id -> language of the linked dashboard accounts that switched the messages on."""
    rows = (await session.execute(select(Admin, BotUser.language).outerjoin(BotUser, BotUser.id == Admin.telegram_id)
                                  .where(Admin.is_active, Admin.telegram_id.is_not(None)))).all()
    return {a.telegram_id: lang if lang in ("uz", "en", "ru") else "uz" for a, lang in rows if pref(a)}


async def site_answers(url: str) -> bool:
    if not url:
        return False
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            return (await client.get(f"{url}/healthz")).status_code == 200
    except httpx.HTTPError:
        return False


async def facts(state: dict) -> dict:
    """What the message says, checked now."""
    url = webapp_url()
    async with session_scope() as session:
        campaign = await active_campaign(session)
        online = not get_settings().admin_local_only or await settings_store.get(session, "admin_online")
    web = (server_status().get("children") or {}).get("web", {}).get("running", True)
    return {"url": url, "site": "ok" if await site_answers(url) else ("starting" if not url else "down"),
            "web": web, "online": online,
            "survey": {"title": campaign.title,
                       "closes": campaign.closes_at.astimezone(TASHKENT).strftime("%d.%m %H:%M")} if campaign else None}


def render(lang: str, state: dict, f: dict, now: float) -> tuple[str, InlineKeyboardMarkup | None, bool]:
    """(text, buttons, everything works?)."""
    at = datetime.fromtimestamp(state["at"], TASHKENT).strftime("%d.%m.%Y %H:%M")
    head = ta(lang, "alert_started" if state["kind"] == "start" else "alert_address", at=at)
    site = ta(lang, f"alert_site_{f['site']}")
    lines = [head, "", ta(lang, "alert_bot"), ta(lang, "alert_web_ok" if f["web"] else "alert_web_down"),
             ta(lang, "alert_site", state=site)]
    if f["url"]:
        lines.append(f"🔗 <code>{escape(f['url'])}</code>")
    s = f["survey"]
    lines.append(ta(lang, "alert_survey_open", title=escape(s["title"]), closes=s["closes"]) if s
                 else ta(lang, "alert_survey_none"))
    lines.append(ta(lang, "alert_admin_online") if f["online"] else
                 ta(lang, "alert_admin_local", port=get_settings().web_port))
    ok = f["site"] == "ok" and f["web"]
    checked = datetime.fromtimestamp(now, TASHKENT).strftime("%H:%M")
    if ok:
        foot = ta(lang, "alert_all_ok", time=checked)
    elif now - state["at"] > LIVE_FOR:
        foot = ta(lang, "alert_gave_up", n=LIVE_FOR // 60)
    else:
        foot = ta(lang, "alert_watching", time=checked)
    text = "\n".join(lines) + "\n\n" + foot
    markup = None
    if f["url"]:
        buttons = [InlineKeyboardButton(text=ta(lang, "btn_open_survey"), web_app=WebAppInfo(url=f"{f['url']}/survey"))]
        if f["online"]:
            buttons.insert(0, InlineKeyboardButton(text=ta(lang, "btn_open_admin"), url=f"{f['url']}/admin"))
        markup = InlineKeyboardMarkup(inline_keyboard=[buttons])
    return text, markup, ok


async def _send(bot: Bot, chat_id: int, text: str, markup) -> int | None:
    try:
        return (await bot.send_message(chat_id, text, reply_markup=markup, disable_web_page_preview=True)).message_id
    except TelegramAPIError as e:
        log.warning("Server message to %s not sent: %s", chat_id, e)
        return None


async def _edit(bot: Bot, chat_id: int, message_id: int, text: str, markup) -> None:
    try:
        await bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, reply_markup=markup,
                                    disable_web_page_preview=True)
    except TelegramBadRequest as e:
        if "not modified" not in str(e):
            log.warning("Server message %s/%s not updated: %s", chat_id, message_id, e)
    except TelegramAPIError as e:
        log.warning("Server message %s/%s not updated: %s", chat_id, message_id, e)


async def tick(bot: Bot, now: float | None = None) -> dict:
    """One check: a new message to everyone who wants it when the server started or the address changed, else
    the open messages brought up to date. Returns the state (kept in app_settings, so a restarted bot goes on)."""
    now = now or time.time()
    async with session_scope() as session:
        state = dict(await settings_store.get(session, "server_alert") or {})
        who = await targets(session)
    started = server_status().get("started") or state.get("started") or BOT_STARTED
    url = webapp_url()
    new = None
    if started != state.get("started"):
        new = "start"
    elif url and state.get("url") and url != state["url"]:
        new = "address"
    if new:
        state = {"started": started, "url": url, "kind": new, "at": int(now), "messages": {}, "done": False}
    elif url and not state.get("url"):
        state["url"] = url  # the address of this start became known
        await _save(state)
    if state.get("done") and not new:
        return state
    f = await facts(state)
    for chat_id, lang in who.items():
        text, markup, ok = render(lang, state, f, now)
        if str(chat_id) in state["messages"]:
            if not new and text != state.get("texts", {}).get(str(chat_id)):
                await _edit(bot, chat_id, state["messages"][str(chat_id)], text, markup)
        elif new:
            if mid := await _send(bot, chat_id, text, markup):
                state["messages"][str(chat_id)] = mid
        state.setdefault("texts", {})[str(chat_id)] = text
        state["done"] = ok or now - state["at"] > LIVE_FOR
    if not who:
        state["done"] = True
    await _save(state)
    return state


async def _save(state: dict) -> None:
    async with session_scope() as session:
        await settings_store.save(session, server_alert=state)


async def send_now(bot: Bot, chat_id: int, lang: str) -> None:
    """Just switched on: the current status at once (and kept up to date while the event is fresh)."""
    async with session_scope() as session:
        state = dict(await settings_store.get(session, "server_alert") or {})
    now = time.time()
    if not state:
        state = {"started": server_status().get("started") or BOT_STARTED, "url": webapp_url(), "kind": "start",
                 "at": int(now), "messages": {}, "done": False}
    text, markup, ok = render(lang, state, await facts(state), now)
    if (mid := await _send(bot, chat_id, text, markup)) and not state.get("done"):
        state.setdefault("messages", {})[str(chat_id)] = mid
        state.setdefault("texts", {})[str(chat_id)] = text
        await _save(state)


async def alerts_loop(bot: Bot) -> None:
    chatlog.origin.set("system")
    while True:
        try:
            await tick(bot)
        except Exception:  # a DB hiccup: try again on the next round
            log.exception("Server message check failed")
        await asyncio.sleep(EVERY)
