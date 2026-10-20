"""The bot for dashboard accounts linked to Telegram (app.services.admin_link): a card with the survey's numbers,
the site's addresses, details, a Mini App with charts, and switches - server status messages (app.bot.server_alerts)
and the daily report, both off until switched on. Other users never see any of it; viewers see the numbers,
superadmins can also ask for a new public address, the programmer account has 🖥 Server: the server computer from
anywhere - its state, update from GitHub, restart, backup (the launcher does them, app.server.Launcher), and
🩺 Diagnostics: why the site doesn't open, checked on the server computer (app.diagnose), with its logs."""
import asyncio
import platform
from contextlib import suppress
from datetime import datetime
from html import escape

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command
from aiogram.types import (BotCommand, BotCommandScopeChat, BufferedInputFile, CallbackQuery, InlineKeyboardButton,
                           InlineKeyboardMarkup, Message, WebAppInfo)
from sqlalchemy.ext.asyncio import AsyncSession

from app import audit, diagnose, settings_store
from app.bot import server_alerts
from app.bot.admin_i18n import ta
from app.bot.cards import send_card, swap_card
from app.bot.handlers.menu import TASHKENT
from app.bot.i18n import t
from app.config import get_settings
from app.models import Admin
from app import backup
from app.runtime import (control_log, fixed_address, launcher_alive, request_control, request_tunnel_restart,
                         server_status, version_info)
from app.services import admin_link, admin_stats
from app.web.admin.i18n import translator

router = Router(name="admin")


async def is_admin(_, admin: Admin | None) -> bool:
    return admin is not None


def admin_lang(lang: str) -> str:
    return lang if lang in ("uz", "en", "ru") else "uz"


def _b(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=data)


def _left(lang: str, days: int) -> str:
    return ta(lang, "left_today") if days <= 0 else ta(lang, "left_days", n=days)


def site_text(lang: str, site: dict) -> str:
    return ta(lang, f"site_{site['state']}" if site["state"] in ("ok", "down", "starting", "none") else "site_unknown")


def survey_text(lang: str, s: dict) -> str:
    c = s["campaign"]
    if c is None:
        return ta(lang, "survey_none")
    values = {"title": escape(c["title"]), "pct": s["participation_pct"], "evaluations": s["evaluations"],
              "overall": s["overall"] if s["overall"] is not None else "—"}
    if not c["open"]:
        return ta(lang, "survey_closed", **values)
    return ta(lang, "survey_open", **values, left=_left(lang, c["days_left"]), participants=s["participants"],
              completed=s["completed"], today=s["today"], comments=s["comments"])


async def admin_card(session: AsyncSession, admin: Admin, lang: str) -> tuple:
    lang = admin_lang(lang)
    s = await admin_stats.snapshot(session)
    name = escape((admin.telegram_name or admin.username).split()[0])
    text = ta(lang, "home", name=name, role=translator(lang)(f"role_{admin.role}"), survey=survey_text(lang, s),
              in_bot=s["in_bot"], students=s["students"], site=site_text(lang, s["site"]))
    prefs = admin.prefs or {}
    rows = []
    if s["site"]["url"]:
        rows.append([InlineKeyboardButton(text=ta(lang, "btn_app"),
                                          web_app=WebAppInfo(url=f"{s['site']['url']}/miniapp/admin"))])
    rows += [[_b(ta(lang, "btn_links"), "adm:links"), _b(ta(lang, "btn_stats"), "adm:stats")],
             [_b(ta(lang, "btn_notify_on" if prefs.get("tg_server") else "btn_notify_off"), "adm:notify"),
              _b(ta(lang, "btn_daily_on" if prefs.get("tg_daily") else "btn_daily_off"), "adm:daily")]]
    tools = [_b(ta(lang, "btn_refresh"), "adm:home")]
    if admin.is_super and not fixed_address():
        tools.append(_b(ta(lang, "btn_tunnel"), "adm:tunnel"))
    rows.append(tools)
    if admin.is_programmer:
        rows.append([_b(ta(lang, "btn_server"), "adm:srv")])
    rows.append([_b(ta(lang, "btn_student"), "home"), _b(ta(lang, "btn_unlink"), "adm:unlink")])
    return text, InlineKeyboardMarkup(inline_keyboard=rows)


def back(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[_b(ta(lang, "btn_back"), "adm:home")]])


