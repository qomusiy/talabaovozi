"""Suhbatlar (programmer only): the bot's conversations, shown like Telegram shows them to the bot's owner -
the people on the left, the chosen conversation on the right (the bot's messages on the right side, with their
buttons), and a box to write to that person as the bot. The conversations come from app.bot.chatlog."""
import hashlib
import re
from datetime import datetime
from html import escape

from aiogram.exceptions import TelegramAPIError, TelegramForbiddenError
from aiogram.types import BufferedInputFile
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, Response
from markupsafe import Markup
from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot import chatlog
from app.bot.pictures import BadImage, normalize_photo
from app.models import Admin, BotChat, BotMessage, BotUser, Group
from app.runtime import ROOT
from app.web.admin.views import TASHKENT, get_lang, group_namer, render, resolve_campaign
from app.web.admin.i18n import translator
from app.web.deps import get_session, programmer
from app.web.templating import templates

router = APIRouter(prefix="/admin")
SHOWN = 300           # newest messages of a conversation on the page
LISTED = 300          # conversations in the list
FILES = ROOT / "data" / "runtime" / "chatfiles"   # pictures fetched from Telegram, kept so they load fast
TYPES = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp", "webm": "video/webm"}


# ---------------------------------------------------------------- reading

async def chat_list(session: AsyncSession, q: str = "") -> list[dict]:
    """Conversations, newest first, with the group the person picked in the bot."""
    stmt = (select(BotChat, Group.name, BotUser.blocked, BotUser.suspended_until)
            .outerjoin(BotUser, BotUser.id == BotChat.chat_id).outerjoin(Group, Group.id == BotUser.group_id)
            .order_by(BotChat.last_at.desc()).limit(LISTED))
    if q := q.strip():
        like = f"%{q.lstrip('@')}%"
        stmt = stmt.where(or_(BotChat.name.ilike(like), BotChat.username.ilike(like), Group.name.ilike(like),
                              cast(BotChat.chat_id, String).ilike(like)))
    rows = []
    now = datetime.now().astimezone()
    for chat, group, banned, until in (await session.execute(stmt)).all():
        rows.append({"id": chat.chat_id, "title": chat.name or str(chat.chat_id), "group": group,
                     "username": chat.username, "tg_name": chat.name,
                     "stopped": bool(banned) or bool(until and until > now),
                     "blocked": chat.blocked, "last_text": chat.last_text or "", "last_dir": chat.last_dir,
                     "last_at": chat.last_at})
    return rows


async def list_version(session: AsyncSession) -> str:
    n, last = (await session.execute(select(func.count(), func.max(BotChat.last_at)).select_from(BotChat))).one()
    return f"{n}:{last.timestamp() if last else 0}"


async def chat_version(session: AsyncSession, chat_id: int) -> str:
    n, top, edited = (await session.execute(
        select(func.count(), func.max(BotMessage.id), func.max(BotMessage.edited_at))
        .where(BotMessage.chat_id == chat_id))).one()
    deleted = await session.scalar(select(func.count()).where(BotMessage.chat_id == chat_id, BotMessage.deleted))
    return f"{n}:{top}:{edited.timestamp() if edited else 0}:{deleted}"


async def messages(session: AsyncSession, chat_id: int) -> list[BotMessage]:
    rows = (await session.execute(select(BotMessage).where(BotMessage.chat_id == chat_id)
                                  .order_by(BotMessage.id.desc()).limit(SHOWN))).scalars().all()
    return list(reversed(rows))


# Telegram HTML -> safe HTML: everything is escaped, then only Telegram's own formatting tags are let back in.
_TAGS = re.compile(r"&lt;(/?)(b|strong|i|em|u|ins|s|strike|del|code|pre|blockquote)(?: [^&]*?)?&gt;")
_LINK = re.compile(r"&lt;a href=&quot;(https?://[^&\"]+|tg://[^&\"]+)&quot;&gt;")
_SPOILER = re.compile(r"&lt;(?:span class=&quot;tg-spoiler&quot;|tg-spoiler)&gt;")
_DROP = re.compile(r"&lt;/?(?:tg-emoji[^&]*?|span|tg-spoiler)&gt;")


def safe_html(text: str | None) -> Markup:
    if not text:
        return Markup("")
    s = escape(text, quote=True)
    s = _TAGS.sub(lambda m: f"<{m.group(1)}{m.group(2)}>", s)
    s = _LINK.sub(lambda m: f'<a href="{m.group(1)}" target="_blank" rel="noopener">', s).replace("&lt;/a&gt;", "</a>")
    s = _SPOILER.sub('<span class="spoiler">', s)
    s = _DROP.sub(lambda m: "</span>" if m.group(0).startswith("&lt;/") and "span" in m.group(0) else "", s)
    return Markup(s)


def day_label(t, dt: datetime) -> str:
    local = dt.astimezone(TASHKENT).date()
    today = datetime.now(TASHKENT).date()
    if local == today:
        return t("chat_today")
    if (today - local).days == 1:
        return t("chat_yesterday")
    return local.strftime("%d.%m.%Y")


def _context(request: Request, rows: list[BotMessage], admins: dict[int, str]) -> dict:
    t = translator(get_lang(request))
    items, last_day = [], None
    for m in rows:
        day = day_label(t, m.at)
        if day != last_day:
            items.append({"day": day})
            last_day = day
        items.append({"m": m})
    return {"items": items, "t": t, "safe_html": safe_html, "admins": admins,
            "hm": lambda dt: dt.astimezone(TASHKENT).strftime("%H:%M")}


async def _admins(session: AsyncSession) -> dict[int, str]:
    return dict((await session.execute(select(Admin.id, Admin.username))).all())


