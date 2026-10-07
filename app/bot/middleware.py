from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User

from app.bot.i18n import DEFAULT_LANG
from app.db import session_scope
from app.services import admin_link
from app.services.students import get_by_telegram


class ContextMiddleware(BaseMiddleware):
    """Gives every handler a DB `session`, the logged-in `student` (or None), the linked dashboard account `admin`
    (or None; `admin_linked_now` when its @username was recognised just now) and the UI `lang`."""

    async def __call__(self, handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
                       event: TelegramObject, data: dict[str, Any]) -> Any:
        user: User | None = data.get("event_from_user")
        async with session_scope() as session:
            student = await get_by_telegram(session, user.id) if user else None
            if student:
                lang = student.language
            else:
                # Not logged in yet: language chosen during login lives in the FSM state.
                state = data.get("state")
                lang = (await state.get_data()).get("lang", DEFAULT_LANG) if state else DEFAULT_LANG
            admin, linked_now = await admin_link.by_telegram(session, user)
            data.update(session=session, student=student, lang=lang, admin=admin, admin_linked_now=linked_now)
            return await handler(event, data)
