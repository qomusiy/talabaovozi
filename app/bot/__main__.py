"""Run the Telegram bot:  python -m app.bot"""
import asyncio
import logging
import os
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramAPIError, TelegramNotFound, TelegramUnauthorizedError
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

from app.bot import chatlog
from app.bot.handlers import admin, auth, menu
from app.bot.i18n import DEFAULT_LANG, LANGUAGE_NAMES, t
from app.bot.menu_button import follow_survey_url, published_url
from app.bot.middleware import ContextMiddleware
from app.bot.reactions import ReactionMiddleware
from app.bot.admin_reports import daily_loop
from app.bot.reminders import reminder_loop
from app.config import get_settings
from app.db import engine
from app.runtime import WEBAPP_URL_FILE

log = logging.getLogger("bot")


async def setup_bot_profile(bot: Bot) -> None:
    """Commands and descriptions shown in Telegram, localised by the user's Telegram language."""
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
            await bot.set_my_description(t(lang, "bot_description"), language_code=code)
            await bot.set_my_short_description(t(lang, "bot_short_description"), language_code=code)
        except TelegramAPIError as e:  # e.g. rate limit; not critical
            log.warning("Could not set bot profile for %s: %s", code, e)


def single_instance_lock() -> None:
    """Refuse to start if another copy of the bot is already running (they would steal each other's updates)."""
    lock = WEBAPP_URL_FILE.parent / "bot.pid"
    lock.parent.mkdir(parents=True, exist_ok=True)
    try:
        other = int(lock.read_text())
        cmdline = Path(f"/proc/{other}/cmdline").read_bytes()  # still alive, and really our bot?
        if other != os.getpid() and b"app.bot" in cmdline:
            raise SystemExit(f"❌ The bot is already running (pid {other}). Stop it first, or use scripts/dev.sh.")
    except (OSError, ValueError):
        pass  # no lock, or the old process is gone
    lock.write_text(str(os.getpid()))


async def main() -> None:
    single_instance_lock()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    token = get_settings().bot_token
    if not token:
        raise SystemExit("❌ BOT_TOKEN is missing in .env")

    bot = chatlog.new_bot(token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    dp.update.outer_middleware(ContextMiddleware())
    dp.update.outer_middleware(chatlog.IncomingLog())  # after ContextMiddleware: it uses the student found there
    dp.message.middleware(ReactionMiddleware())
    dp.include_routers(admin.router, auth.router, menu.router)

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
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        follower.cancel()
        reminders.cancel()
        reports.cancel()
        await bot.session.close()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
