"""Activity log of the dashboard: who logged in, which pages they opened, what they changed (old -> new), errors.

Every /admin request passes AuditMiddleware, which writes one `audit_log` row after the response:
- kind: login / login_failed / logout / view (a page) / action (a form) / export (Excel) / denied (403) / error
- the page title (set by the page itself, see views.render), the message the admin saw after an action,
  the form fields (passwords and passport codes hidden), and every database change the request made -
  collected from SQLAlchemy as the request flushes, so "Kafedra: Ingliz tili -> Oliy matematika" is there
  without each page having to report it.
Only programmer accounts can read the log (Dasturchi › Jurnal).
"""
import contextvars
import logging
import re
import time
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from urllib.parse import parse_qsl

from sqlalchemy import delete, event, inspect
from sqlalchemy.orm import Session
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.db import session_scope
from app.models import Admin, AuditLog, ImportLog, TimetableSnapshot
from app.web.security import client_ip

log = logging.getLogger("audit")
KEEP_DAYS = 365
SECRET_FIELDS = re.compile(r"password|passport|current|new|repeat|token|secret", re.I)
SECRET_COLUMNS = {"password_hash", "passport_hash"}
SKIP_MODELS = (AuditLog, TimetableSnapshot, ImportLog)   # big or self-describing
QUIET_PATHS = ("/admin/bot/audience",)                    # background requests of a page, not something a person did

# The database changes of the request being handled (None outside a dashboard request, e.g. in the bot).
_changes: contextvars.ContextVar[list | None] = contextvars.ContextVar("audit_changes", default=None)


def note(entity: str, entity_id, field: str, old, new) -> None:
    """Record a change the ORM can't see (settings written with INSERT ... ON CONFLICT, bulk deletes)."""
    changes = _changes.get()
    if changes is not None and old != new:
        changes.append({"entity": entity, "id": entity_id, "field": field, "old": _plain(old), "new": _plain(new)})


def _plain(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat(timespec="minutes") if isinstance(value, datetime) else value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value if not isinstance(value, str) else value[:300]
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value][:50]
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in list(value.items())[:50]}
    return str(value)[:300]


def _label(obj) -> str:
    for attr in ("full_name", "name", "title", "username", "key"):
        if (value := getattr(obj, attr, None)) is not None:
            return str(value)[:120]
    return ""


def _models_by_table() -> dict:
    from app.models import Base
    return {m.class_.__table__.name: m.class_ for m in Base.registry.mappers}


def _linked(session: Session, column, value):
    """A foreign key's value with the name of the row it points to: 'Oliy matematika #2'."""
    fk = next(iter(column.foreign_keys), None) if column is not None else None
    if value is None or fk is None:
        return _plain(value)
    model = _models_by_table().get(fk.column.table.name)
    try:
        with session.no_autoflush:
            row = session.get(model, value) if model else None
    except Exception:
        row = None
    return f"{_label(row)} #{value}" if row is not None and _label(row) else value


@event.listens_for(Session, "before_flush")
def _collect(session: Session, _ctx, _instances) -> None:
    """Every insert, update and delete the ORM is about to write, as entity / field / old -> new."""
    changes = _changes.get()
    if changes is None:
        return
    for obj in session.new:
        if isinstance(obj, SKIP_MODELS):
            continue
        fields = {c.key: _plain(getattr(obj, c.key, None)) for c in inspect(obj).mapper.column_attrs
                  if c.key not in ("id", "created_at", "updated_at") and getattr(obj, c.key, None) is not None}
        changes.append({"entity": type(obj).__name__, "op": "create", "label": _label(obj),
                        "fields": {k: ("•••" if k in SECRET_COLUMNS else v) for k, v in fields.items()}})
    for obj in session.dirty:
        if isinstance(obj, SKIP_MODELS) or not session.is_modified(obj):
            continue
        state = inspect(obj)
        for attr in state.mapper.column_attrs:
            if attr.key == "updated_at":
                continue
            hist = state.attrs[attr.key].history
            if not hist.has_changes():
                continue
            old = hist.deleted[0] if hist.deleted else None
            new = hist.added[0] if hist.added else None
            if old == new:
                continue
            secret = attr.key in SECRET_COLUMNS
            column = attr.columns[0] if attr.columns else None
            changes.append({"entity": type(obj).__name__, "id": state.identity[0] if state.identity else None,
                            "label": _label(obj), "field": attr.key,
                            "old": "•••" if secret else _linked(session, column, old),
                            "new": "•••" if secret else _linked(session, column, new)})
    for obj in session.deleted:
        if not isinstance(obj, SKIP_MODELS):
            changes.append({"entity": type(obj).__name__, "op": "delete", "label": _label(obj),
                            "id": inspect(obj).identity[0] if inspect(obj).identity else None})


@event.listens_for(Session, "do_orm_execute")
def _bulk(state) -> None:
    """DELETE/UPDATE statements run directly (e.g. "delete this teacher") - the ORM flush doesn't see those."""
    changes = _changes.get()
    if changes is None or not (state.is_delete or state.is_update):
        return
    try:
        sql = str(state.statement.compile(compile_kwargs={"literal_binds": True}))
    except Exception:  # some values can't be written inline
        sql = str(state.statement)
    table = getattr(getattr(state.statement, "table", None), "name", "")
    if table in ("audit_log", "timetable_snapshots", "app_settings", "broadcasts"):
        return
    changes.append({"entity": table, "op": "delete" if state.is_delete else "update", "sql": " ".join(sql.split())[:400]})