async def links_card(session: AsyncSession, lang: str) -> tuple:
    lang = admin_lang(lang)
    site = admin_stats.site_state()
    if not site["url"]:
        return ta(lang, "no_url"), InlineKeyboardMarkup(inline_keyboard=[[_b(ta(lang, "btn_refresh"), "adm:links")],
                                                                          [_b(ta(lang, "btn_back"), "adm:home")]])
    online = not get_settings().admin_local_only or await settings_store.get(session, "admin_online")
    admin = ta(lang, "admin_online", url=site["url"]) if online else ta(lang, "admin_local", port=get_settings().web_port)
    checked = ta(lang, "checked", n=site["ago_min"]) if site["ago_min"] is not None else ""
    text = ta(lang, "links", url=site["url"], admin=admin, site=site_text(lang, site), checked=checked)
    buttons = [InlineKeyboardButton(text=ta(lang, "btn_open_survey"), web_app=WebAppInfo(url=f"{site['url']}/survey"))]
    if online:
        buttons.insert(0, InlineKeyboardButton(text=ta(lang, "btn_open_admin"), url=f"{site['url']}/admin"))
    return text, InlineKeyboardMarkup(inline_keyboard=[buttons, [_b(ta(lang, "btn_refresh"), "adm:links"),
                                                                 _b(ta(lang, "btn_back"), "adm:home")]])


def _bar(pct: float, width: int = 8) -> str:
    filled = round(width * pct / 100)
    return "▓" * filled + "░" * (width - filled)


async def stats_text(session: AsyncSession, lang: str) -> str:
    lang = admin_lang(lang)
    s = await admin_stats.snapshot(session, detail=True)
    if s["campaign"] is None:
        return ta(lang, "survey_none")
    courses = "\n".join(ta(lang, "course_line", course=c["course"] or "?", bar=_bar(c["participation_pct"]),
                           pct=c["participation_pct"], p=c["participants"], n=c["students"]) for c in s["courses"])
    low = "\n".join(ta(lang, "low_line", name=escape(g["name"]), pct=g["participation_pct"], p=g["participants"],
                       n=g["students"]) for g in s["low_groups"])
    daily = "\n".join(ta(lang, "day_line", date=datetime.fromisoformat(d["date"]).strftime("%d.%m"), n=d["count"])
                      for d in s["daily"])
    dash = ta(lang, "nothing")
    return ta(lang, "stats", title=escape(s["campaign"]["title"]), courses=courses or dash, low=low or dash,
              daily=daily or dash, **{k: s[k] if s[k] is not None else dash
                                      for k in ("teaching", "fairness", "professionalism")})


async def send_admin_home(message: Message, session: AsyncSession, admin: Admin, lang: str) -> None:
    await send_card(message.bot, message.chat.id, *await admin_card(session, admin, lang))


async def set_admin_commands(bot: Bot, chat_id: int, lang: str) -> None:
    """Linked admins get the admin commands in their Telegram menu (only in their own chat)."""
    lang = admin_lang(lang)
    with suppress(TelegramAPIError):
        await bot.set_my_commands([
            BotCommand(command="admin", description=ta(lang, "cmd_admin")),
            BotCommand(command="link", description=ta(lang, "cmd_link")),
            BotCommand(command="start", description=t(lang, "cmd_start")),
            BotCommand(command="help", description=t(lang, "cmd_help")),
        ], scope=BotCommandScopeChat(chat_id=chat_id))


async def welcome_linked(message: Message, admin: Admin, lang: str) -> None:
    """Said once, when this Telegram account has just been linked to a dashboard account."""
    await message.answer(ta(admin_lang(lang), "linked", username=escape(admin.username)))
    await set_admin_commands(message.bot, message.chat.id, lang)


# ---------------------------------------------------------------- commands

@router.message(Command("admin"), is_admin)
async def admin_cmd(message: Message, session: AsyncSession, admin: Admin, lang: str) -> None:
    await send_admin_home(message, session, admin, lang)


@router.message(Command("link"), is_admin)
async def link_cmd(message: Message, session: AsyncSession, lang: str) -> None:
    text, markup = await links_card(session, lang)
    await message.answer(text, reply_markup=markup)


# ---------------------------------------------------------------- 🖥 Server (the programmer account)

def _when(ts: int | float | None) -> str:
    return datetime.fromtimestamp(ts, TASHKENT).strftime("%d.%m %H:%M") if ts else "—"


def commit_lines(commits: list[dict], limit: int = 8) -> str:
    lines = [f"• <code>{escape(c['short'])}</code> {escape(c['subject'][:80])}" for c in commits[:limit]]
    if len(commits) > limit:
        lines.append(f"• … +{len(commits) - limit}")
    return "\n".join(lines)


