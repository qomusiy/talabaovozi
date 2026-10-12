"""Messages to the bot's users, written in the dashboard (Bot page) and sent in the background.

Who gets it: everyone, or - by the group they picked in the bot - chosen courses / groups / kafedras (groups taught by
that kafedra's teachers this semester) / specialties; and, while a survey is open, only those who haven't finished it
(or only those who have). Blocked and suspended users get nothing.
A message can carry a photo, a video or a file; it is uploaded to Telegram once and then reused.
"""
import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramRetryAfter
from aiogram.types import FSInputFile, InlineKeyboardMarkup
from sqlalchemy import and_, distinct, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot import chatlog
from app.bot import keyboards as kb
from app.db import session_scope
from app.models import Broadcast, BotUser, Feedback, Group, Semester, Teacher, TeachingAssignment
from app.runtime import MEDIA_DIR, webapp_url
from app.services.survey import active_campaign

log = logging.getLogger("broadcast")
AUDIENCES = ("all", "course", "group", "department", "specialty", "unfinished")  # "unfinished": reminders
SURVEY_FILTERS = ("", "unfinished", "finished")
BROADCAST_MEDIA = MEDIA_DIR / "broadcasts"
CAPTION_LIMIT = 1024  # longer texts go as a second message after the photo/video
PER_SECOND = 20  # Telegram allows ~30 messages/second; stay well below
_running: set[asyncio.Task] = set()


def _ints(values: list[str]) -> list[int]:
    return [int(v) for v in values if str(v).isdigit()]


async def recipients(session: AsyncSession, audience: str, values: list[str] | str | None = None,
                     survey: str = "") -> list[tuple[int, str]]:
    """(telegram id, language) of the users in the audience.

    survey="unfinished": only users who haven't finished the survey that is open now - rated all their group's
    teachers, or (no group picked) anyone at all; "finished": only those who have. (audience "unfinished" = everyone
    who hasn't finished.)
    """
    values = [values] if isinstance(values, str) else [str(v) for v in values or [] if str(v).strip()]
    if audience == "unfinished":
        audience, survey = "all", "unfinished"
    if audience not in AUDIENCES or (audience != "all" and not values):
        return []
    now = datetime.now(timezone.utc)
    q = select(BotUser.id, BotUser.language).where(
        BotUser.id > 0, BotUser.onboarded_at.is_not(None), BotUser.blocked.is_(False),
        or_(BotUser.suspended_until.is_(None), BotUser.suspended_until < now))
    if audience == "course":
        q = q.join(Group, Group.id == BotUser.group_id).where(Group.course.in_(_ints(values)))
    elif audience == "group":
        q = q.where(BotUser.group_id.in_(_ints(values)))
    elif audience == "specialty":
        q = q.join(Group, Group.id == BotUser.group_id).where(Group.code.in_(values))
    elif audience == "department":
        taught = (select(TeachingAssignment.group_id).join(Teacher, Teacher.id == TeachingAssignment.teacher_id)
                  .join(Semester).where(Semester.is_current, Teacher.department_id.in_(_ints(values))))
        q = q.where(BotUser.group_id.in_(taught))
    if survey in ("unfinished", "finished"):
        campaign = await active_campaign(session)
        if campaign is None:
            return []
        expected = (select(TeachingAssignment.group_id.label("gid"),
                           func.count(distinct(TeachingAssignment.teacher_id)).label("n"))
                    .join(Semester).where(Semester.is_current).group_by(TeachingAssignment.group_id).subquery())
        rated = (select(Feedback.user_id.label("uid"), func.count(distinct(Feedback.teacher_id)).label("n"))
                 .where(Feedback.campaign_id == campaign.id).group_by(Feedback.user_id).subquery())
        q = q.outerjoin(expected, expected.c.gid == BotUser.group_id).outerjoin(rated, rated.c.uid == BotUser.id)
        # With a group: all its teachers rated. Without one there is no list to finish: anyone rated counts.
        done = func.coalesce(rated.c.n, 0) >= func.coalesce(expected.c.n, 1)
        q = q.where(done if survey == "finished" else ~done)
    return [(tid, lang) for tid, lang in (await session.execute(q)).all()]


