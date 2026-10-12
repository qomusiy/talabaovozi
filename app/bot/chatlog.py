"""Every bot conversation, both ways, for the programmer's "Suhbatlar" page in the dashboard.

Telegram doesn't let a bot read its chat history, so the bot writes it down as it goes:
- what people send (and which button they tapped) - IncomingLog, a dispatcher middleware;
- what the bot sends, edits and deletes - OutgoingLog, on the bot's connection, so every way of sending is
  covered: the bot's answers, messages to users from the dashboard, reminders, the programmer's replies.

An edit changes the stored message, as it changes the message in the chat. Anything that looks like a passport
number is masked (people still send them out of habit). Messages of blocked users are logged too - the programmer
needs to see what they sent.
"""
import logging
import re
from contextvars import ContextVar
from datetime import datetime, timedelta, timezone
from html import escape, unescape

from aiogram import BaseMiddleware, Bot
from aiogram.client.session.middlewares.base import BaseRequestMiddleware
from aiogram.exceptions import TelegramForbiddenError
from aiogram.methods import (AnswerCallbackQuery, DeleteMessage, EditMessageCaption, EditMessageMedia,
                             EditMessageReplyMarkup, EditMessageText, SendAnimation, SendAudio, SendDocument,
                             SendMessage, SendPhoto, SendSticker, SendVideo, SendVideoNote, SendVoice, SetMessageReaction)
from aiogram.types import InlineKeyboardMarkup, Message, Update
from sqlalchemy import delete, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.config import get_settings
from app.db import session_scope
from app.models import BotChat, BotMessage

log = logging.getLogger("chatlog")
origin: ContextVar[str] = ContextVar("chat_origin", default="bot")   # bot / broadcast:12 / reminder / panel / system
actor: ContextVar[int | None] = ContextVar("chat_actor", default=None)  # the dashboard account sending from the panel

PASSPORT = re.compile(r"\b[A-Za-z]{2}\s?\d{7}\b")
SENDS = (SendMessage, SendPhoto, SendVideo, SendDocument, SendAnimation, SendAudio, SendVoice, SendSticker, SendVideoNote)
EDITS = (EditMessageText, EditMessageCaption, EditMessageMedia, EditMessageReplyMarkup)
PREVIEW = {"photo": "📷", "video": "🎬", "document": "📎", "sticker": "", "voice": "🎤", "audio": "🎵",
           "animation": "🎞", "video_note": "📹", "contact": "👤", "location": "📍", "other": "💬"}
_callbacks: dict[str, int] = {}  # callback id -> chat, to file a pop-up answer under the right conversation


def mask(html: str | None) -> str | None:
    return PASSPORT.sub("•• •••••••", html) if html else html


def describe(m: Message) -> tuple[str, str | None, str | None]:
    """(kind, text as Telegram HTML, file id) of a message."""
    file_id = None
    for kind in ("photo", "video", "document", "animation", "audio", "voice", "video_note", "sticker"):
        value = getattr(m, kind, None)
        if value:
            file_id = value[-1].file_id if kind == "photo" else value.file_id
            break
    else:
        kind = "text" if m.text is not None else (
            "contact" if m.contact else "location" if m.location else "other")
    if kind == "sticker":
        return kind, escape(m.sticker.emoji or ""), file_id
    text = m.html_text if (m.text or m.caption) else None
    if kind == "contact":
        text = escape(f"{m.contact.first_name} {m.contact.phone_number}")
    return kind, mask(text), file_id


def buttons_of(markup) -> list | None:
    if not isinstance(markup, InlineKeyboardMarkup):
        return None
    rows = []
    for row in markup.inline_keyboard:
        rows.append([{"t": b.text, "k": "app" if b.web_app else "url" if b.url else "cb",
                      **({"u": b.url} if b.url else {})} for b in row])
    return rows or None


def preview(kind: str, html: str | None) -> str:
    plain = unescape(re.sub(r"<[^>]+>", "", html or "")).replace("\n", " ").strip()
    icon = PREVIEW.get(kind, "")
    return (f"{icon} {plain}" if icon and plain else plain or icon or "…")[:200]


async def _chat(session, chat_id: int, direction: str, text: str, *, name=None, username=None,
                blocked: bool | None = None) -> None:
    now = datetime.now(timezone.utc)
    values = {"chat_id": chat_id, "last_at": now, "last_text": text[:255], "last_dir": direction}
    changes = dict(values)
    for key, value in (("name", name), ("username", username), ("blocked", blocked)):
        if value is not None:
            values[key] = changes[key] = value
    stmt = pg_insert(BotChat).values(**values)
    await session.execute(stmt.on_conflict_do_update(index_elements=["chat_id"],
                                                     set_={k: v for k, v in changes.items() if k != "chat_id"}))


# ---------------------------------------------------------------- incoming