def server_card(lang: str) -> tuple[str, InlineKeyboardMarkup]:
    lang = admin_lang(lang)
    st, info, log = server_status(), version_info(), control_log()
    lines = [ta(lang, "srv_title", host=escape(platform.node())), ""]
    if st:
        cloudflared = st.get("cloudflared") or {}
        parts = [ta(lang, "srv_tunnel_waiting") if name == "tunnel" and c.get("running")
                 and cloudflared.get("connected") is False else
                 ("🟢 " if c.get("running") else "🔴 ") + ta(lang, f"srv_part_{name}")
                 for name, c in (st.get("children") or {}).items() if name in ("web", "bot", "tunnel")]
        lines += [" · ".join(parts), ta(lang, "srv_started", at=_when(st.get("started")))]
    else:
        lines.append(ta(lang, "srv_down"))
    if current := info.get("current"):
        lines.append(ta(lang, "srv_version", short=escape(current["short"]), date=current["date"][:10]))
    if info.get("error"):
        lines.append(ta(lang, "srv_check_error", e=escape(info["error"][:150])))
    elif info.get("failed"):
        lines.append(ta(lang, "srv_failed"))
    elif info.get("behind"):
        lines += [ta(lang, "srv_behind", n=info["behind"]), commit_lines(info.get("commits", []), 5)]
    elif current:
        lines.append(ta(lang, "srv_newest"))
    if last_copy := backup.newest():
        lines.append(ta(lang, "srv_backup", name=last_copy.name))
    active = next((e for e in log if e.get("state") == "running"), None)
    if active:
        lines += ["", ta(lang, "srv_busy", action=ta(lang, f"srv_act_{active['action']}"))]
    elif log:
        e = log[0]
        lines.append(ta(lang, "srv_last", action=ta(lang, f"srv_act_{e['action']}"),
                        result=ta(lang, f"srv_r_{e['state']}"), at=_when(e.get("finished") or e.get("at"))))
    alive = launcher_alive()
    if not alive:
        lines += ["", ta(lang, "srv_no_launcher")]
    rows = []
    if alive and not active:
        if info.get("behind") and not info.get("failed") and not info.get("ahead"):
            rows.append([_b(ta(lang, "btn_srv_update"), "adm:srv:update")])
        rows += [[_b(ta(lang, "btn_srv_restart"), "adm:srv:restart"), _b(ta(lang, "btn_srv_backup"), "adm:srv:backup")],
                 [_b(ta(lang, "btn_srv_check"), "adm:srv:check"), _b(ta(lang, "btn_srv_diag"), "adm:srv:diag")]]
    else:  # diagnostics need no launcher: the bot runs them itself
        rows.append([_b(ta(lang, "btn_srv_diag"), "adm:srv:diag")])
    rows.append([_b(ta(lang, "btn_refresh"), "adm:srv"), _b(ta(lang, "btn_back"), "adm:home")])
    return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=rows)


async def _programmer(call: CallbackQuery, admin: Admin, lang: str) -> bool:
    if admin.is_programmer:
        return True
    await call.answer(ta(admin_lang(lang), "srv_programmer_only"), show_alert=True)
    return False


@router.callback_query(F.data == "adm:srv", is_admin)
async def server_cb(call: CallbackQuery, admin: Admin, lang: str) -> None:
    if await _programmer(call, admin, lang):
        await swap_card(call.message, *server_card(lang))
        await call.answer()


@router.callback_query(F.data.in_({"adm:srv:update", "adm:srv:restart"}), is_admin)
async def server_confirm(call: CallbackQuery, admin: Admin, lang: str) -> None:
    if not await _programmer(call, admin, lang):
        return
    lang = admin_lang(lang)
    action = call.data.rsplit(":", 1)[1]
    text = (ta(lang, "srv_update_confirm", commits=commit_lines(version_info().get("commits", [])))
            if action == "update" else ta(lang, "srv_restart_confirm"))
    await swap_card(call.message, text, InlineKeyboardMarkup(inline_keyboard=[
        [_b(ta(lang, f"btn_srv_yes_{action}"), f"adm:srv:do:{action}")], [_b(ta(lang, "btn_back"), "adm:srv")]]))
    await call.answer()


@router.callback_query(F.data.in_({"adm:srv:do:update", "adm:srv:do:restart", "adm:srv:backup", "adm:srv:check"}),
                       is_admin)