# ---------------------------------------------------------------- Request log

def device(agent: str | None) -> str:
    """'Mozilla/5.0 (X11; Linux x86_64) ... Chrome/140 ...' -> 'Chrome · Linux'."""
    a = agent or ""
    browser = next((name for key, name in (("Edg/", "Edge"), ("OPR/", "Opera"), ("YaBrowser", "Yandex"),
                                           ("Firefox/", "Firefox"), ("Chrome/", "Chrome"), ("Safari/", "Safari"))
                    if key in a), "")
    system = next((name for key, name in (("Android", "Android"), ("iPhone", "iPhone"), ("iPad", "iPad"),
                                          ("Windows", "Windows"), ("Mac OS", "macOS"), ("Linux", "Linux"))
                   if key in a), "")
    return " · ".join(x for x in (browser, system) if x) or (a[:40] if a else "—")


def _kind(request: Request, status: int, before: dict, after: dict) -> str | None:
    path, method = request.url.path, request.method
    if path == "/admin/login" and method == "POST":
        return "login" if status == 303 and after.get("admin_id") else "login_failed"
    if path == "/admin/logout":
        return "logout" if before.get("admin_id") else None
    if not (before.get("admin_id") or after.get("admin_id")):
        return None                           # not logged in: login page, redirects to it
    if status >= 500:
        return "error"
    if status in (401, 403):
        return "denied"
    if path.endswith(".xlsx"):
        return "export"
    if method == "POST" or path.startswith("/admin/lang/"):
        return "action"
    if status == 200 and path not in QUIET_PATHS:
        return "view"
    return None


def _form(request: Request, body: bytes) -> dict | None:
    kind = request.headers.get("content-type", "")
    if "multipart/form-data" in kind:
        return {"(file)": "upload"}
    if not body:
        return None
    fields: dict[str, list[str]] = {}
    for key, value in parse_qsl(body.decode("utf-8", "replace"), keep_blank_values=True):
        fields.setdefault(key, []).append("•••" if SECRET_FIELDS.search(key) and value else value[:300])
    return {k: v[0] if len(v) == 1 else v for k, v in fields.items()}


class AuditMiddleware(BaseHTTPMiddleware):
    """Logs every dashboard request (see the module docstring). Must run inside SessionMiddleware."""

    async def dispatch(self, request: Request, call_next):
        if not request.url.path.startswith("/admin"):
            return await call_next(request)
        started = time.monotonic()
        before = dict(request.session)
        body = b""
        if request.method == "POST" and "multipart/form-data" not in request.headers.get("content-type", ""):
            body = await request.body()   # kept by Starlette for the page itself
        changes: list = []
        token = _changes.set(changes)
        error = None
        try:
            response = await call_next(request)
            status = response.status_code
        except Exception as e:
            error, status = f"{type(e).__name__}: {e}", 500
            raise
        finally:
            _changes.reset(token)
            try:
                await self._write(request, status, before, body, changes, error, started)
            except Exception:  # the log must never break the dashboard
                log.exception("Could not write the activity log")
        return response

    async def _write(self, request: Request, status: int, before: dict, body: bytes, changes: list,
                     error: str | None, started: float) -> None:
        after = dict(request.session) if "session" in request.scope else {}
        kind = _kind(request, status, before, after)
        if kind is None:
            return
        who = after if kind != "logout" else before
        form = _form(request, body)
        flash = after.get("flash") or {}
        outcome = error or flash.get("text")
        details = {k: v for k, v in (("form", form), ("changes", changes)) if v}
        if kind == "logout" and before.get("login_at"):
            details["session_seconds"] = int(time.time() - before["login_at"])
        if kind == "login_failed":
            details["username"] = (form or {}).get("username", "")
        async with session_scope() as session:
            admin_id = who.get("admin_id")
            account = await session.get(Admin, admin_id) if admin_id else None
            session.add(AuditLog(
                admin_id=admin_id, username=account.username if account else (form or {}).get("username"),
                role=account.role if account else None, sid=who.get("sid"), kind=kind, method=request.method,
                path=request.url.path[:255], query=(request.url.query or None) and request.url.query[:500],
                title=getattr(request.state, "audit_title", None), outcome=outcome, status=status,
                ms=int((time.monotonic() - started) * 1000), ip=client_ip(request)[:64],
                agent=(request.headers.get("user-agent") or "")[:255] or None, details=details or None))


async def bot_action(session, admin, path: str, title: str, details: dict | None = None) -> None:
    """Something an admin did through the bot (Telegram), in the same activity log as the dashboard."""
    session.add(AuditLog(admin_id=admin.id, username=admin.username, role=admin.role, kind="action", method="BOT",
                         path=path[:255], title=title[:255], status=200, ms=0, agent="Telegram bot",
                         details=details))


async def prune(session) -> None:
    await session.execute(delete(AuditLog).where(AuditLog.at < datetime.now(timezone.utc) - timedelta(days=KEEP_DAYS)))
