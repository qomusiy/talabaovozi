"""/start, the language, the introduction and picking a group (course › specialty › group).

The first time, a person picks the language, reads what the bot is (anonymous; the group only decides which
teachers they see), then picks their group. After that /start brings the home card, where "Change group" leads
through the same three steps."""
from datetime import datetime, timezone
from html import escape

from aiogram import F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot import keyboards as kb
from app.bot.cards import send_card, swap_card
from app.bot.handlers.menu import drop_reply_keyboard, send_home, show_home
from app.bot.i18n import LANGUAGE_NAMES, t
from app.faculty import specialty_name
from app.models import Admin, BotUser
from app.services import admin_link, users
from app.services.users import group_name

router = Router(name="start")


def _int(raw: str) -> int | None:
    return int(raw) if raw.isdigit() else None


@router.message(CommandStart())
@router.message(Command("menu"))
async def cmd_start(message: Message, session: AsyncSession, user: BotUser, lang: str,
                    command: CommandObject | None = None, admin: Admin | None = None,
                    admin_linked_now: bool = False) -> None:
    from app.bot.handlers import admin as admin_menu  # (imports this module's neighbours)
    if user.onboarded_at:  # the old always-open menu, if this phone still shows it (only people from before)
        await drop_reply_keyboard(message)
    payload = (command.args or "") if command else ""
    if payload.startswith(admin_link.TOKEN_PREFIX):  # the one-time link from the dashboard's "My account"
        linked = await admin_link.by_token(session, payload.removeprefix(admin_link.TOKEN_PREFIX), message.from_user)
        if linked is None:
            await message.answer(admin_menu.ta(admin_menu.admin_lang(lang), "link_bad"))
        else:
            admin, admin_linked_now = linked, True
    if admin is not None:
        if admin_linked_now:
            await admin_menu.welcome_linked(message, admin, lang)
        await admin_menu.send_admin_home(message, session, admin, lang)
    elif user.onboarded_at is None:
        await send_card(message.bot, message.chat.id, t(lang, "pick_language"), kb.languages())
    else:
        await send_home(message, session, user, lang)


@router.message(Command("myid"))
async def my_id(message: Message, lang: str) -> None:
    """Admins send this to get their Telegram ID."""
    await message.answer(t(lang, "my_id", id=message.from_user.id))


# ---------- Language ----------

@router.message(Command("language"))
async def ask_language(message: Message, user: BotUser, lang: str) -> None:
    await message.answer(t(lang, "choose_language"), reply_markup=kb.languages(lang, "home" if user.onboarded_at else ""))


@router.callback_query(F.data == "choose_lang")
async def ask_language_cb(call: CallbackQuery, user: BotUser, lang: str) -> None:
    await swap_card(call.message, t(lang, "choose_language"), kb.languages(lang, "home" if user.onboarded_at else ""))
    await call.answer()


@router.callback_query(F.data.startswith("lang:"))
async def set_language(call: CallbackQuery, session: AsyncSession, user: BotUser) -> None:
    code = call.data.split(":", 1)[1]
    if code not in LANGUAGE_NAMES:
        await call.answer()
        return
    user.language = code
    await call.answer(t(code, "language_set"))
    if user.onboarded_at is None:  # the first visit goes on: what this bot is
        await swap_card(call.message, t(code, "intro"), kb.intro(code))
    else:
        await show_home(call, session, user, code)


# ---------- The introduction and picking a group ----------

@router.callback_query(F.data == "intro")
async def intro_cb(call: CallbackQuery, lang: str) -> None:
    await swap_card(call.message, t(lang, "intro"), kb.intro(lang))
    await call.answer()


async def show_courses(call: CallbackQuery, session: AsyncSession, lang: str, came_from: str) -> None:
    found = users.courses(await users.selectable_groups(session))
    if not found:
        await swap_card(call.message, t(lang, "no_groups"), kb.intro(lang))
    else:
        await swap_card(call.message, t(lang, "pick_course"), kb.pick_course(lang, came_from, found))
    await call.answer()


@router.callback_query(F.data.startswith("pick:"))
async def pick_course(call: CallbackQuery, session: AsyncSession, lang: str) -> None:
    await show_courses(call, session, lang, call.data.split(":", 1)[1])


@router.callback_query(F.data.in_({"profile", "nogroup"}))
async def old_group_buttons(call: CallbackQuery, session: AsyncSession, user: BotUser, lang: str) -> None:
    """Buttons of cards from before (👤 Profile, ➡️ Go on without a group): picking the group instead."""
    await show_courses(call, session, lang, "home" if user.onboarded_at else "intro")


@router.callback_query(F.data.startswith("pc:"))
async def pick_specialty(call: CallbackQuery, session: AsyncSession, lang: str) -> None:
    _, came_from, course = (call.data.split(":") + ["", ""])[:3]
    course = _int(course) or 0
    found = users.specialties(await users.selectable_groups(session), course, lang)
    await swap_card(call.message, t(lang, "pick_specialty", course=t(lang, "course_n", n=course)),
                    kb.pick_specialty(lang, came_from, course, found))
    await call.answer()


@router.callback_query(F.data.startswith("ps:"))
async def pick_group(call: CallbackQuery, session: AsyncSession, lang: str) -> None:
    _, came_from, course, code = (call.data.split(":", 3) + ["", "", ""])[:4]
    course = _int(course) or 0
    found = users.groups_of(await users.selectable_groups(session), course, code)
    await swap_card(call.message, t(lang, "pick_group", course=t(lang, "course_n", n=course),
                                    specialty=escape(specialty_name(code, lang))),
                    kb.pick_group(lang, came_from, course, found))
    await call.answer()


@router.callback_query(F.data.startswith("pg:"))
async def group_chosen(call: CallbackQuery, session: AsyncSession, user: BotUser, lang: str) -> None:
    gid = _int(call.data.split(":", 1)[1])
    group = next((g for g in await users.selectable_groups(session) if g.id == gid), None)
    if group is None:  # an old button: the group is gone or has no teachers now
        await show_courses(call, session, lang, "home")
        return
    user.group_id = group.id
    user.onboarded_at = user.onboarded_at or datetime.now(timezone.utc)
    await session.flush()
    await session.refresh(user, ["group"])
    await call.answer(t(lang, "group_set", group=group_name(group, lang)))
    await show_home(call, session, user, lang)
