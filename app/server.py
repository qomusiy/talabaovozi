"""The whole server as one program, on Linux and Windows:

    python -m app.server            # web server, Telegram bot and public address (Ctrl+C stops all three)
    python -m app.server --no-bot   # without the bot - e.g. to try the dashboard while the real server runs the bot
    python -m app.server status     # is it running? + the public address and the version
    python -m app.server update     # update from GitHub now (also: restart, backup, check) - the running server does it

What the computer starts is the launcher (Launcher, below): it runs the server - the supervisor, main(), as a child
process - and starts it again whenever it stops; does what the dashboard's Server page and the bot ask (restart,
update from GitHub, backup); and watches an update: if the new version doesn't come up healthy, it puts the previous
one back by itself (app.updater). The supervisor runs the web server, the bot and the public address, starts each
again if it stops, watches the address (a quick tunnel that stops answering gets a new one) and makes a database
backup every night (app.backup). Logs: data/runtime/logs/.
It starts with the computer as a systemd service on Linux (scripts/setup.sh; scripts/server.sh manages it) and as a
task on Windows (scripts\\setup.bat; scripts\\server.bat manages it).
"""
import argparse
import asyncio
import getpass
import json
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

import httpx

from app import backup, updater
from app.config import get_settings
from app.runtime import (CONTROL_ACTIONS, CONTROL_DIR, CONTROL_LOG_FILE, LAUNCHER_FILE, ROOT, SERVER_SCRIPT,
                         SERVER_STATUS_FILE, SETUP_SCRIPT, TUNNEL_RESTART_FILE, TUNNEL_STATUS_FILE, WEBAPP_URL_FILE,
                         address_check, control_log, launcher_alive, request_control, tunnel_status,
                         version_info)

