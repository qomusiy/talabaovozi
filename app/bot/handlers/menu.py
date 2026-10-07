"""The logged-in student's "home card": one message with the menu picture, the survey status and buttons.
Sections (teachers, profile, help, language) open in that same message with ⬅️ Back - no reply keyboard to open
or close. The timetable comes as a picture of its own, so it stays in the chat to look at later."""
from contextlib import suppress
from datetime import datetime
from html import escape
from zoneinfo import ZoneInfo

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app import settings_store
from app.bot import keyboards as kb
from app.bot import timetable
from app.bot.cards import CAPTION_LIMIT, edit_card, send_card, visible_length
from app.bot.i18n import LANGUAGE_NAMES, all_variants, t
from app.bot.menu_button import sync_menu_button
from app.models import Student
from app.services.students import active_campaign, current_semester, rated_teacher_ids, teachers_of
from app.timetable.view import latest

router = Router(name="menu")
TASHKENT = ZoneInfo("Asia/Tashkent")
PER_PAGE = 6  # at most this many teachers per page of "My teachers" (fewer if their text is long)
# Labels of the old reply keyboard: students who still have it on their phone get the home card instead.
OLD_BUTTONS = set().union(*(all_variants(k) for k in ("btn_survey", "btn_teachers", "btn_profile", "btn_help")))


async def logged_in(_, student: Student | None) -> bool:
    return student is not None


def progress_bar(done: int, total: int, width: int = 10) -> str:
    filled = round(width * done / total) if total else 0
    return f"{'🟩' * filled}{'⬜' * (width - filled)} {round(100 * done / total) if total else 0}%"


def first_name(full_name: str) -> str:
    """'Karimov Aziz Anvar o‘g‘li' -> 'Aziz' (Uzbek names: surname first)."""
    words = full_name.split()
    return words[1] if len(words) > 1 else (words[0] if words else "")


async def welcome_card(session: AsyncSession, lang: str, text: str | None = None) -> tuple[str, InlineKeyboardMarkup]:
    values = await settings_store.load(session)
    return text or t(lang, "welcome"), kb.welcome(lang, values["channel_url"])


async def home_card(session: AsyncSession, student: Student, lang: str, bot: Bot) -> tuple[str, InlineKeyboardMarkup]:
    group = student.group
    who = escape(group.name) if group else "—"
    values = await settings_store.load(session)
    channel = values["channel_url"]
    campaign = await active_campaign(session)
    if campaign is None:
        return t(lang, "home", name=escape(first_name(student.full_name)), group=who,
                 status=t(lang, "home_closed")), kb.home(lang, channel=channel)
    url = await sync_menu_button(bot)
    teacher_ids = {c.teacher.id for c in await teachers_of(session, student)}
    total = len(teacher_ids)
    done = len(await rated_teacher_ids(session, student, campaign) & teacher_ids)
    days = (campaign.closes_at.astimezone(TASHKENT).date() - datetime.now(TASHKENT).date()).days
    left = t(lang, "left_today") if days <= 0 else t(lang, "left_days", n=days)
    title = escape(campaign.title)
    if not total:
        status = t(lang, "no_teachers_in_survey", support=escape(settings_store.contacts(values)[0]))
        button = False
    elif done >= total:
        status = t(lang, "home_done", title=title, left=left, total=total) + (
            t(lang, "home_can_edit") if values["survey_edit"] else "")
        button = values["survey_edit"]
    else:
        status = t(lang, "home_open", title=title, left=left, done=done, total=total, bar=progress_bar(done, total),
                   cta=t(lang, "cta_start" if not done else "cta_continue"))
        button = True
    if button and not url:
        status += "\n\n" + t(lang, "survey_coming_soon")
    text = t(lang, "home", name=escape(first_name(student.full_name)), group=who, status=status)
    return text, kb.home(lang, url, survey=button, done=done >= total, channel=channel)


async def _forget_old_card(bot: Bot, chat_id: int, student: Student, keep: int) -> None:
    """Only the newest home card keeps buttons: an old one could open an address that no longer works."""
    if student.survey_message_id and student.survey_message_id != keep:
        with suppress(TelegramAPIError):
            await bot.edit_message_reply_markup(chat_id=chat_id, message_id=student.survey_message_id)
    student.survey_message_id = keep


