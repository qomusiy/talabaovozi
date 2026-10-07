"""/start, language selection and the HEMIS + passport login flow."""
import re

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app import settings_store
from app.bot import keyboards as kb
from app.bot.cards import edit_card, send_card
from app.bot.handlers.menu import drop_reply_keyboard, send_home, show_home, welcome_card
from app.bot.i18n import DEFAULT_LANG, LANGUAGE_NAMES, all_variants, t
from app.models import Admin, Student
from app.services import admin_link
from app.security import is_valid_passport, normalize_hemis, normalize_passport
from app.services.students import AlreadyLinkedError, authenticate, link_telegram

router = Router(name="auth")


class Login(StatesGroup):
    hemis = State()
    passport = State()


async def reset_state(state: FSMContext) -> None:
    """Leave the login flow but remember the language picked before login."""
    lang = (await state.get_data()).get("lang", DEFAULT_LANG)
    await state.clear()
    await state.update_data(lang=lang)


async def show_welcome(message: Message, session: AsyncSession, lang: str) -> None:
    await send_card(message.bot, message.chat.id, *await welcome_card(session, lang))


@router.message(CommandStart())
@router.message(Command("menu"))
async def cmd_start(message: Message, state: FSMContext, session: AsyncSession, student: Student | None,
                    lang: str, command: CommandObject | None = None, admin: Admin | None = None,
                    admin_linked_now: bool = False) -> None:
    from app.bot.handlers import admin as admin_menu  # (imports this module's neighbours)
    await reset_state(state)
    await drop_reply_keyboard(message)  # the old always-open menu, if this phone still shows it
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
        await admin_menu.send_admin_home(message, session, admin, lang, student)
        return
    if student:
        await send_home(message, session, student, lang)
    else:
        await show_welcome(message, session, lang)


@router.message(Command("myid"))
async def my_id(message: Message, lang: str) -> None:
    """Admins send this to get the number to enter in the dashboard (Bot page) for notifications."""
    await message.answer(t(lang, "my_id", id=message.from_user.id))


async def login_closed(message: Message, session: AsyncSession, lang: str) -> bool:
    """True (and tells the user) if admins closed logging in from the dashboard."""
    values = await settings_store.load(session)
    if values["login_open"]:
        return False
    await message.answer(t(lang, "login_closed", support=settings_store.contacts(values)[0]))
    return True


# ---------- Language ----------

@router.message(Command("language"))
@router.message(F.text.in_(all_variants("btn_language")))
async def ask_language(message: Message, student: Student | None, lang: str) -> None:
    if message.text and not message.text.startswith("/"):
        await drop_reply_keyboard(message)
    await message.answer(t(lang, "choose_language"), reply_markup=kb.languages(back_to_home=bool(student), lang=lang))


@router.callback_query(F.data == "choose_lang")
async def ask_language_cb(call: CallbackQuery, student: Student | None, lang: str) -> None:
    await edit_card(call.message, t(lang, "choose_language"),
                    kb.languages(lang=lang, back_to="home" if student else "welcome"))
    await call.answer()


@router.callback_query(F.data.startswith("lang:"))
async def set_language(call: CallbackQuery, state: FSMContext, session: AsyncSession, student: Student | None) -> None:
    code = call.data.split(":", 1)[1]
    if code not in LANGUAGE_NAMES:
        await call.answer()
        return
    await state.update_data(lang=code)
    if student:  # straight back to the home card, now in the new language
        student.language = code
        await call.answer(t(code, "language_set"))
        await show_home(call, session, student, code)
        return
    await call.answer(t(code, "language_set"))
    if await state.get_state() is None:  # the welcome card again, in the new language
        await edit_card(call.message, *await welcome_card(session, code))
    else:  # in the middle of logging in: carry on in the new language
        await edit_card(call.message, t(code, "language_set"), None)


# ---------- Login ----------

@router.callback_query(F.data == "login")
async def start_login(call: CallbackQuery, state: FSMContext, session: AsyncSession, student: Student | None,
                      lang: str) -> None:
    await call.answer()
    if student:
        await send_home(call.message, session, student, lang)
        return
    if await login_closed(call.message, session, lang):
        return
    await state.set_state(Login.hemis)
    await call.message.answer(t(lang, "ask_hemis"), reply_markup=kb.cancel(lang))


@router.callback_query(F.data == "cancel")
async def cancel_login(call: CallbackQuery, state: FSMContext, lang: str) -> None:
    await reset_state(state)
    await edit_card(call.message, t(lang, "cancelled"), None)
    await call.answer()


@router.message(Login.hemis, F.text)
async def got_hemis(message: Message, state: FSMContext, lang: str) -> None:
    hemis = normalize_hemis(message.text)
    if not re.fullmatch(r"\d{5,20}", hemis):
        await message.answer(t(lang, "bad_hemis"), reply_markup=kb.cancel(lang))
        return
    await state.update_data(hemis=hemis)
    await state.set_state(Login.passport)
    await message.answer(t(lang, "ask_passport"), reply_markup=kb.cancel(lang))


@router.message(Login.passport, F.text)
async def got_passport(message: Message, state: FSMContext, session: AsyncSession, lang: str) -> None:
    passport = normalize_passport(message.text)
    try:
        await message.delete()  # don't leave the passport number in the chat history
    except TelegramBadRequest:
        pass
    if not is_valid_passport(passport):
        await message.answer(t(lang, "bad_passport"), reply_markup=kb.cancel(lang))
        return

    hemis = (await state.get_data()).get("hemis", "")
    support = settings_store.contacts(await settings_store.load(session))[0]
    if await login_closed(message, session, lang):
        await reset_state(state)
        return
    student = await authenticate(session, hemis, passport)
    await reset_state(state)
    if student is None:
        await message.answer(t(lang, "login_failed", support=support), reply_markup=kb.retry(lang))
        return
    try:
        await link_telegram(session, student, message.from_user.id, lang)
    except AlreadyLinkedError:
        await message.answer(t(lang, "linked_elsewhere", support=support))
        return
    await message.answer(
        t(lang, "login_success", name=student.full_name, group=student.group.name if student.group else "—"))
    await send_home(message, session, student, lang)


@router.message(Login.hemis)
@router.message(Login.passport)
async def login_non_text(message: Message, lang: str) -> None:
    await message.answer(t(lang, "unknown"), reply_markup=kb.cancel(lang))