def _partial(request: Request, name: str, ctx: dict) -> str:
    return templates.get_template(name).render({"request": request, **ctx})


# ---------------------------------------------------------------- pages

@router.get("/chats", response_class=HTMLResponse)
async def chats_page(request: Request, c: int | None = None, q: str = "", admin: Admin = Depends(programmer),
                     session: AsyncSession = Depends(get_session, scope="function")):
    cid, campaigns = await resolve_campaign(session, None)
    people = await chat_list(session, q)
    chat = next((p for p in people if p["id"] == c), None)
    if c and chat is None:  # not in the (searched) list: still open it
        chat = next((p for p in await chat_list(session, str(c)) if p["id"] == c), None)
    ctx = {"people": people, "chat": chat, "q": q, "list_v": await list_version(session),
           "when": when_label(translator(get_lang(request))),
           "total": await session.scalar(select(func.count()).select_from(BotChat))}
    if chat:
        rows = await messages(session, chat["id"])
        ctx |= _context(request, rows, await _admins(session)) | {"chat_v": await chat_version(session, chat["id"])}
    return await render(request, "admin/chats.html", admin, (cid, campaigns), **ctx)


@router.get("/chats/{chat_id}/feed")
async def chat_feed(request: Request, chat_id: int, v: str = "", admin: Admin = Depends(programmer),
                    session: AsyncSession = Depends(get_session, scope="function")):
    """New or changed messages: the conversation again, only if something changed."""
    version = await chat_version(session, chat_id)
    if version == v:
        return JSONResponse({"v": version})
    ctx = _context(request, await messages(session, chat_id), await _admins(session))
    return JSONResponse({"v": version, "html": _partial(request, "admin/_chat_messages.html", ctx)})


@router.get("/chats/list")
async def chat_list_feed(request: Request, v: str = "", q: str = "", c: int | None = None,
                         admin: Admin = Depends(programmer), session: AsyncSession = Depends(get_session, scope="function")):
    version = await list_version(session)
    if version == v:
        return JSONResponse({"v": version})
    t = translator(get_lang(request))
    html = _partial(request, "admin/_chat_list.html", {"people": await chat_list(session, q), "chat": {"id": c},
                                                        "t": t, "q": q, "when": when_label(t),
                                                        "grp": await group_namer(request, admin)})
    return JSONResponse({"v": version, "html": html})


def when_label(t):
    def when(dt: datetime) -> str:
        local = dt.astimezone(TASHKENT)
        return local.strftime("%H:%M") if local.date() == datetime.now(TASHKENT).date() else local.strftime("%d.%m")
    return when


@router.post("/chats/{chat_id}/send")
async def chat_send(request: Request, chat_id: int, text: str = Form(""), photo: UploadFile | None = File(None),
                    admin: Admin = Depends(programmer), session: AsyncSession = Depends(get_session, scope="function")):
    """Write to this person as the bot. They see an ordinary message from the bot."""
    t = translator(get_lang(request))
    if await session.get(BotChat, chat_id) is None:
        raise HTTPException(404)
    text = text.strip()[:4000]
    picture = await photo.read(10 * 1024 * 1024 + 1) if photo and photo.filename else b""
    if not text and not picture:
        return JSONResponse({"ok": False, "error": t("chat_err_empty")}, status_code=400)
    origin, actor = chatlog.origin.set("panel"), chatlog.actor.set(admin.id)
    bot = chatlog.new_bot()
    try:
        if picture:
            jpeg = normalize_photo(picture)
            caption = text if text and len(text.encode("utf-16-le")) // 2 <= 1024 else None
            await bot.send_photo(chat_id, BufferedInputFile(jpeg, "photo.jpg"), caption=caption)
            if text and caption is None:
                await bot.send_message(chat_id, text)
        else:
            await bot.send_message(chat_id, text)
    except BadImage:
        return JSONResponse({"ok": False, "error": t("chat_err_image")}, status_code=400)
    except TelegramForbiddenError:
        return JSONResponse({"ok": False, "error": t("chat_err_blocked")}, status_code=409)
    except TelegramAPIError as e:
        return JSONResponse({"ok": False, "error": t("chat_err_telegram", error=str(e))}, status_code=502)
    finally:
        await bot.session.close()
        chatlog.origin.reset(origin)
        chatlog.actor.reset(actor)
    return JSONResponse({"ok": True})


@router.get("/chats/file/{mid}")
async def chat_file(mid: int, admin: Admin = Depends(programmer),
                    session: AsyncSession = Depends(get_session, scope="function")):
    """A photo (or sticker) of a conversation, fetched from Telegram once and kept here."""
    m = await session.get(BotMessage, mid)
    if m is None or not m.file_id or m.kind not in ("photo", "sticker"):
        raise HTTPException(404)
    key = hashlib.sha1(m.file_id.encode()).hexdigest()
    for ext, ctype in TYPES.items():
        cached = FILES / f"{key}.{ext}"
        if cached.is_file():
            return Response(cached.read_bytes(), media_type=ctype, headers={"Cache-Control": "private, max-age=86400"})
    bot = chatlog.new_bot()
    try:
        info = await bot.get_file(m.file_id)
        ext = (info.file_path or "").rsplit(".", 1)[-1].lower()
        if ext not in TYPES:  # animated stickers (.tgs) can't be shown as a picture
            raise HTTPException(404)
        data = (await bot.download_file(info.file_path)).read()
    except TelegramAPIError:
        raise HTTPException(404) from None
    finally:
        await bot.session.close()
    FILES.mkdir(parents=True, exist_ok=True)
    (FILES / f"{key}.{ext}").write_bytes(data)
    return Response(data, media_type=TYPES[ext], headers={"Cache-Control": "private, max-age=86400"})