async def server_do(call: CallbackQuery, session: AsyncSession, admin: Admin, lang: str) -> None:
    if not await _programmer(call, admin, lang):
        return
    lang = admin_lang(lang)
    action = call.data.rsplit(":", 1)[1]
    if not launcher_alive():
        await call.answer(ta(lang, "srv_no_launcher").split(".")[0], show_alert=True)
        return
    if any(e.get("state") == "running" for e in control_log()):
        await call.answer(ta(lang, "srv_busy_alert"), show_alert=True)
        return
    request_control(action, f"{admin.username} (Telegram)", notify=[call.message.chat.id])
    await audit.bot_action(session, admin, f"/bot/server/{action}", f"Telegram › Server › {action}")
    await call.answer(ta(lang, "srv_asked", action=ta(lang, f"srv_act_{action}")).replace("<b>", "").replace("</b>", ""))
    await swap_card(call.message, ta(lang, "srv_asked", action=ta(lang, f"srv_act_{action}")),
                    InlineKeyboardMarkup(inline_keyboard=[[_b(ta(lang, "btn_refresh"), "adm:srv"),
                                                           _b(ta(lang, "btn_back"), "adm:home")]]))


def diag_text(lang: str, r: dict) -> str:
    mark = {True: "✅", False: "❌", None: "➖"}
    lines = [ta(lang, "dg_title", host=escape(platform.node()), time=_when(r["at"])), ""]
    lines += [f"{mark[c['ok']]} {ta(lang, 'dg_' + c['name'])}: <code>{escape(str(c['detail']))}</code>"
              for c in r["checks"]]
    t = r["tunnel"]
    if t["mode"] in diagnose.CLOUDFLARE:
        lines += ["", ta(lang, "dg_tunnel", mode=escape(t["mode"]), version=escape(str(t["version"] or "?")))]
        if t["connected_now"] is not None:
            lines.append(ta(lang, "dg_now_on", protocol=t["protocol"]) if t["connected_now"] else
                         ta(lang, "dg_now_off", protocol=t["protocol"], misses=t["misses"]))
        if t["restarts"]:
            lines.append(ta(lang, "dg_restarts", n=t["restarts"]))
        lines.append(ta(lang, "dg_last_connected", at=escape(t["connected"]) or ta(lang, "dg_never")))
        if t["precheck"]:
            lines.append(ta(lang, "dg_precheck"))
            lines += [f"{mark[p['ok']]} {escape(name)}: {escape(p['details'])}" for name, p in t["precheck"].items()]
        if t["errors"]:
            lines += [ta(lang, "dg_errors"), "<pre>" + escape("\n".join(t["errors"])) + "</pre>"]
    lines += ["", ta(lang, "dg_verdict", text=ta(lang, f"dg_v_{r['verdict']}"))]
    text = "\n".join(lines)
    if len(text) > 4000:  # Telegram's limit is 4096: the errors are in the log file anyway
        text = "\n".join(line for line in lines if not line.startswith("<pre>"))
    return text


_diagnosing: set[int] = set()  # chats waiting for diagnostics (a second tap doesn't start them twice)


@router.callback_query(F.data == "adm:srv:diag", is_admin)
async def server_diag(call: CallbackQuery, session: AsyncSession, admin: Admin, lang: str) -> None:
    if not await _programmer(call, admin, lang):
        return
    lang, chat_id = admin_lang(lang), call.message.chat.id
    await call.answer(ta(lang, "dg_running"))
    if chat_id in _diagnosing:
        return
    _diagnosing.add(chat_id)
    try:
        report = await diagnose.report()
        await audit.bot_action(session, admin, "/bot/server/diagnose", "Telegram › Server › diagnose")
        host, now = platform.node(), datetime.now(TASHKENT)
        logs = await asyncio.to_thread(diagnose.logs_text)
        with suppress(TelegramAPIError):
            await call.message.bot.send_document(chat_id, BufferedInputFile(
                logs.encode("utf-8"), filename=f"logs-{host}-{now:%Y%m%d-%H%M}.txt"),
                caption=ta(lang, "dg_logs", host=escape(host), time=f"{now:%d.%m %H:%M}"))
        await swap_card(call.message, diag_text(lang, report), InlineKeyboardMarkup(inline_keyboard=[
            [_b(ta(lang, "btn_dg_again"), "adm:srv:diag")], [_b(ta(lang, "btn_back"), "adm:srv")]]))
    finally:
        _diagnosing.discard(chat_id)


# ---------------------------------------------------------------- the card's buttons

@router.callback_query(F.data == "adm:home", is_admin)
async def home_cb(call: CallbackQuery, session: AsyncSession, admin: Admin, lang: str) -> None:
    await swap_card(call.message, *await admin_card(session, admin, lang))
    await call.answer()


