"""Foydalanuvchilar (programmer accounts only): the bot's users - their Telegram accounts.

The survey is anonymous to everyone else; this page is for finding and stopping abuse: who rated what, everything
Telegram tells about an account (name, @username, id, profile photo, bio, language, Premium, ...), its conversation
with the bot, and what can be done about it - block, suspend for a while, warn, change the group, delete its
ratings, delete it. Every action is in the activity log (Jurnal).
"""
import hashlib
import math
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

from aiogram.exceptions import TelegramAPIError, TelegramForbiddenError
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot import chatlog
from app.models import RATING_CRITERIA, BotMessage, BotUser, Feedback, Group, SurveyCampaign, Teacher
from app.runtime import ROOT
from app.services import users as users_svc
from app.web.admin import analytics as an
from app.web.admin.i18n import translator
from app.web.admin.views import TASHKENT, flash, get_lang, render, resolve_campaign
from app.web.deps import get_session, programmer

router = APIRouter(prefix="/admin/users")
PER_PAGE = 50
FILTERS = ("all", "stopped", "flood", "rated", "no_group", "demo")
PHOTOS = ROOT / "data" / "runtime" / "chatfiles"   # profile photos fetched from Telegram, kept so they load fast
SUSPEND_HOURS = (1, 24, 24 * 7)


def _t(request: Request):
    return translator(get_lang(request))


def _back(uid: int, anchor: str = "") -> RedirectResponse:
    return RedirectResponse(f"/admin/users/{uid}{anchor}", status_code=303)


def _filter(kind: str, now: datetime):
    stopped = or_(BotUser.blocked, BotUser.suspended_until > now)
    return {"stopped": stopped, "flood": BotUser.floods > 0, "no_group": BotUser.group_id.is_(None),
            "demo": BotUser.is_demo}.get(kind)


@router.get("", response_class=HTMLResponse)
async def users_page(request: Request, q: str = "", f: str = "all", group: str = "", page: str = "1",
                     admin=Depends(programmer), session: AsyncSession = Depends(get_session, scope="function")):
    f = f if f in FILTERS else "all"
    page_n = max(1, int(page) if page.isdigit() else 1)
    now = datetime.now(timezone.utc)
    rated = (select(Feedback.user_id.label("uid"), func.count(Feedback.id).label("n"),
                    func.max(Feedback.updated_at).label("last")).group_by(Feedback.user_id).subquery())
    base = (select(BotUser, Group.name, func.coalesce(rated.c.n, 0).label("n"), rated.c.last)
            .outerjoin(Group, Group.id == BotUser.group_id).outerjoin(rated, rated.c.uid == BotUser.id))
    if f != "demo":
        base = base.where(BotUser.is_demo.is_(False))
    if q.strip():
        base = base.where(or_(an.who_search(q), Group.name.ilike(f"%{q.strip()}%")))
    if group.isdigit():
        base = base.where(BotUser.group_id == int(group))
    counts = {}
    for kind in FILTERS:
        cond = rated.c.n > 0 if kind == "rated" else _filter(kind, now)
        counts[kind] = await session.scalar(select(func.count()).select_from(
            (base.where(cond) if cond is not None else base).subquery()))
    if f == "rated":
        base = base.where(rated.c.n > 0)
    elif (cond := _filter(f, now)) is not None:
        base = base.where(cond)
    total = counts[f]
    rows = (await session.execute(base.order_by(BotUser.last_seen_at.desc())
                                  .offset((page_n - 1) * PER_PAGE).limit(PER_PAGE))).all()
    cid, campaigns = await resolve_campaign(session, None)
    params = {k: v for k, v in (("q", q), ("f", f if f != "all" else ""), ("group", group)) if v}
    return await render(request, "admin/users.html", admin, (cid, campaigns),
                        rows=[{"u": u, "group": g, "n": n, "last": last, "state": users_svc.restriction(u, now)}
                              for u, g, n, last in rows],
                        counts=counts, f=f, q=q, total=total, page=page_n, pages=max(1, math.ceil(total / PER_PAGE)),
                        params=urlencode(params), group_id=int(group) if group.isdigit() else None,
                        groups=await an.all_groups(session), local=lambda dt: dt.astimezone(TASHKENT) if dt else None)


async def _user(session: AsyncSession, uid: int) -> BotUser:
    user = await users_svc.get(session, uid)
    if user is None:
        raise HTTPException(404)
    return user


