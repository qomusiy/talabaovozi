"""Run the Telegram bot:  python -m app.bot"""
import asyncio
import logging
import socket

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramAPIError, TelegramNotFound, TelegramUnauthorizedError
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

from app.bot import chatlog
from app.bot.handlers import admin, menu, start
from app.bot.i18n import BOT_DESCRIPTION, BOT_NAME, BOT_SHORT_DESCRIPTION, DEFAULT_LANG, LANGUAGE_NAMES, t
from app.bot.menu_button import follow_survey_url, published_url
from app.bot.middleware import ContextMiddleware
from app.bot.reactions import ReactionMiddleware
from app.bot.admin_reports import daily_loop
from app.bot.reminders import reminder_loop
from app.bot.server_alerts import alerts_loop
from app.config import get_settings
from app.db import engine
from app.runtime import SERVER_SCRIPT

log = logging.getLogger("bot")
LOCK_PORT = 47802  # held while the bot runs (the server holds 47801)


async def setup_bot_profile(bot: Bot) -> None:
    """Commands in the user's Telegram language; the name and descriptions (BOT_NAME, ...) the same for everyone.
    Telegram allows few renames a day, so each is only sent when it differs from what Telegram shows now."""
    for code in (None, *LANGUAGE_NAMES):
        lang = code or DEFAULT_LANG
        try:
            await bot.set_my_commands([
                BotCommand(command="start", description=t(lang, "cmd_start")),
                BotCommand(command="menu", description=t(lang, "cmd_start")),
                BotCommand(command="timetable", description=t(lang, "tt_title")),
                BotCommand(command="language", description=t(lang, "cmd_language")),
                BotCommand(command="help", description=t(lang, "cmd_help")),
            ], language_code=code)
        except TelegramAPIError as e:  # e.g. rate limit; not critical
            log.warning("Could not set the bot's commands for %s: %s", code, e)
    profile = (
        ("name", bot.get_my_name, bot.set_my_name, BOT_NAME),
        ("description", bot.get_my_description, bot.set_my_description, BOT_DESCRIPTION),
        ("short_description", bot.get_my_short_description, bot.set_my_short_description, BOT_SHORT_DESCRIPTION),
    )
    for field, get, put, text in profile:
        for code in (None, *LANGUAGE_NAMES):  # the default for everyone; a language's own text (from before) goes
            try:
                now = getattr(await get(language_code=code), field)
                if code is None and now != text:
                    await put(text, language_code=None)
                elif code is not None and now not in ("", text):
                    await put("", language_code=code)
            except TelegramAPIError as e:
                log.warning("Could not set the bot's %s for %s: %s", field, code, e)


def single_instance_lock() -> socket.socket:
    """Refuse to start if another copy of the bot is already running (they would steal each other's updates).
    The port stays taken while this process lives - also when it crashes, the lock goes with it."""
    lock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        lock.bind(("127.0.0.1", LOCK_PORT))
    except OSError:
        raise SystemExit(f"❌ The bot is already running on this computer ({SERVER_SCRIPT} status). Stop it first.")
    return lock


async def main() -> None:
    lock = single_instance_lock()  # noqa: F841 - held until the bot stops
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)  # the site checks of app.bot.server_alerts, every few seconds
    token = get_settings().bot_token
    if not token:
        raise SystemExit("❌ BOT_TOKEN is missing in .env")

    bot = chatlog.new_bot(token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    dp.update.outer_middleware(chatlog.IncomingLog())  # first: updates of blocked users are logged too
    dp.update.outer_middleware(ContextMiddleware())
    dp.message.middleware(ReactionMiddleware())
    dp.include_routers(admin.router, start.router, menu.router)

    try:
        me = await bot.get_me()
    except (TelegramUnauthorizedError, TelegramNotFound):
        await bot.session.close()
        raise SystemExit("❌ Telegram rejected BOT_TOKEN. Check the BOT_TOKEN line in .env "
                         "(it must look like 123456789:AAH..., on its own line).")
    log.info("Starting @%s", me.username)
    await setup_bot_profile(bot)
    follower = asyncio.create_task(follow_survey_url(bot, published=await published_url(bot), username=me.username))
    reminders = asyncio.create_task(reminder_loop(bot))
    reports = asyncio.create_task(daily_loop(bot))
    alerts = asyncio.create_task(alerts_loop(bot))
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        for task in (follower, reminders, reports, alerts):
            task.cancel()
        await bot.session.close()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
