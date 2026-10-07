"""Which dashboard account a Telegram user is - for the bot's admin menu.

Two ways to link an account to Telegram (both end with the account's Telegram ID saved):
- a one-time link from "Mening hisobim" (t.me/<bot>?start=adm_<token>, valid 15 minutes) - one tap, safest;
- the @username an admin types in (their own on "Mening hisobim", or a superadmin for them on "Adminlar"):
  the first time that Telegram user writes to the bot, the ID is saved.
After that the bot knows the person by the ID alone, so changing the Telegram username changes nothing.
"""
import secrets
from datetime import datetime, timedelta, timezone

from aiogram.types import User
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Admin

TOKEN_TTL = timedelta(minutes=15)
TOKEN_PREFIX = "adm_"


def clean_username(value: str | None) -> str | None:
    """'@Ali_Valiyev ', 't.me/ali_valiyev' -> 'ali_valiyev'; None if it can't be a Telegram username."""
    v = (value or "").strip().removeprefix("https://").removeprefix("t.me/").removeprefix("@").strip().lower()
    if not v:
        return None
    return v if 5 <= len(v) <= 32 and v.replace("_", "").isalnum() and v.isascii() else None


def new_token(admin: Admin) -> str:
    admin.tg_link_token = secrets.token_urlsafe(12)
    admin.tg_link_until = datetime.now(timezone.utc) + TOKEN_TTL
    return admin.tg_link_token


def _who(user: User) -> str:
    return " ".join(x for x in (user.first_name, user.last_name) if x)[:128]


async def bind(session: AsyncSession, admin: Admin, user: User) -> None:
    # One Telegram account belongs to one dashboard account: take it from any other first.
    await session.execute(update(Admin).where(Admin.telegram_id == user.id, Admin.id != admin.id)
                          .values(telegram_id=None))
    await session.flush()
    admin.telegram_id = user.id
    admin.telegram_username = (user.username or admin.telegram_username or "").lower() or None
    admin.telegram_name = _who(user)
    admin.tg_link_token = admin.tg_link_until = None


async def by_telegram(session: AsyncSession, user: User | None) -> tuple[Admin | None, bool]:
    """(the account of this Telegram user or None, linked just now?)."""
    if user is None:
        return None, False
    admin = await session.scalar(select(Admin).where(Admin.telegram_id == user.id))
    if admin is not None:
        if not admin.is_active:
            return None, False
        name, username = _who(user), (user.username or "").lower() or None
        if (admin.telegram_name, admin.telegram_username) != (name, username):  # keep what the dashboard shows fresh
            admin.telegram_name, admin.telegram_username = name, username
        return admin, False
    if user.username:  # the first time: the @username an admin entered
        admin = await session.scalar(select(Admin).where(
            func.lower(Admin.telegram_username) == user.username.lower(), Admin.telegram_id.is_(None), Admin.is_active))
        if admin is not None:
            await bind(session, admin, user)
            return admin, True
    return None, False


async def by_token(session: AsyncSession, token: str, user: User) -> Admin | None:
    """The one-time link: links the account if the token is valid."""
    admin = await session.scalar(select(Admin).where(Admin.tg_link_token == token, Admin.is_active))
    if admin is None or admin.tg_link_until is None or admin.tg_link_until < datetime.now(timezone.utc):
        return None
    await bind(session, admin, user)
    return admin


def unlink(admin: Admin) -> None:
    """Forget the Telegram account (the username too - otherwise the next message would link it again)."""
    admin.telegram_id = admin.telegram_username = admin.telegram_name = None
    admin.tg_link_token = admin.tg_link_until = None
