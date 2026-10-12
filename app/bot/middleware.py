import logging
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

from aiogram import BaseMiddleware
from aiogram.exceptions import TelegramAPIError
from aiogram.types import TelegramObject, Update, User

from app import settings_store
from app.bot.i18n import t
from app.db import session_scope
from app.services import admin_link, users

log = logging.getLogger("bot")
TASHKENT = ZoneInfo("Asia/Tashkent")


class ContextMiddleware(BaseMiddleware):
    """Gives every handler a DB `session`, the person's `user` account (app.services.users: created the first time,
    refreshed with what Telegram tells), the linked dashboard account `admin` (or None; `admin_linked_now` when its
    @username was recognised just now) and the UI `lang`.

    A blocked or suspended user - by a programmer, or by the flood guard - gets one short answer and nothing else.
    Dashboard accounts are never stopped."""

    async def __call__(self, handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
                       event: TelegramObject, data: dict[str, Any]) -> Any:
        tg: User | None = data.get("event_from_user")
        async with session_scope() as session:
            user = await users.seen(session, tg) if tg and not tg.is_bot else None
            admin, linked_now = await admin_link.by_telegram(session, tg)
            lang = user.language if user else "uz"
            if user is not None and admin is None:
                if users.restriction(user) is None and users.flooding(user.id):
                    users.stop_flood(user)
                    _first_of_many(user.id)  # this message says it; the next answer comes an hour later at most
                    log.warning("Flood guard: %s (%s) paused for %s", user.id, user.name, users.FLOOD_PAUSE)
                    await _tell(data, event, t(lang, "flood_stopped"))
                    return None
                if kind := users.restriction(user):
                    text = None
                    if _first_of_many(user.id):  # say why once in a while, not on every message
                        support = settings_store.contacts(await settings_store.load(session))[0]
                        until = user.suspended_until.astimezone(TASHKENT).strftime("%d.%m.%Y %H:%M") \
                            if user.suspended_until else ""
                        text = t(lang, f"restricted_{kind}", support=support, until=until)
                    await _tell(data, event, text)
                    return None
            data.update(session=session, user=user, lang=lang, admin=admin, admin_linked_now=linked_now)
            return await handler(event, data)


_told: dict[int, float] = {}


def _first_of_many(user_id: int, every: float = 3600.0) -> bool:
    """True at most once an hour per person, so a stopped user isn't answered on every message."""
    now = datetime.now(timezone.utc).timestamp()
    if now - _told.get(user_id, 0) < every:
        return False
    _told[user_id] = now
    if len(_told) > 5000:
        _told.clear()
    return True


async def _tell(data: dict, event: TelegramObject, text: str | None) -> None:
    """Answer a stopped update: `text` if there is one; a button tap is always answered (or it keeps spinning)."""
    bot = data.get("bot")
    update = event if isinstance(event, Update) else None
    try:
        if update and update.callback_query:
            await update.callback_query.answer((text or "")[:190], show_alert=bool(text))
        elif update and update.message and bot and text:
            await bot.send_message(update.message.chat.id, text)
    except TelegramAPIError:
        pass
