"""The whole server as one program - used on Windows, where a task started with Windows runs it
(scripts\\setup.bat sets that up; scripts\\server.bat manages it):

    python -m app.server

It runs the web server, the Telegram bot and the public tunnel, and starts each again if it stops; watches the
public address like scripts/tunnel.sh (a quick tunnel that stops answering gets a new address, the fixed ones
reconnect); and makes a database backup every night (app.backup). Logs: data/runtime/logs/.
On Linux systemd does the same job with scripts/server.sh, tunnel.sh and backup.sh.
"""
import asyncio
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import httpx

from app import backup
from app.config import get_settings
from app.runtime import ROOT, TUNNEL_RESTART_FILE, TUNNEL_STATUS_FILE, WEBAPP_URL_FILE

LOGS = ROOT / "data" / "runtime" / "logs"
STATUS_FILE = ROOT / "data" / "runtime" / "server_status.json"   # read by scripts\server.bat status
LOCK_PORT = 47801        # held while the server runs, so a second copy refuses to start
CHECK_EVERY = 60         # seconds between checks of the public address
MAX_FAILS = 4            # failed checks in a row before the tunnel is started again
BACKUP_AT = (3, 30)      # nightly backup, caught up after the computer was off
QUICK_URL = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")


def say(text: str) -> None:
    line = f"{datetime.now():%Y-%m-%d %H:%M:%S}  {text}"
    if sys.stdout:  # none when started without a console
        print(line, flush=True)
    with open(LOGS / "server.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")


def open_log(name: str):
    """data/runtime/logs/<name>.log, the previous one kept as .old once it passes 5 MB."""
    path = LOGS / f"{name}.log"
    try:
        if path.stat().st_size > 5_000_000:
            os.replace(path, path.with_suffix(".old"))
    except OSError:
        pass  # no log yet, or someone is reading it right now
    return open(path, "a", encoding="utf-8")


def child_env(**extra: str) -> dict:
    return {**os.environ, "PYTHONUTF8": "1", "PYTHONUNBUFFERED": "1", **extra}


def die_with_me() -> None:
    """Windows: put this process in a job that ends every child (web, bot, tunnel) when this process ends,
    however it ends - so stopping the task never leaves a bot running behind."""
    if os.name != "nt":
        return
    import ctypes
    from ctypes import wintypes

    class Basic(ctypes.Structure):
        _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64),
                    ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                    ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
                    ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD),
                    ("SchedulingClass", wintypes.DWORD)]

    class Extended(ctypes.Structure):
        _fields_ = [("BasicLimitInformation", Basic), ("IoInfo", ctypes.c_uint64 * 6),
                    ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
                    ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t)]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateJobObjectW.restype = wintypes.HANDLE
    kernel32.CreateJobObjectW.argtypes = [wintypes.LPVOID, wintypes.LPCWSTR]
    kernel32.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD]
    kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    job = kernel32.CreateJobObjectW(None, None)
    info = Extended()
    info.BasicLimitInformation.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    kernel32.SetInformationJobObject(job, 9, ctypes.byref(info), ctypes.sizeof(info))  # extended limit information
    if not kernel32.AssignProcessToJobObject(job, kernel32.GetCurrentProcess()):
        say(f"⚠️  Could not tie the children to the server (error {ctypes.get_last_error()})")
    die_with_me.job = job  # the handle stays open as long as this process lives


class Child:
    """A program kept running: started again 5 s after it stops (up to a minute if it keeps stopping right away,
    e.g. a wrong bot token). Its output goes to data/runtime/logs/<name>.log."""

    def __init__(self, name: str, command: list[str], env: dict | None = None, on_line=None, on_start=None):
        self.name, self.command, self.env = name, command, env or child_env()
        self.on_line, self.on_start = on_line, on_start
        self.proc: asyncio.subprocess.Process | None = None
        self.since = 0.0
        self.restarts = -1

    @property
    def running(self) -> bool:
        return self.proc is not None and self.proc.returncode is None

    async def keep_running(self) -> None:
        delay = 5
        while True:
            log = open_log(self.name)
            try:
                self.proc = await asyncio.create_subprocess_exec(
                    *self.command, cwd=ROOT, env=self.env, stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.STDOUT, limit=1 << 20)
            except OSError as e:
                log.close()
                say(f"❌ {self.name}: cannot start ({e}) - trying again in 30 s")
                await asyncio.sleep(30)
                continue
            self.since, self.restarts = time.time(), self.restarts + 1
            say(f"▶️  {self.name} started (pid {self.proc.pid})")
            if self.on_start:
                self.on_start()
            with log:
                async for raw in self.proc.stdout:
                    line = raw.decode("utf-8", "replace").rstrip()
                    log.write(f"{datetime.now():%H:%M:%S} {line}\n")
                    log.flush()
                    if self.on_line:
                        self.on_line(line)
            code = await self.proc.wait()
            delay = 5 if time.time() - self.since > 120 else min(delay * 2, 60)
            say(f"⏹  {self.name} stopped (exit code {code}) - starting again in {delay} s")
            await asyncio.sleep(delay)

    def stop(self) -> None:
        """Stop it; keep_running starts it again."""
        if self.running:
            self.proc.kill()