async def refresh_from_telegram(user: BotUser) -> str | None:
    """Ask Telegram for everything it tells a bot about this person (getChat: bio, birthdate, ...; the newest
    profile photo). Returns an error text, or None."""
    if user.id <= 0:
        return None
    bot = chatlog.new_bot()
    try:
        chat = await bot.get_chat(user.id)
        photos = await bot.get_user_profile_photos(user.id, limit=1)
    except TelegramAPIError as e:
        return str(e)
    finally:
        await bot.session.close()
    info = chat.model_dump(exclude_none=True, mode="json")
    user.profile = {**(user.profile or {}), "chat": info,
                    "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    user.first_name, user.last_name = chat.first_name or user.first_name, chat.last_name
    user.username = chat.username or user.username
    user.photo_file_id = photos.photos[0][-1].file_id if photos.total_count and photos.photos else None
    return None


@router.get("/{uid}", response_class=HTMLResponse)
async def user_page(request: Request, uid: int, admin=Depends(programmer),
                    session: AsyncSession = Depends(get_session, scope="function")):
    user = await _user(session, uid)
    if user.id > 0 and "chat" not in (user.profile or {}):  # the first look: what Telegram tells about them
        await refresh_from_telegram(user)
    ratings = (await session.execute(
        select(Feedback, Teacher.full_name, SurveyCampaign.title, Group.name)
        .join(Teacher, Teacher.id == Feedback.teacher_id).join(SurveyCampaign, SurveyCampaign.id == Feedback.campaign_id)
        .outerjoin(Group, Group.id == Feedback.group_id).where(Feedback.user_id == uid)
        .order_by(Feedback.updated_at.desc()))).all()
    messages = await session.scalar(select(func.count(BotMessage.id)).where(BotMessage.chat_id == uid,
                                                                           BotMessage.dir.in_(("in", "tap"))))
    cid, campaigns = await resolve_campaign(session, None)
    t = _t(request)
    return await render(
        request, "admin/user.html", admin, (cid, campaigns),
        {"label": {"s": user.name}, "kind": "user", "entity": f"user:{uid}", "ctx": None},
        [{"label": {"s": t("nav_users"), "k": "nav_users", "v": {}}, "kind": "/admin/users", "path": "/admin/users",
          "url": "/admin/users"}],
        u=user, state=users_svc.restriction(user), messages=messages, groups=await an.all_groups(session),
        ratings=[{"f": f, "teacher": tname, "survey": survey, "group": gname,
                  "overall": round(sum(getattr(f, c) for c in RATING_CRITERIA) / 3, 1)}
                 for f, tname, survey, gname in ratings],
        campaigns_rated=sorted({(f.campaign_id, survey) for f, _, survey, _ in ratings}, key=lambda x: -x[0]),
        local=lambda dt: dt.astimezone(TASHKENT).strftime("%d.%m.%Y %H:%M") if dt else "—",
        suspend_hours=SUSPEND_HOURS, telegram_info=(user.profile or {}))


@router.post("/{uid}/refresh")
async def user_refresh(request: Request, uid: int, admin=Depends(programmer),
                       session: AsyncSession = Depends(get_session, scope="function")):
    user = await _user(session, uid)
    error = await refresh_from_telegram(user)
    flash(request, "bad" if error else "good", _t(request)("us_refresh_failed", error=error) if error
          else _t(request)("us_refreshed"))
    return _back(uid)


@router.get("/{uid}/photo")
async def user_photo(uid: int, admin=Depends(programmer), session: AsyncSession = Depends(get_session, scope="function")):
    """The newest profile photo, fetched from Telegram once and kept here."""
    user = await _user(session, uid)
    if not user.photo_file_id:
        raise HTTPException(404)
    cached = PHOTOS / f"{hashlib.sha1(user.photo_file_id.encode()).hexdigest()}.jpg"
    if not cached.is_file():
        bot = chatlog.new_bot()
        try:
            info = await bot.get_file(user.photo_file_id)
            data = (await bot.download_file(info.file_path)).read()
        except TelegramAPIError:
            raise HTTPException(404) from None
        finally:
            await bot.session.close()
        PHOTOS.mkdir(parents=True, exist_ok=True)
        cached.write_bytes(data)
    return Response(cached.read_bytes(), media_type="image/jpeg", headers={"Cache-Control": "private, max-age=86400"})


@router.post("/{uid}/block")
async def user_block(request: Request, uid: int, blocked: bool = Form(False), note: str = Form(""),
                     admin=Depends(programmer), session: AsyncSession = Depends(get_session, scope="function")):
    """Blocked: the bot doesn't answer them (it says so, at most once an hour) and the survey refuses them."""
    user = await _user(session, uid)
    user.blocked = blocked
    if note.strip():
        user.note = note.strip()[:2000]
    if not blocked:
        user.suspended_until = None
    flash(request, "good", _t(request)("us_blocked" if blocked else "us_unblocked", name=user.name))
    return _back(uid)


@router.post("/{uid}/suspend")
async def user_suspend(request: Request, uid: int, hours: str = Form(""), admin=Depends(programmer),
                       session: AsyncSession = Depends(get_session, scope="function")):
    """Stop them for a while (0 = lift it now)."""
    t = _t(request)
    user = await _user(session, uid)
    if not hours.isdigit() or int(hours) > 24 * 365:
        flash(request, "bad", t("us_err_hours"))
        return _back(uid)
    n = int(hours)
    user.suspended_until = datetime.now(timezone.utc) + timedelta(hours=n) if n else None
    flash(request, "good", t("us_suspended", name=user.name, until=user.suspended_until.astimezone(TASHKENT)
                             .strftime("%d.%m.%Y %H:%M")) if n else t("us_unsuspended", name=user.name))
    return _back(uid)


@router.post("/{uid}/warn")
async def user_warn(request: Request, uid: int, text: str = Form(""), admin=Depends(programmer),
                    session: AsyncSession = Depends(get_session, scope="function")):
    """A warning from the bot (an ordinary message; it is in the conversation log)."""
    t = _t(request)
    user = await _user(session, uid)
    text = text.strip()[:4000]
    if not text or user.id <= 0:
        flash(request, "bad", t("chat_err_empty"))
        return _back(uid, "#warn")
    origin, actor = chatlog.origin.set("panel"), chatlog.actor.set(admin.id)
    bot = chatlog.new_bot()
    try:
        await bot.send_message(user.id, text)
        user.warnings = (user.warnings or 0) + 1
        flash(request, "good", t("us_warned", name=user.name))
    except TelegramForbiddenError:
        flash(request, "bad", t("chat_err_blocked"))
    except TelegramAPIError as e:
        flash(request, "bad", t("chat_err_telegram", error=str(e)))
    finally:
        await bot.session.close()
        chatlog.origin.reset(origin)
        chatlog.actor.reset(actor)
    return _back(uid)


@router.post("/{uid}/group")
async def user_group(request: Request, uid: int, group: str = Form(""), admin=Depends(programmer),
                     session: AsyncSession = Depends(get_session, scope="function")):
    """Their group from now on (ratings already given keep the group they were given in)."""
    user = await _user(session, uid)
    user.group_id = int(group) if group.isdigit() and await session.get(Group, int(group)) else None
    flash(request, "good", _t(request)("saved"))
    return _back(uid)


@router.post("/{uid}/note")
async def user_note(request: Request, uid: int, note: str = Form(""), admin=Depends(programmer),
                    session: AsyncSession = Depends(get_session, scope="function")):
    user = await _user(session, uid)
    user.note = note.strip()[:2000] or None
    flash(request, "good", _t(request)("saved"))
    return _back(uid)


@router.post("/{uid}/ratings/delete")
async def user_ratings_delete(request: Request, uid: int, campaign: str = Form(""), admin=Depends(programmer),
                              session: AsyncSession = Depends(get_session, scope="function")):
    """Delete this account's ratings - of one survey round, or all of them (spam, an attack)."""
    user = await _user(session, uid)
    stmt = delete(Feedback).where(Feedback.user_id == uid)
    if campaign.isdigit():
        stmt = stmt.where(Feedback.campaign_id == int(campaign))
    n = (await session.execute(stmt)).rowcount
    flash(request, "good", _t(request)("us_ratings_deleted", n=n, name=user.name))
    return _back(uid)


@router.post("/{uid}/delete")
async def user_delete(request: Request, uid: int, admin=Depends(programmer),
                      session: AsyncSession = Depends(get_session, scope="function")):
    """Forget the account and its ratings (the conversation log stays). If they write again, they start anew -
    block them instead to keep them out."""
    user = await _user(session, uid)
    name = user.name
    await session.execute(delete(BotUser).where(BotUser.id == uid))
    flash(request, "good", _t(request)("us_deleted", name=name))
    return RedirectResponse("/admin/users", status_code=303)