LOGS = ROOT / "data" / "runtime" / "logs"
STATUS_FILE = SERVER_STATUS_FILE   # written every 10 s: `status`, and the bot's server messages to admins
STARTED = int(time.time())
LOCK_PORT = 47801        # held while the server runs, so a second copy refuses to start
ADDRESS_CHECK_EVERY = 60  # seconds between checks of the public address
MAX_FAILS = 4            # failed checks in a row before the tunnel is started again
BACKUP_AT = (3, 30)      # nightly backup, caught up after the computer was off
# a quick tunnel's address: words with hyphens - not api.trycloudflare.com, which cloudflared names when it fails
QUICK_URL = re.compile(r"https://(?!api\.)[a-z0-9]+(?:-[a-z0-9]+)+\.trycloudflare\.com")
CONNECTED = re.compile(r"Registered tunnel connection|Connection [0-9a-f-]+ registered")  # cloudflared's words
PROTOCOLS = ("http2", "quic")  # how cloudflared reaches Cloudflare: TCP 7844 first, UDP 7844 if that never connects
CONNECT_WITHIN = 90      # seconds for cloudflared to connect before it is started again


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
    e.g. a wrong bot token). Its output goes to data/runtime/logs/<name>.log.
    command: the program and its arguments - or a function that gives them, asked before every start;
    on_exit(exit code): may ask for a longer pause (seconds) before the next start."""

    def __init__(self, name: str, command, env: dict | None = None, on_line=None, on_start=None, on_exit=None):
        self.name, self.command, self.env = name, command, env or child_env()
        self.on_line, self.on_start, self.on_exit = on_line, on_start, on_exit
        self.proc: asyncio.subprocess.Process | None = None
        self.since = 0.0
        self.restarts = -1

    @property
    def running(self) -> bool:
        return self.proc is not None and self.proc.returncode is None

    async def keep_running(self) -> None:
        try:
            await self._loop()
        finally:  # the server stops: the program stops with it
            self.stop()

    async def _loop(self) -> None:
        delay = 5
        while True:
            log = open_log(self.name)
            command = self.command() if callable(self.command) else self.command
            try:
                self.proc = await asyncio.create_subprocess_exec(
                    *command, cwd=ROOT, env=self.env, stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.STDOUT, limit=1 << 20)
            except OSError as e:
                log.close()
                hint = f" - is it installed? {SETUP_SCRIPT} installs it" if isinstance(e, FileNotFoundError) else ""
                say(f"❌ {self.name}: cannot start {command[0]} ({e}) - trying again in 60 s{hint}")
                await asyncio.sleep(60)
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
                        try:
                            self.on_line(line)
                        except Exception as e:  # never stop reading the program's output
                            say(f"❌ {self.name}: {e!r}")
            code = await self.proc.wait()
            delay = 5 if time.time() - self.since > 120 else min(delay * 2, 60)
            if self.on_exit:
                try:
                    delay = max(delay, self.on_exit(code) or 0)
                except Exception as e:  # never stop keeping the program running
                    say(f"❌ {self.name}: {e!r}")
            say(f"⏹  {self.name} stopped (exit code {code}) - starting again in {delay} s")
            await asyncio.sleep(delay)

    def stop(self) -> None:
        """Stop it; keep_running starts it again."""
        if self.running:
            self.proc.kill()


def write_file(path: Path, text: str) -> bool:
    """Replace the file at once, so the bot and the web server never read half of it."""
    tmp = path.with_suffix(".tmp")
    tmp.write_text(text)
    for _ in range(50):  # Windows refuses to replace a file while the bot or the web server is reading it
        try:
            os.replace(tmp, path)
            return True
        except PermissionError:
            time.sleep(0.1)
    say(f"❌ Could not write {path}")
    return False


def write_url(url: str) -> None:
    if write_file(WEBAPP_URL_FILE, url):
        say(f"🌐 Public address: {url}  (survey: {url}/survey)")


class Tunnel:
    """The public HTTPS address of the survey (TUNNEL in .env, README › Fixed address):

    quick       a free Cloudflare quick tunnel, https://….trycloudflare.com - a NEW address after every restart
    tailscale   Tailscale Funnel, https://talaba-ovozi.<tailnet>.ts.net - the same address forever
    cloudflare  a Cloudflare named tunnel on your own domain (CLOUDFLARE_TUNNEL_TOKEN, WEBAPP_URL) - the same forever
    off         no public address (trying things on a computer that isn't the server)

    A quick address is handed out (the bot, the dashboard) only once cloudflared has connected to Cloudflare - an
    address it never connects is dead. cloudflared that doesn't connect is started again with the other protocol
    (http2 = TCP 7844, quic = UDP 7844: a network may close one of them), the tries further and further apart.
    """

    def __init__(self, mode: str):
        self.mode = mode or "quick"
        self.url, self.fails, self.since, self.last_check = "", 0, time.time(), 0.0
        self.connected, self.misses, self.proto = False, 0, 0  # proto: PROTOCOLS index - the one that last worked
        self.child: Child | None = None
        self.cloudflared = str(ROOT / "tools" / ("cloudflared.exe" if os.name == "nt" else "cloudflared"))
        if self.mode == "quick":
            self.child = Child("tunnel", self.command, on_line=self.on_line, on_start=self.started,
                               on_exit=self.ended)
        elif self.mode == "cloudflare":
            token, self.url = get_settings().cloudflare_tunnel_token, get_settings().webapp_url.rstrip("/")
            if not token or not self.url:
                say("❌ TUNNEL=cloudflare needs CLOUDFLARE_TUNNEL_TOKEN and WEBAPP_URL in .env")
            # The token goes in the environment, not the command line (which every user of the computer can read).
            self.child = Child("tunnel", self.command, env=child_env(TUNNEL_TOKEN=token), on_line=self.on_line,
                               on_start=self.started, on_exit=self.ended)
        elif self.mode not in ("tailscale", "off"):
            say(f"❌ Unknown TUNNEL={self.mode} in .env (quick | tailscale | cloudflare | off)")

    @property
    def protocol(self) -> str:
        return PROTOCOLS[self.proto]

    def command(self) -> list[str]:
        args = [self.cloudflared, "tunnel", "--no-autoupdate", "--protocol", self.protocol]
        return args + (["--url", f"http://127.0.0.1:{get_settings().web_port}"] if self.mode == "quick" else ["run"])

    def status(self, state: str, fails: int = 0) -> None:
        TUNNEL_STATUS_FILE.write_text(f"{state}|{fails}|{int(time.time())}")

    def started(self) -> None:
        self.since, self.fails, self.connected = time.time(), 0, False
        self.status("starting")
        if self.mode == "quick":
            self.url = ""  # the address file keeps the old one until the new tunnel is connected
        elif self.url:
            write_url(self.url)

    def on_line(self, line: str) -> None:
        if self.mode == "quick" and not self.url and (m := QUICK_URL.search(line)):
            self.url = m.group(0)
            say(f"🔗 Quick address {self.url} - connecting to Cloudflare ({self.protocol})")
        elif not self.connected and CONNECTED.search(line):
            self.connect()
        elif self.mode == "quick" and self.url and "Tunnel not found" in line:
            say("❌ Cloudflare deleted this quick tunnel - starting a new one (new address)")
            self.restart()

    def connect(self) -> None:
        """cloudflared reached Cloudflare: the address works - from now on it is handed out."""
        self.connected, self.misses = True, 0
        say(f"✅ Tunnel connected to Cloudflare ({self.protocol})")
        if self.mode == "quick" and self.url:
            write_url(self.url)

    def ended(self, code: int) -> int:
        """cloudflared stopped. If it never connected this time, the next start uses the other protocol, after a
        pause that grows (each quick try is a new address, and Cloudflare limits how many it hands out)."""
        if self.connected:
            return 0
        self.misses += 1
        tried, self.proto = self.protocol, (self.proto + 1) % len(PROTOCOLS)
        wait = 0 if self.misses < 2 else min(60 * 2 ** (self.misses - 2), 600)  # 0, 1, 2, 4, 8, 10 min
        say(f"❌ The tunnel did not connect to Cloudflare over {tried} (try {self.misses}) - next over {self.protocol}"
            + (f" in {wait // 60} min" if wait else "") + ". Port 7844 closed on this network? "
            "Diagnostics: the bot's 🖥 Server › 🩺, or python -m app.diagnose")
        self.status("down", MAX_FAILS)
        return wait

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
            say(f"❌ Tailscale: {e} - is it installed and logged in? ({SETUP_SCRIPT})")
            self.status("down", MAX_FAILS)

    def restart(self) -> None:
        self.status("starting")
        if self.child:
            self.child.stop()
        else:
            self.tailscale_up()

    async def watch(self) -> None:
        if self.mode == "off":
            await asyncio.Event().wait()  # nothing to watch, ever
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
            if self.child:  # cloudflared
                if not self.child.running:
                    continue  # between two starts: Child starts it again after its pause
                if not self.connected and now - self.since > CONNECT_WITHIN:
                    say(f"❌ {'Not connected to Cloudflare' if self.url else 'No public address'} after "
                        f"{CONNECT_WITHIN} s - starting the tunnel again")
                    self.since = now
                    self.restart()
                    continue
            elif not self.url:  # Tailscale
                if self.mode == "tailscale" and now - self.since > 60:
                    await asyncio.to_thread(self.tailscale_up)
                continue
            if not self.url or now - self.since < 60 or now - self.last_check < ADDRESS_CHECK_EVERY:
                continue
            self.last_check = now
            code, _ = await address_check(self.url, timeout=20)
            if code == 200:
                self.fails = 0
                self.status("ok")
                if self.child and not self.connected:  # it answers, so it is connected (whatever cloudflared said)
                    self.connect()
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
        write_file(STATUS_FILE, json.dumps({
            "at": int(time.time()), "started": STARTED, "pid": os.getpid(), "tunnel_mode": tunnel.mode,
            "run": os.environ.get("TALABA_RUN", ""),  # which start of the launcher's this is (Launcher.health)
            "url": tunnel.url,
            "cloudflared": ({"connected": tunnel.connected, "protocol": tunnel.protocol, "misses": tunnel.misses}
                            if tunnel.child else None),
            "children": {c.name: {"running": c.running, "since": int(c.since), "restarts": max(c.restarts, 0)}
                         for c in children},
        }))
        await asyncio.sleep(10)


async def forever(name: str, loop) -> None:
    """Run a loop of the server; a bug or a full disk inside it is logged and the loop starts again."""
    while True:
        try:
            await loop()
            await asyncio.sleep(5)  # a loop that ended by itself must not spin and starve the others
        except Exception as e:
            say(f"❌ {name}: {e!r} - starting it again in 30 s")
            await asyncio.sleep(30)


def update_pending() -> bool:
    """Does the database need an update (new code)? False for an empty database, or when it can't tell."""
    result = subprocess.run([sys.executable, "-m", "alembic", "current"], cwd=ROOT, env=child_env(),
                            capture_output=True, text=True)
    return result.returncode == 0 and bool(result.stdout.strip()) and "(head)" not in result.stdout


async def migrate() -> None:
    """Bring the database up to date - retried while PostgreSQL is still starting (right after boot). An update
    may change or delete data, so a backup is made before it (unless the launcher just made one for this update)."""
    if not os.environ.get("TALABA_BACKUP_DONE") and await asyncio.to_thread(update_pending):
        try:
            say(f"💾 Backup before updating the database: {(await asyncio.to_thread(backup.make)).name}")
        except (Exception, SystemExit) as e:
            say(f"⚠️  No backup before the update ({e}) - last night's copy is in data/backups")
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


async def main(with_bot: bool) -> None:
    settings = get_settings()
    if os.name != "nt":  # systemd (or kill) stops it the way Ctrl+C does: the programs stop with it
        asyncio.get_running_loop().add_signal_handler(signal.SIGTERM, asyncio.current_task().cancel)
    say(f"▶️  Server starting (pid {os.getpid()}, TUNNEL={settings.tunnel or 'quick'}"
        + ("" if with_bot else ", without the bot") + ")")
    await migrate()
    python = sys.executable
    web = Child("web", [python, "-m", "app.web"])
    tunnel = Tunnel(settings.tunnel)
    tasks = [asyncio.create_task(forever("web", web.keep_running))]
    await web_ready(settings.web_port)
    say(f"📊 Dashboard: http://127.0.0.1:{settings.web_port}/admin")
    children = ([web] + ([Child("bot", [python, "-m", "app.bot"])] if with_bot else [])
                + ([tunnel.child] if tunnel.child else []))
    tasks += [asyncio.create_task(forever(c.name, c.keep_running)) for c in children[1:]]
    tasks += [asyncio.create_task(forever("tunnel watch", tunnel.watch)),
              asyncio.create_task(forever("backups", backups)),
              asyncio.create_task(forever("status", lambda: write_status(children, tunnel)))]
    await asyncio.gather(*tasks)


# ================================================================ the launcher

HEALTH_TIMEOUT = int(os.environ.get("TALABA_UPDATE_TIMEOUT", "600"))  # an update must be healthy within this...
HEALTHY_FOR = int(os.environ.get("TALABA_HEALTHY_FOR", "60"))         # ...for this long without a restart
RESTART_TIMEOUT = 180   # a restart is reported as done once healthy (no rollback: the code didn't change)
CHECK_EVERY = 6 * 3600  # look for a newer version on GitHub
LOG_KEEP = 30           # actions kept in control_log.json


class Launcher:
    """What the computer starts. Runs the server (main(), as a child process: python -m app.server run --supervised)
    and starts it again whenever it stops; does the actions the dashboard and the bot ask for (control files,
    app.runtime.request_control) one at a time; watches an update and puts the previous version back if the new one
    doesn't come up healthy. It stays loaded with the code it started with - an update replaces the server's code,
    the launcher's own with the next restart of the computer or of the service/task."""

    def __init__(self, server_args: list[str]):
        self.cmd = [sys.executable, "-X", "utf8", "-m", "app.server", "run", "--supervised", *server_args]
        self.proc: subprocess.Popen | None = None
        self.run_id = ""
        self.started_at = self.next_start = 0.0
        self.backoff = 5
        self.worker: threading.Thread | None = None   # the action being done
        self.restart_for: dict | None = None          # set by an action: restart the server (after an update)
        self.watching: dict | None = None             # a restart/update until the server is healthy again
        self.next_check = time.time() + 120
        self.stopping = False
        self.log_lock = threading.Lock()
        try:
            self.commit = updater.current()["short"]
        except updater.UpdateError:
            self.commit = ""

    # -------------------------------------------------- the server
    def start(self, env: dict | None = None) -> None:
        # Each start has its own id, written back in the server's status: on Windows the process started here is
        # the venv's python.exe redirector, not the server itself, so process ids can't be compared.
        self.run_id = f"{os.getpid()}-{time.time_ns()}"
        self.proc = subprocess.Popen(self.cmd, cwd=ROOT, env=child_env(TALABA_RUN=self.run_id, **(env or {})),
                                     start_new_session=os.name != "nt")  # Linux: its own group, stopped as one
        self.started_at = time.time()

    def stop(self, timeout: int = 30) -> None:
        p = self.proc
        if p is None or p.poll() is not None:
            return
        if os.name == "nt":  # the whole tree: the redirector, the server, its web server, bot and tunnel
            subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"], capture_output=True)
        else:
            os.killpg(p.pid, signal.SIGTERM)
        try:
            p.wait(timeout)
        except subprocess.TimeoutExpired:
            if os.name == "nt":
                p.kill()
            else:
                os.killpg(p.pid, signal.SIGKILL)
            p.wait(10)

    def keep_running(self) -> None:
        if self.proc is None:
            if time.time() >= self.next_start:
                self.start()
            return
        code = self.proc.poll()
        if code is None:
            return
        self.backoff = min(self.backoff * 2, 60) if time.time() - self.started_at < 120 else 5
        say(f"⏹  The server stopped (exit code {code}) - starting it again in {self.backoff} s")
        self.proc, self.next_start = None, time.time() + self.backoff

    def health(self) -> tuple[bool, int, set]:
        """(the server's programs run and the web server answers, how often they restarted so far, which run)."""
        try:
            st = json.loads(SERVER_STATUS_FILE.read_text())
        except (OSError, ValueError):
            return False, 0, set()
        if self.proc is None or st.get("run") != self.run_id or time.time() - st.get("at", 0) > 25:
            return False, 0, set()
        kids = {k: v for k, v in st.get("children", {}).items() if k != "tunnel"}  # the internet's, not the code's
        running = {k for k, v in kids.items() if v.get("running")}
        try:
            web = httpx.get(f"http://127.0.0.1:{get_settings().web_port}/healthz", timeout=5).status_code == 200
        except httpx.HTTPError:
            web = False
        return web and "web" in running, sum(v.get("restarts", 0) for v in kids.values()), running

    # -------------------------------------------------- actions
    def log(self, entry: dict) -> dict:
        """Add or update an action in control_log.json (newest first)."""
        with self.log_lock:
            entries = [e for e in control_log() if e.get("id") != entry["id"]]
            entries.insert(0, entry)
            write_file(CONTROL_LOG_FILE, json.dumps(entries[:LOG_KEEP], ensure_ascii=False))
        return entry

    def finish(self, entry: dict, state: str, message: str = "") -> None:
        entry |= {"state": state, "message": message, "finished": int(time.time())}
        self.log(entry)
        icon = {"ok": "✅", "failed": "❌", "rolled_back": "↩️"}.get(state, "ℹ️")
        say(f"{icon} {entry['action']} ({entry['by']}): {message or state}")

    def take_requests(self) -> None:
        if (self.worker and self.worker.is_alive()) or self.restart_for or self.watching:
            return  # one at a time: the next waits in its file
        try:
            files = sorted(CONTROL_DIR.glob("*.json"))
        except OSError:
            return
        for f in files:
            try:
                req = json.loads(f.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                req = None
            f.unlink(missing_ok=True)
            if not isinstance(req, dict) or req.get("action") not in CONTROL_ACTIONS:
                continue
            entry = self.log({"id": str(req.get("id")), "action": req["action"], "by": str(req.get("by", "?")),
                              "at": int(time.time()), "state": "running", "message": "",
                              "notify": [int(x) for x in req.get("notify", []) if str(x).lstrip("-").isdigit()]})
            say(f"▶️  {entry['action']} asked by {entry['by']}")
            self.worker = threading.Thread(target=self.do, args=(entry,), daemon=True)
            self.worker.start()
            return

    def do(self, entry: dict) -> None:
        """An action, in its own thread (the launcher keeps watching the server meanwhile)."""
        action = entry["action"]
        try:
            if action == "restart":
                self.restart_for = {"entry": entry}
            elif action == "backup":
                self.finish(entry, "ok", backup.make().name)
            elif action == "check":
                info = updater.check()
                self.finish(entry, "failed" if info["error"] else "ok",
                            info["error"] or (f"{info['behind']} new" if info["behind"] else "up to date"))
            elif action == "update":
                _, _, running = self.health()
                state = updater.prepare(entry["id"])
                entry |= {"from": state["from"][:7], "to": state["to"][:7]}
                self.log(entry)
                self.restart_for = {"entry": entry, "update": state, "required": sorted(running)}
        except updater.NothingToDo as e:
            self.finish(entry, "ok", str(e))
        except updater.UpdateError as e:
            self.finish(entry, "failed", str(e))
        except (Exception, SystemExit) as e:
            self.finish(entry, "failed", f"{e!r}")

    def restart_now(self) -> None:
        job, self.restart_for = self.restart_for, None
        update = job.get("update")
        say("🔁 " + (f"Starting the new version {update['to'][:7]}" if update else "Restarting the server"))
        self.stop()
        self.start({"TALABA_BACKUP_DONE": "1"} if update else None)
        self.backoff = 5
        self.watching = {**job, "deadline": time.time() + (HEALTH_TIMEOUT if update else RESTART_TIMEOUT),
                         "since": None, "restarts": None, "checked": 0.0}
        if update:
            update["phase"] = "watch"
            updater.save_state(update)

    def watch(self) -> None:
        """After a restart or an update: done once the server is healthy for HEALTHY_FOR seconds in a row (an update
        also needs the programs that ran before it: the bot too). A failed update is undone."""
        w, now = self.watching, time.time()
        if not w or now - w["checked"] < 5:
            return
        w["checked"] = now
        ok, restarts, running = self.health()
        ok = ok and set(w.get("required", [])) <= running
        if ok and w["restarts"] == restarts:
            if now - w["since"] >= (HEALTHY_FOR if w.get("update") else 10):
                self.watching = None
                if w.get("update"):
                    updater.clear_state()
                    self.finish(w["entry"], "ok", f"{w['update']['from'][:7]} → {w['update']['to'][:7]}")
                else:
                    self.finish(w["entry"], "ok", "running again")
                return
        elif ok:  # healthy - from now on (or again, after one of its programs restarted)
            w["since"], w["restarts"] = now, restarts
        else:
            w["since"] = w["restarts"] = None
        if w.get("update") and restarts >= 3:  # it keeps stopping: no need to wait for the deadline
            self.watching = None
            self.roll_back(w, "the new version kept stopping")
        elif now > w["deadline"]:
            self.watching = None
            if w.get("update"):
                self.roll_back(w, f"the new version did not run properly within {HEALTH_TIMEOUT // 60} min")
            else:
                self.finish(w["entry"], "failed", f"not healthy after {RESTART_TIMEOUT // 60} min - see the logs")

    def roll_back(self, w: dict, reason: str) -> None:
        say(f"↩️  {reason} - putting the previous version back")
        self.stop()
        try:
            notes = updater.revert(w["update"], failed=True)
            state = "rolled_back"
        except (Exception, SystemExit) as e:
            notes, state = f"could not put everything back: {e!r} - see {SERVER_SCRIPT} logs", "failed"
        self.start()
        self.finish(w["entry"], state, f"{reason}. {notes}")

    def resume(self) -> None:
        """At start: finish what a restart of the computer (or of the launcher) interrupted."""
        state = updater.load_state()
        for e in control_log():
            if e.get("state") == "running" and not (state and e.get("id") == state.get("entry")):
                self.finish(e, "failed", "interrupted (the server was stopped)")
        if not state:
            return
        entry = next((e for e in control_log() if e.get("id") == state.get("entry")), None) or self.log(
            {"id": state.get("entry") or f"resumed-{int(time.time())}", "action": "update", "by": "?",
             "at": state.get("at", int(time.time())), "state": "running", "message": "", "notify": []})
        if state.get("phase") in ("restart", "watch"):   # the new version is on disk: check it as after the update
            say("🔎 An update was interrupted - checking the new version")
            self.watching = {"entry": entry, "update": state, "deadline": time.time() + HEALTH_TIMEOUT,
                             "since": None, "restarts": None, "checked": 0.0}
        else:  # stopped half-way (moving the code, packages): back to how it was before
            try:
                updater.revert_code(state)
                self.finish(entry, "failed", "interrupted half-way - the previous version is back")
            except updater.UpdateError as e:
                self.finish(entry, "failed", f"interrupted half-way, and could not undo it: {e}")
            updater.clear_state()

    def heartbeat(self) -> None:
        busy = bool((self.worker and self.worker.is_alive()) or self.restart_for or self.watching)
        write_file(LAUNCHER_FILE, json.dumps({"pid": os.getpid(), "at": int(time.time()), "commit": self.commit,
                                              "server_pid": self.proc.pid if self.proc else None, "busy": busy}))

    def run(self) -> None:
        CONTROL_DIR.mkdir(parents=True, exist_ok=True)
        if os.name != "nt":  # systemd (or kill) stops it the way Ctrl+C does
            signal.signal(signal.SIGTERM, lambda *_: setattr(self, "stopping", True))
        say(f"🚀 Talaba Ovozi starting (launcher pid {os.getpid()}, version {self.commit or '?'})")
        try:
            self.resume()
            updater.check(fetch=False)  # the version that runs now, for the dashboard (GitHub is asked later)
        except Exception as e:
            say(f"❌ launcher: {e!r} - going on")
        beat = 0.0
        try:
            while not self.stopping:
                try:
                    self.keep_running()
                    if self.restart_for and not (self.worker and self.worker.is_alive()):
                        self.restart_now()
                    self.watch()
                    self.take_requests()
                    if time.time() >= self.next_check and not (self.worker and self.worker.is_alive()):
                        self.next_check = time.time() + CHECK_EVERY
                        self.worker = threading.Thread(target=updater.check, daemon=True)  # quietly: version.json
                        self.worker.start()
                    if time.time() - beat >= 5:
                        beat = time.time()
                        self.heartbeat()
                except Exception as e:  # a full disk, a file Windows keeps locked...: never stop looking after it
                    say(f"❌ launcher: {e!r} - going on")
                    time.sleep(5)
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        say("⏹  Stopping")
        self.stop()
        LAUNCHER_FILE.unlink(missing_ok=True)
        STATUS_FILE.unlink(missing_ok=True)


def ask(action: str) -> int:
    """`python -m app.server update` (restart, backup, check): the running launcher does it; this shows how it goes.
    Exit code 0 done, 1 failed, 2 the server isn't running (the scripts then do it the old way)."""
    if not launcher_alive():
        print(f"❌ The server is not running ({SERVER_SCRIPT} start)")
        return 2
    rid = request_control(action, f"{getpass.getuser()} (command line)")
    print(f"⏳ {action}: asked the server - it can take a few minutes")
    shown, deadline = "", time.time() + HEALTH_TIMEOUT + 1800
    while time.time() < deadline:
        time.sleep(2)
        entry = next((e for e in control_log() if e.get("id") == rid), None)
        if not entry:
            continue
        state = entry.get("state")
        if state == "running":
            if entry.get("to") and shown != entry["to"]:
                shown = entry["to"]
                print(f"   new version {entry['to']} is starting, being checked (up to {HEALTH_TIMEOUT // 60} min)")
            continue
        icon = {"ok": "✅", "rolled_back": "↩️"}.get(state, "❌")
        print(f"{icon} {action}: {entry.get('message') or state}")
        return 0 if state == "ok" else 1
    print(f"⚠️  No answer yet - see: {SERVER_SCRIPT} logs")
    return 1


def show_status() -> None:
    """Is the server running (it writes STATUS_FILE every 10 s)? + the public address and the newest backup."""
    try:
        status = json.loads(STATUS_FILE.read_text())
    except (OSError, ValueError):
        status = None
    now = time.time()
    if status and now - status["at"] < 30:
        for name, c in status["children"].items():
            if c["running"]:
                print(f"  ✅ {name:8} running for {int((now - c['since']) / 60)} min (restarts: {c['restarts']})")
            else:
                print(f"  ❌ {name:8} NOT running - see: {SERVER_SCRIPT} logs {name}")
        if status["url"]:
            print(f"  🌐 address  {status['url']}   (last check: {tunnel_status()['state']})")
            print(f"  📝 survey   {status['url']}/survey   (students open it from the bot)")
        elif status.get("tunnel_mode") == "off":
            print("  ⏸  address  none (TUNNEL=off in .env)")
        else:
            print("  ⏳ address  none yet (the tunnel is starting)")
    else:
        print(f"  ❌ server   NOT running - {SERVER_SCRIPT} start")
    print(f"  📊 admin    http://127.0.0.1:{get_settings().web_port}/admin   (on this computer)")
    last = backup.newest()
    print(f"  💾 backup   {last.name if last else 'none yet'}")
    info = version_info()
    if current := info.get("current"):
        news = f" - {info['behind']} newer on GitHub ({SERVER_SCRIPT} update)" if info.get("behind") else ""
        print(f"  🔖 version  {current['short']} of {current['date'][:10]}{news}")


def run() -> None:
    parser = argparse.ArgumentParser(prog="python -m app.server", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", nargs="?", choices=("run", "status", *CONTROL_ACTIONS), default="run")
    parser.add_argument("--no-bot", action="store_true", help="without the Telegram bot")
    parser.add_argument("--supervised", action="store_true", help=argparse.SUPPRESS)  # the launcher's child
    args = parser.parse_args()
    for stream in (sys.stdout, sys.stderr):  # a Windows console can't print emoji in its old code page
        if stream and hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    if args.command == "status":
        return show_status()
    if args.command in CONTROL_ACTIONS:
        sys.exit(ask(args.command))
    LOGS.mkdir(parents=True, exist_ok=True)
    if args.supervised:  # the server itself, run by the launcher
        die_with_me()
        try:
            asyncio.run(main(with_bot=not args.no_bot))
        except (KeyboardInterrupt, asyncio.CancelledError):
            say("⏹  Server stopped")
        finally:
            STATUS_FILE.unlink(missing_ok=True)
        return
    lock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        lock.bind(("127.0.0.1", LOCK_PORT))
    except OSError:
        raise SystemExit(f"❌ The server is already running ({SERVER_SCRIPT} status). Stop it first.")
    die_with_me()
    Launcher(["--no-bot"] if args.no_bot else []).run()


if __name__ == "__main__":
    run()