def write_url(url: str) -> None:
    tmp = WEBAPP_URL_FILE.with_suffix(".tmp")
    tmp.write_text(url)
    os.replace(tmp, WEBAPP_URL_FILE)
    say(f"🌐 Public address: {url}  (survey: {url}/survey)")


class Tunnel:
    """The public HTTPS address (TUNNEL in .env): quick, cloudflare or tailscale - see scripts/tunnel.sh."""

    def __init__(self, mode: str):
        self.mode = mode or "quick"
        self.url, self.fails, self.since, self.last_check = "", 0, time.time(), 0.0
        self.child: Child | None = None
        cloudflared = str(ROOT / "tools" / ("cloudflared.exe" if os.name == "nt" else "cloudflared"))
        port = get_settings().web_port
        if self.mode == "quick":
            self.child = Child("tunnel", [cloudflared, "tunnel", "--no-autoupdate", "--protocol", "http2",
                                          "--url", f"http://127.0.0.1:{port}"],
                               on_line=self.on_line, on_start=self.started)
        elif self.mode == "cloudflare":
            token, self.url = get_settings().cloudflare_tunnel_token, get_settings().webapp_url.rstrip("/")
            if not token or not self.url:
                say("❌ TUNNEL=cloudflare needs CLOUDFLARE_TUNNEL_TOKEN and WEBAPP_URL in .env")
            # The token goes in the environment, not the command line (which every user of the computer can read).
            self.child = Child("tunnel", [cloudflared, "tunnel", "--no-autoupdate", "--protocol", "http2", "run"],
                               env=child_env(TUNNEL_TOKEN=token), on_start=self.started)
        elif self.mode != "tailscale":
            say(f"❌ Unknown TUNNEL={self.mode} in .env (quick | tailscale | cloudflare)")

    def status(self, state: str, fails: int = 0) -> None:
        TUNNEL_STATUS_FILE.write_text(f"{state}|{fails}|{int(time.time())}")

    def started(self) -> None:
        self.since, self.fails = time.time(), 0
        self.status("starting")
        if self.mode == "quick":
            self.url = ""  # the address file keeps the old one until the new one is known
        elif self.url:
            write_url(self.url)

    def on_line(self, line: str) -> None:
        if not self.url and (m := QUICK_URL.search(line)):
            self.url = m.group(0)
            write_url(self.url)
        elif self.url and "Tunnel not found" in line:
            say("❌ Cloudflare deleted this quick tunnel - starting a new one (new address)")
            self.restart()

    def tailscale_up(self) -> None:
        """Turn Funnel on (tailscaled keeps it, this repairs a reset) and read this computer's address."""
        exe = shutil.which("tailscale") or os.path.join(os.environ.get("ProgramFiles", ""), "Tailscale",
                                                         "tailscale.exe")
        self.started()
        try:
            subprocess.run([exe, "funnel", "--bg", str(get_settings().web_port)], capture_output=True, timeout=30)
        except (OSError, subprocess.SubprocessError) as e:
            say(f"⚠️  tailscale funnel: {e}")
        try:
            info = json.loads(subprocess.run([exe, "status", "--json"], capture_output=True, timeout=30).stdout)
            self.url = "https://" + info["Self"]["DNSName"].rstrip(".")
            write_url(self.url)
        except (OSError, subprocess.SubprocessError, ValueError, KeyError) as e:
            say(f"❌ Tailscale: {e} - is it installed and logged in? (scripts\\setup.bat)")
            self.status("down", MAX_FAILS)

    def restart(self) -> None:
        self.status("starting")
        if self.child:
            self.child.stop()
        else:
            self.tailscale_up()

    async def watch(self) -> None:
        if self.mode == "tailscale":
            await asyncio.to_thread(self.tailscale_up)
        while True:
            await asyncio.sleep(5)
            now = time.time()
            if TUNNEL_RESTART_FILE.exists():  # the dashboard's "new address" button
                TUNNEL_RESTART_FILE.unlink(missing_ok=True)
                say("🔁 New address requested from the dashboard")
                self.restart()
                continue
            if not self.url:
                if self.mode == "quick" and now - self.since > 90:
                    say("❌ No public address after 90 s (no internet, or Cloudflare refused) - trying again")
                    self.restart()
                elif self.mode == "tailscale" and now - self.since > 60:
                    await asyncio.to_thread(self.tailscale_up)
                continue
            if now - self.since < 60 or now - self.last_check < CHECK_EVERY:
                continue
            self.last_check = now
            try:
                async with httpx.AsyncClient(timeout=20) as client:
                    code = (await client.get(f"{self.url}/healthz")).status_code
            except httpx.HTTPError:
                code = 0
            if code == 200:
                self.fails = 0
                self.status("ok")
                continue
            self.fails += 1
            self.status("down", self.fails)
            say(f"⚠️  Public address not answering ({code}), check {self.fails}/{MAX_FAILS}")
            if self.fails >= MAX_FAILS:
                say("❌ The public address is dead - " + ("starting a new tunnel (new address)" if self.mode == "quick"
                                                         else "reconnecting (same address)"))
                self.restart()