@router.callback_query(F.data == "adm:links", is_admin)
async def links_cb(call: CallbackQuery, session: AsyncSession, lang: str) -> None:
    await swap_card(call.message, *await links_card(session, lang))
    await call.answer()


@router.callback_query(F.data == "adm:stats", is_admin)
async def stats_cb(call: CallbackQuery, session: AsyncSession, lang: str) -> None:
    await swap_card(call.message, await stats_text(session, lang), back(admin_lang(lang)))
    await call.answer()


@router.callback_query(F.data.in_({"adm:notify", "adm:daily"}), is_admin)
async def toggle_cb(call: CallbackQuery, session: AsyncSession, admin: Admin, lang: str) -> None:
    key = "tg_server" if call.data == "adm:notify" else "tg_daily"
    prefs = dict(admin.prefs or {})
    prefs[key] = not prefs.get(key, False)
    admin.prefs = prefs
    name = {"tg_server": "notify", "tg_daily": "daily"}[key]
    await call.answer(ta(admin_lang(lang), f"{name}_{'on' if prefs[key] else 'off'}"))
    await swap_card(call.message, *await admin_card(session, admin, lang))
    if key == "tg_server" and prefs[key]:  # switched on: how things are right now
        await session.commit()
        await server_alerts.send_now(call.bot, call.message.chat.id, admin_lang(lang))


@router.callback_query(F.data == "adm:tunnel", is_admin)
async def tunnel_ask(call: CallbackQuery, admin: Admin, lang: str) -> None:
    lang = admin_lang(lang)
    if not admin.is_super:
        await call.answer(ta(lang, "super_only"), show_alert=True)
        return
    await swap_card(call.message, ta(lang, "tunnel_confirm"), InlineKeyboardMarkup(inline_keyboard=[
        [_b(ta(lang, "btn_tunnel_yes"), "adm:tunnel:yes")], [_b(ta(lang, "btn_back"), "adm:home")]]))
    await call.answer()


@router.callback_query(F.data == "adm:tunnel:yes", is_admin)
async def tunnel_yes(call: CallbackQuery, session: AsyncSession, admin: Admin, lang: str) -> None:
    lang = admin_lang(lang)
    if not admin.is_super:
        await call.answer(ta(lang, "super_only"), show_alert=True)
        return
    request_tunnel_restart()
    await audit.bot_action(session, admin, "/bot/tunnel", "Telegram › Yangi manzil olish")
    await swap_card(call.message, ta(lang, "tunnel_done"), back(lang))
    await call.answer()


@router.callback_query(F.data == "adm:unlink", is_admin)
async def unlink_ask(call: CallbackQuery, lang: str) -> None:
    lang = admin_lang(lang)
    await swap_card(call.message, ta(lang, "unlink_confirm"), InlineKeyboardMarkup(inline_keyboard=[
        [_b(ta(lang, "btn_unlink_yes"), "adm:unlink:yes")], [_b(ta(lang, "btn_back"), "adm:home")]]))
    await call.answer()


@router.callback_query(F.data == "adm:unlink:yes", is_admin)
async def unlink_yes(call: CallbackQuery, session: AsyncSession, admin: Admin, lang: str) -> None:
    admin_link.unlink(admin)
    await audit.bot_action(session, admin, "/bot/unlink", "Telegram › Botdan uzish")
    with suppress(TelegramAPIError):
        await call.bot.delete_my_commands(scope=BotCommandScopeChat(chat_id=call.message.chat.id))
    await swap_card(call.message, ta(admin_lang(lang), "unlinked"), None)
    await call.answer()


@router.callback_query(F.data.startswith("adm:"))
async def not_admin(call: CallbackQuery, lang: str) -> None:
    """A button of an admin card in a chat that is no longer linked."""
    await call.answer(ta(admin_lang(lang), "unlinked"), show_alert=True)


# ---------------------------------------------------------------- the daily report (bot's background loop)

async def daily_report_text(session: AsyncSession, lang: str) -> str | None:
    lang = admin_lang(lang)
    s = await admin_stats.snapshot(session)
    c = s["campaign"]
    if c is None or not c["open"]:
        return None
    return ta(lang, "daily_report", date=datetime.now(TASHKENT).strftime("%d.%m.%Y"), title=escape(c["title"]),
              left=_left(lang, c["days_left"]), today=s["today"], pct=s["participation_pct"],
              participants=s["participants"], completed=s["completed"],
              overall=s["overall"] if s["overall"] is not None else "—")