class IncomingLog(BaseMiddleware):
    """Register before ContextMiddleware, so updates it stops (blocked users) are logged too."""

    async def __call__(self, handler, event: Update, data: dict):
        try:
            await record_in(event, data)
        except Exception:  # the conversation log must never stop the bot
            log.exception("Could not log an incoming update")
        return await handler(event, data)


async def record_in(event: Update, data: dict) -> None:
    if event.message and event.message.chat.type == "private":
        m = event.message
        kind, text, file_id = describe(m)
        row = BotMessage(chat_id=m.chat.id, message_id=m.message_id, dir="in", kind=kind, text=text, file_id=file_id)
        user = m.from_user
    elif event.callback_query and event.callback_query.message:
        call = event.callback_query
        _callbacks[call.id] = call.message.chat.id
        if len(_callbacks) > 2000:
            _callbacks.clear()
        label = next((b.text for row in (getattr(call.message.reply_markup, "inline_keyboard", None) or [])
                      for b in row if b.callback_data == call.data), call.data)
        row = BotMessage(chat_id=call.message.chat.id, message_id=call.message.message_id, dir="tap", kind="tap",
                         text=escape(label or ""))
        user = call.from_user
    else:
        return
    name = " ".join(x for x in (user.first_name, user.last_name) if x) if user else None
    async with session_scope() as session:
        session.add(row)
        await _chat(session, row.chat_id, row.dir, preview(row.kind, row.text) if row.dir == "in" else f"👆 {label}",
                    name=name, username=(user.username if user else None) or None, blocked=False)


# ---------------------------------------------------------------- outgoing

class OutgoingLog(BaseRequestMiddleware):
    async def __call__(self, make_request, bot: Bot, method):
        try:
            result = await make_request(bot, method)
        except TelegramForbiddenError:  # the person blocked the bot or deleted their account
            chat_id = getattr(method, "chat_id", None)
            if isinstance(chat_id, int):
                try:
                    async with session_scope() as session:
                        await session.execute(update(BotChat).where(BotChat.chat_id == chat_id).values(blocked=True))
                except Exception:
                    log.exception("Could not mark chat %s as blocked", chat_id)
            raise
        try:
            await record_out(method, result)
        except Exception:
            log.exception("Could not log %s", type(method).__name__)
        return result


async def record_out(method, result) -> None:
    if isinstance(method, SENDS) and isinstance(result, Message):
        if result.chat.type != "private":
            return
        kind, text, file_id = describe(result)
        async with session_scope() as session:
            session.add(BotMessage(chat_id=result.chat.id, message_id=result.message_id, dir="out", kind=kind,
                                   text=text, file_id=file_id, buttons=buttons_of(result.reply_markup),
                                   origin=origin.get(), admin_id=actor.get()))
            await _chat(session, result.chat.id, "out", preview(kind, text), blocked=False)
    elif isinstance(method, EDITS) and isinstance(result, Message):
        kind, text, file_id = describe(result)
        values = {"kind": kind, "text": text, "file_id": file_id, "buttons": buttons_of(result.reply_markup),
                  "edited_at": datetime.now(timezone.utc)}
        async with session_scope() as session:
            done = await session.execute(update(BotMessage).where(
                BotMessage.chat_id == result.chat.id, BotMessage.message_id == result.message_id,
                BotMessage.dir == "out").values(**values))
            if not done.rowcount:  # sent before the log existed
                session.add(BotMessage(chat_id=result.chat.id, message_id=result.message_id, dir="out",
                                       origin=origin.get(), **values))
    elif isinstance(method, DeleteMessage) and isinstance(method.chat_id, int):
        async with session_scope() as session:
            await session.execute(update(BotMessage).where(
                BotMessage.chat_id == method.chat_id, BotMessage.message_id == method.message_id,
                BotMessage.dir != "tap").values(deleted=True))
    elif isinstance(method, SetMessageReaction) and isinstance(method.chat_id, int):
        emoji = next((getattr(r, "emoji", None) for r in method.reaction or []), None)
        async with session_scope() as session:
            await session.execute(update(BotMessage).where(
                BotMessage.chat_id == method.chat_id, BotMessage.message_id == method.message_id,
                BotMessage.dir == "in").values(reaction=emoji))
    elif isinstance(method, AnswerCallbackQuery) and method.text and method.callback_query_id in _callbacks:
        chat_id = _callbacks.pop(method.callback_query_id)
        async with session_scope() as session:
            session.add(BotMessage(chat_id=chat_id, dir="out", kind="alert" if method.show_alert else "toast",
                                   text=escape(method.text), origin=origin.get()))


def new_bot(token: str | None = None, **kwargs) -> Bot:
    """A Bot whose messages go into the conversation log (use this, not Bot(...), anywhere the bot sends)."""
    bot = Bot(token or get_settings().bot_token, **kwargs)
    bot.session.middleware(OutgoingLog())
    return bot


async def prune(session, days: int = 365) -> None:
    await session.execute(delete(BotMessage).where(BotMessage.at < datetime.now(timezone.utc) - timedelta(days=days)))