def start(broadcast_id: int) -> None:
    task = asyncio.create_task(_send(broadcast_id))
    _running.add(task)
    task.add_done_callback(_running.discard)


async def _progress(broadcast_id: int, **values) -> None:
    async with session_scope() as session:
        await session.execute(update(Broadcast).where(Broadcast.id == broadcast_id).values(**values))


def _utf16(text: str) -> int:
    return len(text.encode("utf-16-le")) // 2


async def deliver(bot: Bot, chat_id: int, text: str, markup: InlineKeyboardMarkup | None, media: dict | None) -> None:
    """One message: the text alone, or the photo/video/file with the text under it (as a second message if the
    text is too long for a caption). media = {"kind", "path", "id"}; "id" is filled in after the first upload."""
    if not media:
        await bot.send_message(chat_id, text, reply_markup=markup)
        return
    source = media.get("id") or FSInputFile(media["path"])
    caption = text if text and _utf16(text) <= CAPTION_LIMIT else None
    extra = {"caption": caption, "reply_markup": markup if caption or not text else None}
    if media["kind"] == "photo":
        sent = await bot.send_photo(chat_id, source, **extra)
        media["id"] = media.get("id") or (sent.photo[-1].file_id if sent.photo else None)
    elif media["kind"] == "video":
        sent = await bot.send_video(chat_id, source, supports_streaming=True, **extra)
        media["id"] = media.get("id") or (sent.video.file_id if sent.video else None)
    else:
        sent = await bot.send_document(chat_id, source, **extra)
        media["id"] = media.get("id") or (sent.document.file_id if sent.document else None)
    if text and caption is None:
        await bot.send_message(chat_id, text, reply_markup=markup)


def media_of(b: Broadcast) -> dict | None:
    if not b.media_kind or not b.media_name:
        return None
    path = BROADCAST_MEDIA / b.media_name
    return {"kind": b.media_kind, "path": str(path)} if Path(path).is_file() else None


async def _send(broadcast_id: int) -> None:
    chatlog.origin.set(f"broadcast:{broadcast_id}")
    async with session_scope() as session:
        b = await session.get(Broadcast, broadcast_id)
        filters = b.filters or {}
        people = await recipients(session, b.audience, filters.get("values") or b.audience_value,
                                  filters.get("survey", ""))
        text, with_button, media = b.text, b.survey_button, media_of(b)
        b.status, b.total = "sending", len(people)
    url = webapp_url() if with_button else ""
    bot = chatlog.new_bot()
    sent = failed = 0
    try:
        for i, (chat_id, lang) in enumerate(people, 1):
            markup = kb.open_survey(lang, f"{url}/survey") if url else None
            for _attempt in range(3):
                try:
                    await deliver(bot, chat_id, text, markup, media)
                    sent += 1
                    break
                except TelegramRetryAfter as e:
                    await asyncio.sleep(e.retry_after + 1)
                except TelegramAPIError:  # blocked the bot, deleted account, ...
                    failed += 1
                    break
            if i % 25 == 0:
                await _progress(broadcast_id, sent=sent, failed=failed)
            await asyncio.sleep(1 / PER_SECOND)
    except Exception:
        log.exception("Broadcast %s stopped", broadcast_id)
    finally:
        await bot.session.close()
        await _progress(broadcast_id, sent=sent, failed=failed, status="done",
                        finished_at=datetime.now(timezone.utc))


async def mark_interrupted(session: AsyncSession) -> None:
    """After a restart, broadcasts that were being sent are marked as stopped."""
    await session.execute(update(Broadcast).where(and_(Broadcast.status.in_(("queued", "sending"))))
                          .values(status="stopped", finished_at=datetime.now(timezone.utc)))
