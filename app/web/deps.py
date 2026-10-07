from collections.abc import AsyncIterator

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.db import session_scope
from app.models import Admin, Student
from app.services.students import get_by_telegram
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


async def current_student(
    request: Request,
    session: AsyncSession = Depends(get_session, scope="function"),
    x_telegram_init_data: str | None = Header(default=None),
    x_dev_hemis: str | None = Header(default=None),
) -> Student:
    settings = get_settings()
    if x_telegram_init_data:
        user = verify_init_data(x_telegram_init_data, settings.bot_token)
        if user is None:
            raise HTTPException(401, "invalid_init_data")
        student = await get_by_telegram(session, int(user["id"]))
        if student is None:
            raise HTTPException(403, "not_registered")
        return student
    # Dev shortcut: only on this computer, never through the public tunnel.
    if settings.dev_mode and x_dev_hemis and is_local_request(request):
        student = (await session.execute(
            select(Student).options(selectinload(Student.group)).where(Student.hemis_id == x_dev_hemis)
        )).scalar_one_or_none()
        if student:
            return student
    raise HTTPException(401, "open_in_telegram")


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
