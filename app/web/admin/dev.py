"""Programmer pages: the activity log (who did what, when, for how long) and the data structure.

Only programmer accounts reach these; everyone else gets "not found" (app.web.deps.programmer).
"""
import math
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import Integer, Text, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import audit
from app.models import Admin, AuditLog, Base
from app.web.admin.views import TASHKENT, render, resolve_campaign
from app.web.deps import get_session, programmer

router = APIRouter(prefix="/admin")
KINDS = ("login", "logout", "login_failed", "view", "action", "export", "denied", "error")
PER_PAGE = 100
ACTIVE_WITHIN = timedelta(minutes=15)   # a session with no logout and nothing newer is shown as ended


def _day(raw: str | None, default: date) -> date:
    try:
        return date.fromisoformat(raw) if raw else default
    except ValueError:
        return default


def duration(seconds: float | None) -> str:
    """3725 -> '1 h 2 min'; 75 -> '1 min 15 s'."""
    if seconds is None:
        return "—"
    s = int(seconds)
    if s < 60:
        return f"{s} s"
    if s < 3600:
        return f"{s // 60} min {s % 60:02d} s" if s < 600 else f"{s // 60} min"
    return f"{s // 3600} h {s % 3600 // 60} min"


@router.get("/audit", response_class=HTMLResponse)
async def audit_page(request: Request, tab: str = "sessions", user: str = "", kind: str = "", sid: str = "",
                     q: str = "", start: str = "", end: str = "", page: str = "1", admin: Admin = Depends(programmer),
                     session: AsyncSession = Depends(get_session, scope="function")):
    cid, campaigns = await resolve_campaign(session, None)
    today = datetime.now(TASHKENT).date()
    day_from, day_to = _day(start, today - timedelta(days=6)), _day(end, today)
    since = datetime.combine(day_from, datetime.min.time(), TASHKENT)
    until = datetime.combine(day_to + timedelta(days=1), datetime.min.time(), TASHKENT)
    now = datetime.now(timezone.utc)

    # Figures for the last 24 hours, whatever the filters.
    day_ago = now - timedelta(days=1)
    counts = dict((await session.execute(
        select(AuditLog.kind, func.count()).where(AuditLog.at >= day_ago).group_by(AuditLog.kind))).all())
    online = await session.scalar(select(func.count(func.distinct(AuditLog.sid))).where(
        AuditLog.at >= now - timedelta(minutes=10), AuditLog.sid.is_not(None),
        AuditLog.sid.not_in(select(AuditLog.sid).where(AuditLog.kind == "logout", AuditLog.sid.is_not(None)))))
    kpis = {"online": online or 0, "logins": counts.get("login", 0), "failed": counts.get("login_failed", 0),
            "actions": counts.get("action", 0) + counts.get("export", 0), "views": counts.get("view", 0),
            "problems": counts.get("error", 0) + counts.get("denied", 0)}
    users = [u for (u,) in (await session.execute(
        select(AuditLog.username).where(AuditLog.username.is_not(None)).distinct().order_by(AuditLog.username))).all()]

    def filtered(query):
        query = query.where(AuditLog.at >= since, AuditLog.at < until)
        if user:
            query = query.where(AuditLog.username == user)
        return query

    ctx = {"tab": "events" if tab == "events" or sid else "sessions", "kpis": kpis, "users": users, "user": user,
           "kind": kind if kind in KINDS else "", "kinds": KINDS, "sid": sid, "q": q,
           "start": day_from.isoformat(), "end": day_to.isoformat(), "duration": duration}

    if ctx["tab"] == "sessions":
        rows = (await session.execute(filtered(
            select(AuditLog.sid, func.min(AuditLog.at), func.max(AuditLog.at),
                   func.max(AuditLog.username), func.max(AuditLog.role), func.min(AuditLog.ip), func.min(AuditLog.agent),
                   func.sum(cast(AuditLog.kind == "view", Integer)),
                   func.sum(cast(AuditLog.kind.in_(("action", "export")), Integer)),
                   func.sum(cast(AuditLog.kind.in_(("error", "denied")), Integer)),
                   func.bool_or(AuditLog.kind == "logout"), func.bool_or(AuditLog.kind == "login"))
            .where(AuditLog.sid.is_not(None))).group_by(AuditLog.sid).order_by(func.max(AuditLog.at).desc()).limit(200)
        )).all()
        ctx["sessions"] = [{
            "sid": s, "start": first, "last": last, "username": name, "role": role, "ip": ip, "device": audit.device(agent),
            "views": views or 0, "actions": actions or 0, "problems": problems or 0,
            "state": "out" if out else ("active" if now - last < ACTIVE_WITHIN else "ended"),
            "seconds": (last - first).total_seconds(), "full": bool(login)} for
            s, first, last, name, role, ip, agent, views, actions, problems, out, login in rows]
        failed = (await session.execute(filtered(select(AuditLog).where(AuditLog.kind == "login_failed"))
                                        .order_by(AuditLog.at.desc()).limit(20))).scalars().all()
        ctx["failed"] = failed
    else:
        query = filtered(select(AuditLog))
        if sid:
            query = query.where(AuditLog.sid == sid)
        if ctx["kind"]:
            query = query.where(AuditLog.kind == ctx["kind"])
        if q.strip():
            like = f"%{q.strip()}%"
            query = query.where(or_(AuditLog.path.ilike(like), AuditLog.title.ilike(like), AuditLog.outcome.ilike(like),
                                    cast(AuditLog.details, Text).ilike(like)))
        total = await session.scalar(select(func.count()).select_from(query.subquery()))
        page_n = max(1, int(page) if page.isdigit() else 1)
        events = (await session.execute(query.order_by(AuditLog.at.desc(), AuditLog.id.desc())
                                        .offset((page_n - 1) * PER_PAGE).limit(PER_PAGE))).scalars().all()
        # Time on a page: until the same session's next request (pages open longer than 30 min count as "—").
        nxt = {}
        sids = {e.sid for e in events if e.sid}
        if sids:
            later = (await session.execute(
                select(AuditLog.id, func.lead(AuditLog.at).over(partition_by=AuditLog.sid, order_by=AuditLog.at))
                .where(AuditLog.sid.in_(sids)))).all()
            nxt = dict(later)
        rows, last_day = [], None
        for e in events:
            local = e.at.astimezone(TASHKENT)
            spent = (nxt.get(e.id) - e.at).total_seconds() if nxt.get(e.id) else None
            rows.append({"e": e, "time": local.strftime("%H:%M:%S"), "day": local.strftime("%d.%m.%Y"),
                         "new_day": local.date() != last_day, "device": audit.device(e.agent),
                         "spent": spent if e.kind == "view" and spent is not None and spent < 1800 else None})
            last_day = local.date()
        ctx |= {"events": rows, "total": total, "page": page_n, "pages": max(1, math.ceil(total / PER_PAGE))}
        if sid:
            ctx["session_info"] = (await session.execute(
                select(func.min(AuditLog.at), func.max(AuditLog.at), func.max(AuditLog.username), func.min(AuditLog.ip),
                       func.min(AuditLog.agent)).where(AuditLog.sid == sid))).one()
    return await render(request, "admin/audit.html", admin, (cid, campaigns), **ctx)


