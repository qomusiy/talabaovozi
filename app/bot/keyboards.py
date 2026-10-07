"""Inline buttons. The bot has no reply keyboard: everything is a message with buttons under it, and sections
open in that same message (with ⬅️ Back), like a small app."""
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove, WebAppInfo

from app.bot.i18n import LANGUAGE_NAMES, t


def _b(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=data)


def _channel_row(lang: str, channel: str) -> list[list[InlineKeyboardButton]]:
    """The faculty's Telegram channel (dashboard › Telegram bot › settings; empty = no button)."""
    return [[InlineKeyboardButton(text=t(lang, "btn_channel"), url=channel)]] if channel else []


def home(lang: str, url: str = "", survey: bool = False, done: bool = False, channel: str = "") -> InlineKeyboardMarkup:
    """The home card's buttons. The survey button opens the Mini App (only while a survey is open)."""
    rows = []
    if survey and url:
        label = t(lang, "btn_review") if done else t(lang, "btn_open_survey")
        rows.append([InlineKeyboardButton(text=label, web_app=WebAppInfo(url=f"{url}/survey"))])
    rows += [[_b(t(lang, "btn_timetable"), "timetable"), _b(t(lang, "btn_teachers"), "teachers:1")],
             [_b(t(lang, "btn_profile"), "profile"), _b(t(lang, "btn_language"), "choose_lang")]]
    if channel:
        rows.append([_b(t(lang, "btn_help"), "help"), InlineKeyboardButton(text=t(lang, "btn_channel"), url=channel)])
    else:
        rows.append([_b(t(lang, "btn_help"), "help")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def back(lang: str, to: str = "home") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[_b(t(lang, "btn_back"), to)]])


def profile(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[_b(t(lang, "btn_logout"), "logout")],
                                                 [_b(t(lang, "btn_back"), "home")]])


def logout_confirm(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[_b(t(lang, "btn_logout_yes"), "logout:yes")],
                                                 [_b(t(lang, "btn_back"), "profile")]])


def pages(lang: str, page: int, total: int) -> InlineKeyboardMarkup:
    """◀️ 2 / 3 ▶️ under a long list, then Back."""
    nav = []
    if total > 1:
        nav = [_b("◀️", f"teachers:{page - 1}") if page > 1 else _b(" ", "noop"),
               _b(t(lang, "teachers_page", page=page, pages=total), "noop"),
               _b("▶️", f"teachers:{page + 1}") if page < total else _b(" ", "noop")]
    return InlineKeyboardMarkup(inline_keyboard=[*([nav] if nav else []), [_b(t(lang, "btn_back"), "home")]])


def languages(back_to_home: bool = False, lang: str = "uz", back_to: str = "") -> InlineKeyboardMarkup:
    items = list(LANGUAGE_NAMES.items())
    rows = [[_b(name, f"lang:{code}") for code, name in items[i:i + 2]] for i in range(0, len(items), 2)]
    if back_to_home or back_to:
        rows.append([_b(t(lang, "btn_back"), back_to or "home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def welcome(lang: str, channel: str = "") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [_b(t(lang, "btn_login"), "login")],
        [_b(t(lang, "btn_language"), "choose_lang"), _b(t(lang, "btn_help"), "help")],
        *_channel_row(lang, channel),
    ])


def cancel(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[_b(t(lang, "btn_cancel"), "cancel")]])


def retry(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[_b(t(lang, "btn_retry"), "login")]])


def open_survey(lang: str, url: str) -> InlineKeyboardMarkup:
    """A single "start evaluating" button (messages to students from the dashboard, reminders)."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(lang, "btn_open_survey"), web_app=WebAppInfo(url=url))]])


remove = ReplyKeyboardRemove()