async def drop_reply_keyboard(message: Message) -> None:
    """Remove the old always-open menu keyboard (a message must carry the removal; it is deleted at once)."""
    with suppress(TelegramAPIError):
        note = await message.answer("⌛", reply_markup=kb.remove)
        await message.bot.delete_message(chat_id=message.chat.id, message_id=note.message_id)


async def send_home(message: Message, session: AsyncSession, student: Student, lang: str) -> None:
    text, markup = await home_card(session, student, lang, message.bot)
    sent = await send_card(message.bot, message.chat.id, text, markup)
    await _forget_old_card(message.bot, message.chat.id, student, sent.message_id)


async def show_home(call: CallbackQuery, session: AsyncSession, student: Student, lang: str) -> None:
    """The home card in the message that was tapped."""
    text, markup = await home_card(session, student, lang, call.bot)
    shown = await edit_card(call.message, text, markup)
    await _forget_old_card(call.bot, call.message.chat.id, student, shown.message_id)


# ---------- Home ----------

@router.callback_query(F.data == "home", logged_in)
async def home_cb(call: CallbackQuery, session: AsyncSession, student: Student, lang: str) -> None:
    await show_home(call, session, student, lang)
    await call.answer()


@router.callback_query(F.data.in_({"home", "welcome"}))
async def welcome_cb(call: CallbackQuery, session: AsyncSession, student: Student | None, lang: str) -> None:
    """Back to the welcome card (not logged in)."""
    if student:
        await show_home(call, session, student, lang)
    else:
        await edit_card(call.message, *await welcome_card(session, lang))
    await call.answer()


@router.message(F.text.in_(OLD_BUTTONS), logged_in)
async def old_keyboard(message: Message, session: AsyncSession, student: Student, lang: str) -> None:
    await drop_reply_keyboard(message)
    await send_home(message, session, student, lang)


# ---------- Sections ----------

def teacher_blocks(cards, lang: str) -> list[str]:
    blocks = []
    for i, card in enumerate(cards, 1):
        subjects: dict[str, list[str]] = {}
        for subject, kind in card.lessons:
            subjects.setdefault(subject, []).append(t(lang, f"lesson_{kind}"))
        lines = [f"<b>{i}. {escape(card.teacher.full_name)}</b>"]
        lines += [f"    📚 {escape(s)} <i>({', '.join(kinds)})</i>" for s, kinds in subjects.items()]
        extra = []
        if card.teacher.department:
            extra.append(f"🏛 {escape(card.teacher.department.name)}")
        if card.teacher.room_number:
            extra.append(f"🚪 {t(lang, 'room')} {escape(card.teacher.room_number)}")
        if extra:
            lines.append("    " + "  ·  ".join(extra))
        blocks.append("\n".join(lines))
    return blocks


def paginate(header: str, blocks: list[str], limit: int = CAPTION_LIMIT - 60) -> list[list[str]]:
    """Pages of at most PER_PAGE blocks that fit under the menu picture (a photo caption is short)."""
    pages, page = [], []
    for block in blocks:
        trial = page + [block]
        if page and (len(trial) > PER_PAGE or visible_length(header + "\n\n" + "\n\n".join(trial)) > limit):
            pages.append(page)
            trial = [block]
        page = trial
    return pages + [page] if page else pages


@router.callback_query(F.data.startswith("teachers:"), logged_in)
async def teachers_cb(call: CallbackQuery, session: AsyncSession, student: Student, lang: str) -> None:
    cards = await teachers_of(session, student)
    if not cards:
        await edit_card(call.message, t(lang, "no_teachers"), kb.back(lang))
        await call.answer()
        return
    semester = await current_semester(session)
    header = t(lang, "teachers_header", semester=escape(semester.name) if semester else "")
    pages = paginate(header, teacher_blocks(cards, lang))
    arg = call.data.split(":")[1]
    page = min(max(1, int(arg) if arg.isdigit() else 1), len(pages))
    await edit_card(call.message, header + "\n\n" + "\n\n".join(pages[page - 1]), kb.pages(lang, page, len(pages)))
    await call.answer()