# ---------------------------------------------------------------- Data structure (shown on the Data page)

SCHEMA_LAYOUT = {  # table -> (column, row) on the diagram; the rest go to the "system" column
    "departments": (1, 1), "teachers": (1, 2), "subjects": (1, 3),
    "semesters": (2, 1), "teaching_assignments": (2, 2), "timetable_snapshots": (2, 3),
    "groups": (3, 1), "students": (3, 2), "survey_campaigns": (3, 3),
    "feedback": (4, 2),
}
SCHEMA_NOTES = {
    "timetable_snapshots": "EduPage JSON: groups, teachers, subjects, rooms, lessons",
    "teaching_assignments": "who teaches whom → whom a student rates",
    "feedback": "1 row = 1 student × 1 teacher × 1 survey",
    "teachers": "room_number = the teacher's room",
    "bot_chats": "everyone who wrote to the bot (Suhbatlar)",
    "bot_messages": "the bot's messages both ways; passports masked",
}


async def schema(session: AsyncSession) -> dict:
    """Tables, their columns and links (foreign keys), with row counts - drawn by admin.js on the Data page."""
    tables, links = [], []
    for table in Base.metadata.sorted_tables:
        n = await session.scalar(select(func.count()).select_from(table))
        cols = [{"name": c.name, "type": str(c.type).split("(")[0].lower().replace("varchar", "text"),
                 "pk": c.primary_key, "fk": bool(c.foreign_keys)} for c in table.columns]
        col, row = SCHEMA_LAYOUT.get(table.name, (5, 0))
        tables.append({"name": table.name, "n": n, "cols": cols, "col": col, "row": row,
                       "note": SCHEMA_NOTES.get(table.name, "")})
        for c in table.columns:
            for fk in c.foreign_keys:
                links.append({"from": table.name, "to": fk.column.table.name, "col": c.name})
    links.append({"from": "teaching_assignments", "to": "timetable_snapshots", "col": "built from", "soft": True})
    links.append({"from": "bot_messages", "to": "bot_chats", "col": "chat_id", "soft": True})
    return {"tables": tables, "links": links}
