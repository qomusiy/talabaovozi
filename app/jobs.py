"""Background work of the web server: keeps the timetable (and everything built from it) up to date."""
import asyncio
import logging
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app import audit, settings_store
from app.bot import chatlog
from app.db import session_scope
from app.runtime import ROOT
from app.services import broadcast
from app.services.broadcast import BROADCAST_MEDIA
from app.services.teaching import refresh_from_edupage

log = logging.getLogger("jobs")
CHECK_EVERY = 300  # seconds between "is a timetable check due?" checks
CHAT_FILES = ROOT / "data" / "runtime" / "chatfiles"  # app.web.admin.chats.FILES


def _due(values: dict) -> bool:
    if not values["timetable_auto_sync"]:
        return False
    try:
        last = datetime.fromisoformat(values["timetable_checked_at"])
    except (TypeError, ValueError):
        return True
    return datetime.now(timezone.utc) - last >= timedelta(hours=max(1, int(values["timetable_sync_hours"])))


async def timetable_loop() -> None:
    """Every few hours, download the timetable from EduPage. If it changed, the new one is stored and
    teachers, groups and (unless they come from Excel) teaching assignments are updated from it."""
    while True:
        try:
            async with session_scope() as session:
                if _due(await settings_store.load(session, fresh=True)):
                    changed, error = await refresh_from_edupage(session, admin="system")
                    if error:
                        log.warning("Timetable check failed: %s", error)  # saved; shown on the Data page
                    else:
                        log.info("Timetable checked: %s", "changed, updated" if changed else "no changes")
        except Exception:
            log.exception("Timetable check failed")
        await asyncio.sleep(CHECK_EVERY)


FILES_KEEP_DAYS = 30


def remove_old_files(folder: Path, days: int = FILES_KEEP_DAYS) -> int:
    """Photos/videos of sent messages and pictures fetched for the Conversations page: kept for a month."""
    if not folder.is_dir():
        return 0
    cutoff, removed = time.time() - days * 86400, 0
    for f in folder.iterdir():
        if f.is_file() and f.stat().st_mtime < cutoff:
            f.unlink(missing_ok=True)
            removed += 1
    return removed


async def housekeeping_loop() -> None:
    """Once a day: drop activity-log entries and bot conversations older than a year, and old uploaded files."""
    while True:
        try:
            async with session_scope() as session:
                await audit.prune(session)
                await chatlog.prune(session)
            for folder in (BROADCAST_MEDIA, CHAT_FILES):
                remove_old_files(folder)
        except Exception:
            log.exception("Housekeeping failed")
        await asyncio.sleep(24 * 3600)


_tasks: list[asyncio.Task] = []


async def start() -> None:
    async with session_scope() as session:
        await broadcast.mark_interrupted(session)
    _tasks.append(asyncio.create_task(timetable_loop()))
    _tasks.append(asyncio.create_task(housekeeping_loop()))


async def stop() -> None:
    for task in _tasks:
        task.cancel()
    _tasks.clear()