@router.callback_query(F.data == "profile", logged_in)
async def profile_cb(call: CallbackQuery, student: Student, lang: str) -> None:
    group = student.group
    await edit_card(call.message, t(lang, "profile", name=escape(student.full_name), hemis=student.hemis_id,
                                    group=escape(group.name) if group else "—",
                                    course=(group.course if group and group.course else "—"),
                                    language=LANGUAGE_NAMES[student.language]), kb.profile(lang))
    await call.answer()


# ---------- Log out (Profile › 🚪) ----------

@router.callback_query(F.data == "logout", logged_in)
async def logout_ask(call: CallbackQuery, lang: str) -> None:
    await edit_card(call.message, t(lang, "logout_confirm"), kb.logout_confirm(lang))
    await call.answer()


@router.callback_query(F.data == "logout:yes", logged_in)
async def logout(call: CallbackQuery, state: FSMContext, session: AsyncSession, student: Student, lang: str) -> None:
    """Free the account from this Telegram (another phone, or a friend's): the ratings stay, logging in again
    needs the HEMIS number and passport."""
    student.telegram_id, student.survey_message_id = None, None
    await state.clear()
    await state.update_data(lang=lang)
    await edit_card(call.message, *await welcome_card(session, lang, t(lang, "logged_out")))
    await call.answer()


# ---------- Timetable: a picture of the group's week ----------

async def send_timetable(message: Message, session: AsyncSession, student: Student, lang: str) -> str | None:
    """Sends the picture; returns the reason (a text for the student) if there is none to send."""
    tt = await latest(session)
    gid = timetable.find_group(tt, student.group) if tt else None
    if gid is None or not tt.by_group[gid]:
        return t(lang, "tt_none")
    with suppress(TelegramAPIError):
        await message.bot.send_chat_action(message.chat.id, "upload_photo")
    now = datetime.now(TASHKENT)
    photo, caption = await timetable.picture(tt, gid, lang, now)
    if not visible_length(caption) <= CAPTION_LIMIT:
        caption = caption[:caption.index("\n\n")]  # just the title
    file = photo if isinstance(photo, str) else BufferedInputFile(photo, filename=f"{tt.groups[gid]['name']}.png")
    sent = await message.answer_photo(file, caption=caption)
    if sent.photo and not isinstance(photo, str):
        timetable.remember(tt, gid, lang, now, sent.photo[-1].file_id)
    return None


@router.callback_query(F.data == "timetable", logged_in)
async def timetable_cb(call: CallbackQuery, session: AsyncSession, student: Student, lang: str) -> None:
    await call.answer(t(lang, "tt_loading"))
    if problem := await send_timetable(call.message, session, student, lang):
        await call.message.answer(problem, reply_markup=kb.back(lang))


@router.message(Command("timetable"), logged_in)
async def timetable_cmd(message: Message, session: AsyncSession, student: Student, lang: str) -> None:
    if problem := await send_timetable(message, session, student, lang):
        await message.answer(problem)


# ---------- Help ----------

async def help_text(session: AsyncSession, lang: str) -> str:
    support, tech = settings_store.contacts(await settings_store.load(session))
    return t(lang, "help", support=escape(support), tech=escape(tech))


@router.callback_query(F.data == "help")
async def help_cb(call: CallbackQuery, session: AsyncSession, student: Student | None, lang: str) -> None:
    await edit_card(call.message, await help_text(session, lang), kb.back(lang, "home" if student else "welcome"))
    await call.answer()


@router.message(Command("help"))
async def help_cmd(message: Message, session: AsyncSession, student: Student | None, lang: str) -> None:
    await message.answer(await help_text(session, lang), reply_markup=kb.back(lang) if student else None)


@router.callback_query(F.data == "noop")
async def noop(call: CallbackQuery) -> None:
    await call.answer()


# ---------- Anything else ----------

@router.message()
async def fallback(message: Message, session: AsyncSession, student: Student | None, lang: str,
                   admin=None) -> None:
    if admin is not None:  # a dashboard account linked to this Telegram: its admin card
        from app.bot.handlers.admin import send_admin_home
        await send_admin_home(message, session, admin, lang, student)
    elif student:
        await send_home(message, session, student, lang)
    else:
        await message.answer(t(lang, "need_login"))


@router.callback_query()
async def stale_button(call: CallbackQuery, lang: str) -> None:
    await call.answer(t(lang, "need_login"), show_alert=True)
