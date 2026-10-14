"""Server (programmer accounts only): the server computer, from anywhere - like a hosting company's control panel.

Whether the web server, the bot and the public address run; the version and what GitHub has that this computer
doesn't; Update / Restart / Back up / Check for updates (the launcher does them: app.server.Launcher, and puts the
previous version back by itself if an update doesn't come up healthy); what was done and how it went; the logs;
the database copies to download; disk space and the database's size. Every action is in the activity log (Jurnal).
"""
import os
import platform
import re
import shutil
import time
from datetime import datetime

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app import backup
from app.config import get_settings
from app.runtime import (CONTROL_ACTIONS, ROOT, control_log, launcher_alive, launcher_info, request_control,
                         server_status, tunnel_status, version_info, webapp_url)
from app.web.admin.i18n import translator
from app.web.admin.views import TASHKENT, get_lang, render, resolve_campaign
from app.web.deps import get_session, programmer
from app.web.templating import templates

router = APIRouter(prefix="/admin/server")
LOGS = ROOT / "data" / "runtime" / "logs"
LOG_NAMES = ("server", "web", "bot", "tunnel")
LOG_LINES = 400
# Copies that may be downloaded: the database and uploaded files - never a transfer file (it holds .env's secrets).
DOWNLOADABLE = re.compile(r"^(feedback-\d{4}-\d{2}-\d{2}_\d{4}\.sql\.gz|media-\d{4}-\d{2}-\d{2}_\d{4}\.tar\.gz)$")


def _local(ts: int | float | None) -> str:
    return datetime.fromtimestamp(ts, TASHKENT).strftime("%d.%m.%Y %H:%M") if ts else "—"


def _size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit in ("B", "KB") else f"{n:.1f} {unit}"
        n /= 1024
    return str(n)


def _ago(t, ts: int | float | None) -> str:
    if not ts:
        return "—"
    minutes = int((time.time() - ts) // 60)
    if minutes < 1:
        return t("sv_now")
    if minutes < 60:
        return t("sv_min_ago", n=minutes)
    if minutes < 48 * 60:
        return t("sv_h_ago", n=minutes // 60)
    return t("sv_d_ago", n=minutes // 1440)


def live_state(t) -> dict:
    """What the page shows and keeps fresh (also /admin/server/live)."""
    st, launcher = server_status(), launcher_info()
    alive = launcher_alive()
    parts = []
    for name, c in (st.get("children") or {}).items():
        parts.append({"name": name, "running": c.get("running"), "since": _ago(t, c.get("since")),
                      "restarts": c.get("restarts", 0)})
    log = control_log()
    running = next((e for e in log if e.get("state") == "running"), None)
    info = version_info()
    return {
        "alive": alive, "running": bool(st), "busy": bool(launcher.get("busy")) or running is not None,
        "parts": parts, "started": _ago(t, st.get("started")), "started_at": _local(st.get("started")),
        "url": webapp_url(), "tunnel": tunnel_status()["state"], "tunnel_mode": st.get("tunnel_mode") or "",
        "current": info.get("current"), "behind": info.get("behind", 0), "commits": info.get("commits", [])[:15],
        "ahead": info.get("ahead", 0), "failed": info.get("failed", False), "check_error": info.get("error", ""),
        "checked": _ago(t, info.get("checked")),
        "launcher_commit": launcher.get("commit", ""),
        "log": [{**e, "at_s": _local(e.get("at")), "finished_s": _local(e.get("finished"))} for e in log[:12]],
        "active": running,
    }


@router.get("", response_class=HTMLResponse)
async def server_page(request: Request, admin=Depends(programmer),
                      session: AsyncSession = Depends(get_session, scope="function")):
    t = translator(get_lang(request))
    cid, campaigns = await resolve_campaign(session, None)
    disk = shutil.disk_usage(ROOT)
    db_size = await session.scalar(text("select pg_database_size(current_database())"))
    copies = sorted(((p.name, p.stat()) for p in backup.BACKUPS.glob("*.gz") if DOWNLOADABLE.match(p.name)),
                    key=lambda x: x[1].st_mtime, reverse=True)
    machine = {"os": f"{platform.system()} {platform.release()}", "python": platform.python_version(),
               "host": platform.node(), "disk_free": _size(disk.free), "disk_total": _size(disk.total),
               "disk_pct": round(100 * disk.used / disk.total) if disk.total else 0, "db": _size(db_size or 0),
               "root": str(ROOT), "pid": os.getpid()}
    return await render(request, "admin/server.html", admin, (cid, campaigns),
                        live=live_state(t), machine=machine, log_names=LOG_NAMES,
                        copies=[{"name": n, "size": _size(s.st_size), "at": _local(s.st_mtime)} for n, s in copies[:20]],
                        public_admin=not get_settings().admin_local_only)


@router.get("/live", response_class=HTMLResponse)
async def server_live(request: Request, admin=Depends(programmer)):
    """The parts of the page that change (state, actions in progress, what was done) - polled by admin.js."""
    t = translator(get_lang(request))
    live = live_state(t)
    html = templates.get_template("admin/_server_live.html").render({"request": request, "t": t, "live": live})
    return JSONResponse({"html": html, "busy": live["busy"]})


@router.post("/action")
async def server_action(request: Request, action: str = Form(...), admin=Depends(programmer)):
    t = translator(get_lang(request))
    if action not in CONTROL_ACTIONS:
        raise HTTPException(400)
    if not launcher_alive():
        return JSONResponse({"ok": False, "error": t("sv_no_launcher")}, status_code=409)
    if any(e.get("state") == "running" for e in control_log()):
        return JSONResponse({"ok": False, "error": t("sv_busy")}, status_code=409)
    request.state.audit_title = f"Server › {action}"
    rid = request_control(action, f"{admin.username} (dashboard)",
                          notify=[admin.telegram_id] if admin.telegram_id else None)
    return JSONResponse({"ok": True, "id": rid})


@router.get("/logs")
async def server_logs(name: str = "server", admin=Depends(programmer)):
    if name not in LOG_NAMES:
        raise HTTPException(404)
    path = LOGS / f"{name}.log"
    try:
        with open(path, "rb") as f:
            f.seek(0, 2)
            f.seek(max(0, f.tell() - 200_000))
            lines = f.read().decode("utf-8", "replace").splitlines()[-LOG_LINES:]
    except OSError:
        lines = []
    return JSONResponse({"name": name, "lines": lines})


@router.get("/backups/{name}")
async def server_backup_file(name: str, request: Request, admin=Depends(programmer)):
    """A database copy (or uploaded files) to keep somewhere else - all the data: programmer accounts only."""
    if not DOWNLOADABLE.match(name) or not (backup.BACKUPS / name).is_file():
        raise HTTPException(404)
    request.state.audit_title = f"Server › download {name}"
    return FileResponse(backup.BACKUPS / name, filename=name, media_type="application/gzip")

