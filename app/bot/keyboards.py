"""Inline buttons. The bot has no reply keyboard: everything is a card with buttons under it, and a tap swaps
the card for the next one (with ⬅️ Back), like a small app."""
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove, WebAppInfo

from app.bot.i18n import LANGUAGE_NAMES, t


def _b(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=data)


def home(lang: str, url: str = "", survey: bool = False, done: bool = False, channel: str = "",
         group: bool = True) -> InlineKeyboardMarkup:
    """The home card's buttons. The survey button opens the Mini App (only while a survey is open). Everything
    else needs a group: without one, the first button picks it."""
    help_row = [_b(t(lang, "btn_help"), "help")]
    if channel:
        help_row.append(InlineKeyboardButton(text=t(lang, "btn_channel"), url=channel))
    if not group:
        return InlineKeyboardMarkup(inline_keyboard=[
            [_b(t(lang, "btn_pick_group"), "pick:home")], [_b(t(lang, "btn_language"), "choose_lang")], help_row])
    rows = []
    if survey and url:
        label = t(lang, "btn_review") if done else t(lang, "btn_open_survey")
        rows.append([InlineKeyboardButton(text=label, web_app=WebAppInfo(url=f"{url}/survey"))])
    rows.append([_b(t(lang, "btn_timetable"), "timetable"), _b(t(lang, "btn_teachers"), "teachers:1")])
    rows.append([_b(t(lang, "btn_change_group"), "pick:home"), _b(t(lang, "btn_language"), "choose_lang")])
    rows.append(help_row)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def back(lang: str, to: str = "home") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[_b(t(lang, "btn_back"), to)]])


# ---------- The introduction and picking a group: course › specialty › group ----------
# Callback data carries where "Back" from the first step leads: pick:<from>, pc:<from>:<course>,
# ps:<from>:<course>:<code>, pg:<group id> - <from> is intro or home.

def intro(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[_b(t(lang, "btn_pick_group"), "pick:intro")]])


def _grid(buttons: list[InlineKeyboardButton], per_row: int) -> list[list[InlineKeyboardButton]]:
    return [buttons[i:i + per_row] for i in range(0, len(buttons), per_row)]


def _picker_tail(lang: str, back_to: str) -> list[list[InlineKeyboardButton]]:
    return [[_b(t(lang, "btn_back"), back_to)]]


def pick_course(lang: str, came_from: str, courses: list[int]) -> InlineKeyboardMarkup:
    back_to = "intro" if came_from == "intro" else "home"
    return InlineKeyboardMarkup(inline_keyboard=[
        *_grid([_b(t(lang, "course_n", n=c), f"pc:{came_from}:{c}") for c in courses], 2),
        *_picker_tail(lang, back_to)])


def pick_specialty(lang: str, came_from: str, course: int, specialties: list[tuple[str, str]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        *[[_b(name, f"ps:{came_from}:{course}:{code}")] for code, name in specialties],
        *_picker_tail(lang, f"pick:{came_from}")])


def pick_group(lang: str, came_from: str, course: int, groups: list) -> InlineKeyboardMarkup:
    """The number students know a group by ("302") once an admin has typed it in, else its name."""
    return InlineKeyboardMarkup(inline_keyboard=[
        *_grid([_b(g.number or g.name, f"pg:{g.id}") for g in groups], 3 if all(g.number for g in groups) else 2),
        *_picker_tail(lang, f"pc:{came_from}:{course}")])


def pages(lang: str, page: int, total: int) -> InlineKeyboardMarkup:
    """◀️ 2 / 3 ▶️ under a long list, then Back."""
    nav = []
    if total > 1:
        nav = [_b("◀️", f"teachers:{page - 1}") if page > 1 else _b(" ", "noop"),
               _b(t(lang, "teachers_page", page=page, pages=total), "noop"),
               _b("▶️", f"teachers:{page + 1}") if page < total else _b(" ", "noop")]
    return InlineKeyboardMarkup(inline_keyboard=[*([nav] if nav else []), [_b(t(lang, "btn_back"), "home")]])


def languages(lang: str = "uz", back_to: str = "") -> InlineKeyboardMarkup:
    items = list(LANGUAGE_NAMES.items())
    rows = [[_b(name, f"lang:{code}") for code, name in items[i:i + 2]] for i in range(0, len(items), 2)]
    if back_to:
        rows.append([_b(t(lang, "btn_back"), back_to)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def open_survey(lang: str, url: str) -> InlineKeyboardMarkup:
    """A single "start evaluating" button (messages to the bot's users from the dashboard, reminders)."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(lang, "btn_open_survey"), web_app=WebAppInfo(url=url))]])


remove = ReplyKeyboardRemove()
