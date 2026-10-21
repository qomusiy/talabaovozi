"""Values that change while the app runs (not configuration)."""
import asyncio
import json
import os
import shutil
import socket
import subprocess
import time
from pathlib import Path
from urllib.parse import urlsplit

import httpx

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


# ---------------------------------------------------------------- remote control (app.launcher)
# The dashboard's Server page, the bot and `server.sh/.bat update` ask the launcher for an action by writing one small
# file into CONTROL_DIR; the launcher does it and writes what happened into CONTROL_LOG_FILE (newest first).
CONTROL_DIR = ROOT / "data" / "runtime" / "control"
CONTROL_LOG_FILE = ROOT / "data" / "runtime" / "control_log.json"
VERSION_FILE = ROOT / "data" / "runtime" / "version.json"    # the code that runs, and what GitHub has (app.updater)
LAUNCHER_FILE = ROOT / "data" / "runtime" / "launcher.json"  # the launcher's heartbeat (every few seconds)
CONTROL_ACTIONS = ("restart", "update", "backup", "check")


def _read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def launcher_alive() -> bool:
    """Is the launcher running (and so will it do what is asked)?"""
    beat = _read_json(LAUNCHER_FILE, {})
    return isinstance(beat, dict) and time.time() - beat.get("at", 0) < 20


def request_control(action: str, by: str, notify: list[int] | None = None) -> str:
    """Ask the launcher to restart / update / back up / check for updates; returns the request's id (its entry in
    control_log() shows how it went). notify: Telegram chats the bot tells when it is done."""
    if action not in CONTROL_ACTIONS:
        raise ValueError(action)
    CONTROL_DIR.mkdir(parents=True, exist_ok=True)
    rid = f"{time.time_ns()}-{os.getpid()}"
    tmp = CONTROL_DIR / f"{rid}.tmp"
    tmp.write_text(json.dumps({"id": rid, "action": action, "by": by[:100], "at": int(time.time()),
                               "notify": notify or []}), encoding="utf-8")
    os.replace(tmp, CONTROL_DIR / f"{rid}.json")  # the launcher only reads finished .json files
    return rid


def launcher_info() -> dict:
    """The launcher's last heartbeat: {"pid", "at", "commit" (the version it started with), "busy"}."""
    beat = _read_json(LAUNCHER_FILE, {})
    return beat if isinstance(beat, dict) else {}


def control_log() -> list[dict]:
    """What the launcher did lately, newest first: [{"id", "action", "by", "at", "state": running / ok / failed /
    rolled_back, "message", "finished", ...}]."""
    log = _read_json(CONTROL_LOG_FILE, [])
    return log if isinstance(log, list) else []


def version_info() -> dict:
    """{"current": {"commit", "short", "date", "subject"}, "behind": n, "commits": [...], "checked": unix time,
    "error": text} - written by the launcher (app.updater)."""
    info = _read_json(VERSION_FILE, {})
    return info if isinstance(info, dict) else {}


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


DOH = ("https://1.1.1.1/dns-query?name={}&type=A", "https://8.8.8.8/resolve?name={}&type=A")  # public DNS over HTTPS


async def _public_ipv4(client: httpx.AsyncClient, host: str) -> str | None:
    """The address the internet sees for `host` - asked from public DNS, not this computer's (which may be
    Tailscale's own and point back at this computer)."""
    for url in DOH:
        try:
            answers = (await client.get(url.format(host), headers={"accept": "application/dns-json"})).json()
            return next(a["data"] for a in answers.get("Answer", []) if a.get("type") == 1)
        except (httpx.HTTPError, ValueError, KeyError, StopIteration, AttributeError):
            continue
    return None


async def _through(client: httpx.AsyncClient, ip: str, host: str) -> int:
    return (await client.get(f"https://{ip}/healthz", headers={"Host": host},
                             extensions={"sni_hostname": host})).status_code


async def address_check(url: str, timeout: float = 15) -> tuple[int, str]:
    """Does the public address answer, asked from this computer: (HTTP status of {url}/healthz or 0, how it was
    asked - "direct", "edge", "public" or why not).
    - A quick address: this network's DNS may not know a brand-new one yet, or know it only as IPv6 the network
      doesn't route - the site works for everyone else, only this computer can't see it. Then it is asked through
      Cloudflare's IPv4 edge (Cloudflare answers for every address it serves there), so a working tunnel is never
      taken for a dead one.
    - A Tailscale address (….ts.net): this computer's own DNS may be Tailscale's, which points back at this
      computer and would say yes even when the internet can't get in - so it is asked the way the internet asks:
      the address from public DNS, through Tailscale's Funnel servers."""
    host = urlsplit(url).hostname or ""
    async with httpx.AsyncClient(timeout=timeout) as client:
        why = ""
        if host.endswith(".ts.net"):
            try:
                if ip := await _public_ipv4(client, host):
                    return await _through(client, ip, host), "public"
                why = "public DNS doesn't know it"
            except httpx.HTTPError as e:
                why = str(e) or type(e).__name__
        try:
            return (await client.get(f"{url}/healthz")).status_code, "direct"
        except httpx.HTTPError as e:
            why = "; ".join(x for x in (why, str(e) or type(e).__name__) if x)
        if not host.endswith(".trycloudflare.com"):
            return 0, why
        try:
            found = await asyncio.get_running_loop().getaddrinfo("api.trycloudflare.com", 443, family=socket.AF_INET,
                                                                  type=socket.SOCK_STREAM)
            return await _through(client, found[0][4][0], host), "edge"
        except (OSError, httpx.HTTPError) as e:
            return 0, f"{why}; via Cloudflare's IPv4 edge: {str(e) or type(e).__name__}"


async def address_answers(url: str) -> bool:
    return bool(url) and (await address_check(url))[0] == 200


def tailscale_exe() -> str:
    found = shutil.which("tailscale")
    if found:
        return found
    exe = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Tailscale" / "tailscale.exe"
    return str(exe) if os.name == "nt" else "tailscale"


def tailscale_info() -> dict:
    """{"running": bool, "name": "talaba-ovozi.tail1a2b.ts.net", "ips": [...], "error": text} - never raises."""
    try:
        r = subprocess.run([tailscale_exe(), "status", "--json"], capture_output=True, text=True, timeout=15)
        info = json.loads(r.stdout or "{}")
        me = info.get("Self") or {}
        return {"running": info.get("BackendState") == "Running", "state": info.get("BackendState") or "?",
                "name": (me.get("DNSName") or "").rstrip("."), "ips": me.get("TailscaleIPs") or [], "error": ""}
    except (OSError, subprocess.SubprocessError, ValueError) as e:
        return {"running": False, "state": "", "name": "", "ips": [], "error": str(e) or type(e).__name__}


_tailnet = {"at": 0.0, "ips": frozenset()}


async def tailnet_ips() -> frozenset:
    """This computer's own Tailscale addresses (asked again every minute)."""
    if time.time() - _tailnet["at"] > 60:
        _tailnet["at"] = time.time()
        _tailnet["ips"] = frozenset((await asyncio.to_thread(tailscale_info))["ips"])
    return _tailnet["ips"]


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
