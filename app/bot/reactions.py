"""The bot reacts to people's messages with an emoji, the way a person would: 🔥 on /start, 👀 on a HEMIS number,
❤ on a thank-you. Switched off with "Xabarlarga emoji" on the dashboard's Telegram bot page."""
import random
import re
from contextlib import suppress

from aiogram import BaseMiddleware
from aiogram.exceptions import TelegramAPIError
from aiogram.types import Message, ReactionTypeEmoji

from app import settings_store

# Only emoji from Telegram's list of standard reactions can be used.
START = ("🔥", "❤", "🤩", "⚡", "🎉", "🫡")
COMMANDS = {"help": "🤓", "language": "👌", "myid": "👀", "timetable": "✍"}
THANKS = re.compile(r"(rahmat|raxmat|rahmet|tashakkur|спасибо|благодар|thank|sag bol)", re.I)
HELLO = re.compile(r"\b(salom|assalom\w*|salam|привет|здравств\w*|hello|hi|hey)\b", re.I)


def pick(message: Message, raw_state: str | None) -> str | None:
    if raw_state == "Login:passport":  # that message is deleted at once
        return None
    if raw_state == "Login:hemis":
        return "👀"
    text = message.text or message.caption or ""
    if text.startswith("/"):
        command = text[1:].split(maxsplit=1)[0].split("@")[0].lower() if len(text) > 1 else ""
        return random.choice(START) if command in ("start", "menu") else COMMANDS.get(command)
    if message.sticker or message.photo or message.video or message.animation:
        return random.choice(("🔥", "😁", "🤩"))
    if THANKS.search(text):
        return "❤"
    if HELLO.search(text):
        return "🤗"
    return "👀" if text or message.voice or message.video_note else None


class ReactionMiddleware(BaseMiddleware):
    """dp.message middleware: the answer goes first, then the reaction."""

    async def __call__(self, handler, event: Message, data: dict):
        emoji = pick(event, data.get("raw_state")) if event.chat.type == "private" else None
        result = await handler(event, data)
        if emoji and (await settings_store.load(data["session"]))["bot_reactions"]:
            with suppress(TelegramAPIError):
                await data["bot"].set_message_reaction(event.chat.id, event.message_id,
                                                       reaction=[ReactionTypeEmoji(emoji=emoji)])
        return result
