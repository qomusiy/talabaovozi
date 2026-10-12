from collections.abc import AsyncIterator

from datetime import datetime, timezone

from aiogram.types import User
from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import session_scope
from app.models import Admin, BotUser
from app.services import users
from app.web.telegram_auth import verify_init_data


LOCAL_HOSTS = ("127.0.0.1", "localhost", "test")
PROXY_HEADERS = ("cf-connecting-ip", "cf-ray", "x-forwarded-for", "x-real-ip")


def is_local_request(request: Request) -> bool:
    """True only for requests made directly on this computer - not through a tunnel or proxy."""
    host = request.headers.get("host", "").split(":")[0]
    return host in LOCAL_HOSTS and not any(h in request.headers for h in PROXY_HEADERS)


async def get_session() -> AsyncIterator[AsyncSession]:
    """One DB session per request, committed when the endpoint returns - before the response is sent
    (every use is Depends(get_session, scope="function")), so a redirect never shows stale data and a
    failed commit is an error, not a false "saved"."""
    async with session_scope() as session:
        yield session


async def current_user(
    request: Request,
    session: AsyncSession = Depends(get_session, scope="function"),
    x_telegram_init_data: str | None = Header(default=None),
    x_dev_user: str | None = Header(default=None),
) -> BotUser:
    """The bot account of whoever opened the survey - Telegram signs who that is (initData). Someone who opens it
    without having started the bot gets an account too (no group yet). Blocked / suspended accounts: 403."""
    settings = get_settings()
    if x_telegram_init_data:
        tg = verify_init_data(x_telegram_init_data, settings.bot_token)
        try:
            account = User.model_validate({"first_name": "", **(tg or {}), "is_bot": False})
        except ValueError:  # signed, but not a user we understand
            account = None
        if account is None or account.id <= 0:
            raise HTTPException(401, "invalid_init_data")
        user = await users.seen(session, account, count=False, extra={"webapp_user": tg})
    elif settings.dev_mode and (x_dev_user or "").isdigit() and is_local_request(request):
        # Dev shortcut: only on this computer, never through the public tunnel.
        user = await users.seen(session, User(id=int(x_dev_user), is_bot=False, first_name="Dev"), count=False)
        user.onboarded_at = user.onboarded_at or datetime.now(timezone.utc)
    else:
        raise HTTPException(401, "open_in_telegram")
    if kind := users.restriction(user):
        raise HTTPException(403, kind)
    return user


class LoginRequired(Exception):
    pass


async def current_admin(request: Request, session: AsyncSession = Depends(get_session, scope="function")) -> Admin:
    admin_id = request.session.get("admin_id")
    admin = await session.get(Admin, admin_id) if admin_id else None
    if admin is None or not admin.is_active:
        raise LoginRequired
    return admin


async def superadmin(admin: Admin = Depends(current_admin)) -> Admin:
    """Management pages (data, surveys, bot, admins) are for superadmins; viewers only see the analytics."""
    if not admin.is_super:
        raise HTTPException(403, "Only superadmins can do this")
    return admin


async def programmer(admin: Admin = Depends(current_admin)) -> Admin:
    """The activity log, the data structure and changing ratings: programmer accounts only. Others get "not
    found", so the pages don't give away that such accounts exist."""
    if not admin.is_programmer:
        raise HTTPException(404)
    return admin
