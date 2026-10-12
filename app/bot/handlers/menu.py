"""The user's "home card": one message with the menu picture, the survey status and buttons. Sections (teachers,
help, language, picking a group) replace it with a card of their own that has ⬅️ Back - no reply keyboard to open
or close. The timetable comes as a picture of its own, so it stays in the chat to look at later."""
from contextlib import suppress
from datetime import datetime
from html import escape
from zoneinfo import ZoneInfo

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command
from aiogram.types import BufferedInputFile, CallbackQuery, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app import settings_store
from app.bot import keyboards as kb
from app.bot import timetable
from app.bot.cards import CAPTION_LIMIT, remove_card, send_card, swap_card, visible_length
from app.bot.i18n import all_variants, t
from app.bot.menu_button import sync_menu_button
from app.models import BotUser
from app.services.survey import active_campaign, current_semester, rated_teacher_ids, teachers_of
from app.services.users import group_name
from app.timetable.view import latest

router = Router(name="menu")
TASHKENT = ZoneInfo("Asia/Tashkent")
PER_PAGE = 6  # at most this many teachers per page of "My teachers" (fewer if their text is long)
# Labels of the old reply keyboard: students who still have it on their phone get the home card instead.
OLD_BUTTONS = {"📝 Baholash", "📝 Evaluate", "📝 Оценить", "📝 Baha bermek", "👤 Profil", "👤 Profile", "👤 Профиль",
               *all_variants("btn_teachers"), *all_variants("btn_help")}


async def onboarded(_, user: BotUser | None) -> bool:
    return user is not None and user.onboarded_at is not None


def greeting(lang: str, now: datetime | None = None) -> str:
    hour = (now or datetime.now(TASHKENT)).hour
    return t(lang, "greet_morning" if 5 <= hour < 11 else "greet_day" if 11 <= hour < 18 else "greet_evening")


async def home_card(session: AsyncSession, user: BotUser, lang: str, bot: Bot) -> tuple[str, InlineKeyboardMarkup]:
    has_group = user.group_id is not None
    values = await settings_store.load(session)
    channel = values["channel_url"]
    campaign = await active_campaign(session)

    def card(*lines: str, markup: InlineKeyboardMarkup) -> tuple[str, InlineKeyboardMarkup]:
        status = "\n\n".join(x for x in lines if x)
        return t(lang, "home", greeting=greeting(lang), group=escape(group_name(user.group, lang)), status=status), markup

    if campaign is None:
        return card(t(lang, "survey_closed"), markup=kb.home(lang, channel=channel, group=has_group))
    days = (campaign.closes_at.astimezone(TASHKENT).date() - datetime.now(TASHKENT).date()).days
    status = t(lang, "survey_open") + "\n" + (t(lang, "closes_today") if days <= 0 else t(lang, "closes_in", n=days))
    if not has_group:
        return card(status, t(lang, "cta_pick_group"), markup=kb.home(lang, channel=channel, group=False))
    url = await sync_menu_button(bot)
    rated = await rated_teacher_ids(session, user, campaign)
    teacher_ids = {c.teacher.id for c in await teachers_of(session, user)}
    total, done = len(teacher_ids), len(rated & teacher_ids)
    if not total:
        lines = [t(lang, "no_teachers_in_survey", support=escape(settings_store.contacts(values)[0]))]
        button = False
    elif done >= total:
        lines = [t(lang, "rated_n", done=done, total=total),
                 t(lang, "home_thanks") + ("\n" + t(lang, "home_can_edit") if values["survey_edit"] else "")]
        button = values["survey_edit"]
    else:
        lines = [t(lang, "rated_n", done=done, total=total), t(lang, "cta_continue" if done else "cta_start")]
        button = True
    if button and not url:
        lines[-1] = t(lang, "survey_coming_soon")
    return card(status, *lines, markup=kb.home(lang, url, survey=button, done=done >= total, channel=channel))


async def _forget_old_card(bot: Bot, chat_id: int, user: BotUser, keep: int) -> None:
    """Only the newest home card stays: an old one could open an address that no longer works."""
    if user.survey_message_id and user.survey_message_id != keep:
        await remove_card(bot, chat_id, user.survey_message_id)
    user.survey_message_id = keep


async def drop_reply_keyboard(message: Message) -> None:
    """Remove the old always-open menu keyboard (a message must carry the removal; it is deleted at once)."""
    with suppress(TelegramAPIError):
        note = await message.answer("⌛", reply_markup=kb.remove)
        await message.bot.delete_message(chat_id=message.chat.id, message_id=note.message_id)


async def send_home(message: Message, session: AsyncSession, user: BotUser, lang: str) -> None:
    text, markup = await home_card(session, user, lang, message.bot)
    sent = await send_card(message.bot, message.chat.id, text, markup)
    await _forget_old_card(message.bot, message.chat.id, user, sent.message_id)


async def show_home(call: CallbackQuery, session: AsyncSession, user: BotUser, lang: str) -> None:
    """The home card in place of the card that was tapped."""
    text, markup = await home_card(session, user, lang, call.bot)
    shown = await swap_card(call.message, text, markup)
    await _forget_old_card(call.bot, call.message.chat.id, user, shown.message_id)