def backup_due(now: datetime, last: datetime | None) -> bool:
    """Today's backup time has passed and no copy was made since (also after the computer was off at night)."""
    today = now.replace(hour=BACKUP_AT[0], minute=BACKUP_AT[1], second=0, microsecond=0)
    return now >= today and (last is None or last < today)


async def backups() -> None:
    while True:
        last = backup.newest()
        if backup_due(datetime.now(), datetime.fromtimestamp(last.stat().st_mtime) if last else None):
            try:
                out = await asyncio.to_thread(backup.make)
                say(f"💾 Backup: {out.name}")
            except (Exception, SystemExit) as e:  # never let a failed backup stop the server; try again later
                say(f"❌ Backup failed: {e}")
                await asyncio.sleep(3600)
        await asyncio.sleep(600)


async def write_status(children: list[Child], tunnel: Tunnel) -> None:
    while True:
        STATUS_FILE.write_text(json.dumps({
            "at": int(time.time()), "pid": os.getpid(), "tunnel_mode": tunnel.mode, "url": tunnel.url,
            "children": {c.name: {"running": c.running, "since": int(c.since), "restarts": max(c.restarts, 0)}
                         for c in children},
        }))
        await asyncio.sleep(10)


async def forever(name: str, loop) -> None:
    """Run a loop of the server; a bug or a full disk inside it is logged and the loop starts again."""
    while True:
        try:
            await loop()
        except Exception as e:
            say(f"❌ {name}: {e!r} - starting it again in 30 s")
            await asyncio.sleep(30)


async def migrate() -> None:
    """Bring the database up to date - retried while PostgreSQL is still starting (right after boot)."""
    while True:
        result = await asyncio.to_thread(subprocess.run, [sys.executable, "-m", "alembic", "upgrade", "head"],
                                         cwd=ROOT, env=child_env(), capture_output=True, text=True)
        if result.returncode == 0:
            return
        say("⏳ Database not ready: " + (result.stderr.strip().splitlines() or ["?"])[-1] + " - trying again in 10 s")
        await asyncio.sleep(10)


async def web_ready(port: int) -> None:
    async with httpx.AsyncClient(timeout=3) as client:
        for _ in range(60):
            try:
                if (await client.get(f"http://127.0.0.1:{port}/healthz")).status_code == 200:
                    return
            except httpx.HTTPError:
                pass
            await asyncio.sleep(1)


async def main() -> None:
    settings = get_settings()
    say(f"🚀 Talaba Ovozi server starting (pid {os.getpid()}, TUNNEL={settings.tunnel or 'quick'})")
    await migrate()
    python = sys.executable
    web = Child("web", [python, "-m", "app.web"])
    bot = Child("bot", [python, "-m", "app.bot"])
    tunnel = Tunnel(settings.tunnel)
    tasks = [asyncio.create_task(forever("web", web.keep_running))]
    await web_ready(settings.web_port)
    say(f"📊 Dashboard: http://127.0.0.1:{settings.web_port}/admin")
    children = [web, bot] + ([tunnel.child] if tunnel.child else [])
    tasks += [asyncio.create_task(forever(c.name, c.keep_running)) for c in children[1:]]
    tasks += [asyncio.create_task(forever("tunnel watch", tunnel.watch)),
              asyncio.create_task(forever("backups", backups)),
              asyncio.create_task(forever("status", lambda: write_status(children, tunnel)))]
    await asyncio.gather(*tasks)


def run() -> None:
    LOGS.mkdir(parents=True, exist_ok=True)
    for stream in (sys.stdout, sys.stderr):  # a Windows console can't print emoji in its old code page
        if stream and hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    lock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        lock.bind(("127.0.0.1", LOCK_PORT))
    except OSError:
        raise SystemExit("❌ The server is already running (scripts\\server.bat status). Stop it first.")
    die_with_me()
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        say("⏹  Stopped (Ctrl+C)")


if __name__ == "__main__":
    run()
