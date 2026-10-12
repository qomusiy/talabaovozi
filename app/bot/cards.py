"""The bot's cards: one message with the menu picture on top, a caption and buttons under it.

Tapping a button swaps the card: the next one is sent at the bottom of the chat while the tapped one is deleted,
both at the same time, so the chat always ends with a single fresh card (no caption changing in place).

The picture is uploaded once; after that Telegram's id for it is reused, so a new card appears at once. A text that
is too long for a photo caption (1024 characters) is sent as an ordinary message instead.
"""
import asyncio
import logging
import re
import time
from contextlib import suppress
from html import unescape

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.types import FSInputFile, InlineKeyboardMarkup, Message

from app.runtime import menu_photo

log = logging.getLogger("bot")
CAPTION_LIMIT = 1024
_photo: dict = {"key": None, "id": None}
# (chat, tapped card) -> (when, the new card being sent): a second quick tap on the same card gets that same card.
_swaps: dict[tuple[int, int], tuple[float, asyncio.Future]] = {}
DOUBLE_TAP = 10  # seconds


def visible_length(html: str) -> int:
    """Length as Telegram counts it: without the HTML tags, in UTF-16 units (an emoji counts as 2)."""
    return len(unescape(re.sub(r"<[^>]+>", "", html)).encode("utf-16-le")) // 2


def fits_caption(text: str) -> bool:
    return visible_length(text) <= CAPTION_LIMIT


def _photo_input():
    path = menu_photo()
    if path is None:
        return None, None
    st = path.stat()
    key = (str(path), st.st_mtime_ns, st.st_size)
    return key, (_photo["id"] if _photo["key"] == key and _photo["id"] else FSInputFile(path))


async def send_card(bot: Bot, chat_id: int, text: str, markup: InlineKeyboardMarkup | None) -> Message:
    key, photo = _photo_input()
    if photo is not None and fits_caption(text):
        try:
            sent = await bot.send_photo(chat_id, photo, caption=text, reply_markup=markup)
            if sent.photo:
                _photo.update(key=key, id=sent.photo[-1].file_id)
            return sent
        except TelegramBadRequest as e:  # a stale picture id, a broken file: the card still goes, as text
            log.warning("Menu picture not sent: %s", e)
            _photo.update(key=None, id=None)
    return await bot.send_message(chat_id, text, reply_markup=markup)


async def remove_card(bot: Bot, chat_id: int, message_id: int) -> None:
    """Delete a card; one Telegram no longer lets the bot delete (older than 48 hours) just loses its buttons."""
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
    except TelegramAPIError:
        with suppress(TelegramAPIError):
            await bot.edit_message_reply_markup(chat_id=chat_id, message_id=message_id)


async def swap_card(message: Message, text: str, markup: InlineKeyboardMarkup | None) -> Message:
    """Show `text` in place of the card that was tapped: the new card is sent while the old one is deleted.
    Returns the new card."""
    key, now = (message.chat.id, message.message_id), time.monotonic()
    for old in [k for k, (at, _) in _swaps.items() if now - at > DOUBLE_TAP]:
        del _swaps[old]
    if key in _swaps:  # tapped twice: the first tap already brings the new card
        return await _swaps[key][1]
    sending = asyncio.ensure_future(send_card(message.bot, message.chat.id, text, markup))
    _swaps[key] = (now, sending)
    await remove_card(message.bot, message.chat.id, message.message_id)
    try:
        return await sending
    except Exception:
        _swaps.pop(key, None)
        raise