# ---------- Home ----------

@router.callback_query(F.data == "home")
async def home_cb(call: CallbackQuery, session: AsyncSession, user: BotUser, lang: str) -> None:
    await show_home(call, session, user, lang)
    await call.answer()


@router.message(F.text.in_(OLD_BUTTONS), onboarded)
async def old_keyboard(message: Message, session: AsyncSession, user: BotUser, lang: str) -> None:
    await drop_reply_keyboard(message)
    await send_home(message, session, user, lang)


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


def pick_first(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[*kb.home(lang, group=False).inline_keyboard[0]],
                                                 [*kb.back(lang).inline_keyboard[0]]])


@router.callback_query(F.data.startswith("teachers:"))
async def teachers_cb(call: CallbackQuery, session: AsyncSession, user: BotUser, lang: str) -> None:
    if user.group_id is None:
        await swap_card(call.message, t(lang, "no_group"), pick_first(lang))
        await call.answer()
        return
    cards = await teachers_of(session, user)
    if not cards:
        await swap_card(call.message, t(lang, "no_teachers"), kb.back(lang))
        await call.answer()
        return
    semester = await current_semester(session)
    header = t(lang, "teachers_header", semester=escape(semester.name) if semester else "")
    pages = paginate(header, teacher_blocks(cards, lang))
    arg = call.data.split(":")[1]
    page = min(max(1, int(arg) if arg.isdigit() else 1), len(pages))
    await swap_card(call.message, header + "\n\n" + "\n\n".join(pages[page - 1]), kb.pages(lang, page, len(pages)))
    await call.answer()


# ---------- Timetable: a picture of the group's week ----------

async def send_timetable(message: Message, session: AsyncSession, user: BotUser, lang: str) -> str | None:
    """Sends the picture; returns the reason (a text for the person) if there is none to send."""
    if user.group is None:
        return t(lang, "tt_need_group")
    tt = await latest(session)
    gid = timetable.find_group(tt, user.group) if tt else None
    if gid is None or not tt.by_group[gid]:
        return t(lang, "tt_none")
    with suppress(TelegramAPIError):
        await message.bot.send_chat_action(message.chat.id, "upload_photo")
    title = group_name(user.group, lang)
    photo, caption = await timetable.picture(tt, gid, lang, title)
    file = photo if isinstance(photo, str) else BufferedInputFile(photo, filename=f"{tt.groups[gid]['name']}.png")
    sent = await message.answer_photo(file, caption=caption)
    if sent.photo and not isinstance(photo, str):
        timetable.remember(tt, gid, lang, title, sent.photo[-1].file_id)
    return None


@router.callback_query(F.data == "timetable")
async def timetable_cb(call: CallbackQuery, session: AsyncSession, user: BotUser, lang: str) -> None:
    await call.answer(t(lang, "tt_loading"))
    if problem := await send_timetable(call.message, session, user, lang):
        await swap_card(call.message, problem, pick_first(lang) if user.group is None else kb.back(lang))
    else:  # the picture stays in the chat to keep; the menu moves under it, so the chat still ends with the menu
        await show_home(call, session, user, lang)


@router.message(Command("timetable"))
async def timetable_cmd(message: Message, session: AsyncSession, user: BotUser, lang: str) -> None:
    if problem := await send_timetable(message, session, user, lang):
        await message.answer(problem, reply_markup=pick_first(lang) if user.group is None else None)


# ---------- Help ----------

async def help_text(session: AsyncSession, lang: str) -> str:
    support, tech = settings_store.contacts(await settings_store.load(session))
    return t(lang, "help", support=escape(support), tech=escape(tech))


@router.callback_query(F.data == "help")
async def help_cb(call: CallbackQuery, session: AsyncSession, lang: str) -> None:
    await swap_card(call.message, await help_text(session, lang), kb.back(lang))
    await call.answer()


@router.message(Command("help"))
async def help_cmd(message: Message, session: AsyncSession, user: BotUser, lang: str) -> None:
    await message.answer(await help_text(session, lang), reply_markup=kb.back(lang) if user.onboarded_at else None)


@router.callback_query(F.data == "noop")
async def noop(call: CallbackQuery) -> None:
    await call.answer()


# ---------- Anything else ----------

@router.message()
async def fallback(message: Message, session: AsyncSession, user: BotUser, lang: str, admin=None) -> None:
    if admin is not None:  # a dashboard account linked to this Telegram: its admin card
        from app.bot.handlers.admin import send_admin_home
        await send_admin_home(message, session, admin, lang)
    elif user.onboarded_at is None:  # the first visit: the language first
        await send_card(message.bot, message.chat.id, t(lang, "pick_language"), kb.languages())
    else:
        await send_home(message, session, user, lang)


@router.callback_query()
async def stale_button(call: CallbackQuery, session: AsyncSession, user: BotUser, lang: str) -> None:
    """A button the bot no longer has (e.g. the old "Log in"): the home card instead (or the language, the first
    time)."""
    if user.onboarded_at is None:
        await swap_card(call.message, t(lang, "pick_language"), kb.languages())
        await call.answer()
    else:
        await home_cb(call, session, user, lang)
