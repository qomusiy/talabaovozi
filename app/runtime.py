"""Values that change while the app runs (not configuration)."""
import json
import os
import time
from pathlib import Path

from app.config import get_settings

ROOT = Path(__file__).resolve().parent.parent
WEBAPP_URL_FILE = ROOT / "data" / "runtime" / "webapp_url"
# What to run on this computer, for messages that say so.
SERVER_SCRIPT = r"scripts\server.bat" if os.name == "nt" else "scripts/server.sh"
SETUP_SCRIPT = r"scripts\setup.bat" if os.name == "nt" else "scripts/setup.sh"

TUNNEL_STATUS_FILE = ROOT / "data" / "runtime" / "tunnel_status"
TUNNEL_RESTART_FILE = ROOT / "data" / "runtime" / "tunnel_restart"
SERVER_STATUS_FILE = ROOT / "data" / "runtime" / "server_status.json"  # app.server writes it every 10 s


def server_status() -> dict:
    """What app.server last wrote: {"at", "started", "pid", "url", "children": {name: {"running", ...}}} - or {}
    if it doesn't run (or hasn't written for 30 s)."""
    try:
        status = json.loads(SERVER_STATUS_FILE.read_text())
        return status if time.time() - status["at"] < 30 else {}
    except (OSError, ValueError, KeyError, TypeError):
        return {}


def tunnel_status() -> dict:
    """What app.server last found: {"state": ok / down / starting / unknown, "fails": n, "at": unix time}."""
    try:
        state, fails, at = TUNNEL_STATUS_FILE.read_text().strip().split("|")
        return {"state": state, "fails": int(fails), "at": int(at)}
    except (OSError, ValueError):
        return {"state": "unknown", "fails": 0, "at": 0}


def fixed_address() -> bool:
    """Is the public address permanent (Tailscale Funnel, a Cloudflare named tunnel, WEBAPP_URL in .env)?
    Then there is no "new address" to ask for - a restart of the tunnel reconnects to the same one."""
    s = get_settings()
    return s.tunnel in ("tailscale", "cloudflare") or bool(s.webapp_url)


def request_tunnel_restart() -> None:
    """Ask the server (app.server) for a new tunnel (it checks every few seconds; the address changes)."""
    TUNNEL_RESTART_FILE.parent.mkdir(parents=True, exist_ok=True)
    TUNNEL_RESTART_FILE.write_text("1")


def webapp_url() -> str:
    """Public HTTPS base URL of the survey Mini App, or "" if there is none.

    WEBAPP_URL in .env wins (TUNNEL=cloudflare). Otherwise the address the server (app.server) wrote for the
    current tunnel is used - read fresh every time, so the bot follows when the address changes.
    """
    if url := get_settings().webapp_url:
        return url.rstrip("/")
    try:
        return WEBAPP_URL_FILE.read_text().strip().rstrip("/")
    except OSError:
        return ""


# Files the dashboard uploads: the picture on the bot's menu card, photos/videos of messages to students.
MEDIA_DIR = ROOT / "data" / "media"
MENU_PHOTO_FILE = MEDIA_DIR / "menu.jpg"            # uploaded on the Bot page; replaces the demo picture
DEFAULT_MENU_PHOTO = ROOT / "app" / "assets" / "menu.jpg"


def menu_photo():
    """The picture shown on top of the bot's menu card: the uploaded one, else the demo one (None if neither)."""
    for path in (MENU_PHOTO_FILE, DEFAULT_MENU_PHOTO):
        if path.is_file():
            return path
    return None
