"""The bot's cards: one message with the menu picture on top, a caption and buttons under it. Tapping a button
changes the caption and buttons of that same message (like a small app), so the chat stays short.

The picture is uploaded once; after that Telegram's id for it is reused. A text that is too long for a photo
caption (1024 characters) is sent as an ordinary message instead.
"""
import logging
import re
from html import unescape

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.types import FSInputFile, InlineKeyboardMarkup, Message

from app.runtime import menu_photo

log = logging.getLogger("bot")
CAPTION_LIMIT = 1024
_photo: dict = {"key": None, "id": None}


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


async def edit_card(message: Message, text: str, markup: InlineKeyboardMarkup | None) -> Message:
    """Show `text` in the card that was tapped; returns the message that now shows it (a new one if needed)."""
    try:
        if message.photo:
            if not fits_caption(text):
                raise ValueError("too long for a caption")
            await message.edit_caption(caption=text, reply_markup=markup)
        else:
            await message.edit_text(text, reply_markup=markup)
        return message
    except TelegramBadRequest as e:
        if "not modified" in str(e):  # tapped twice
            return message
    except (ValueError, TelegramAPIError):
        pass
    return await send_card(message.bot, message.chat.id, text, markup)
