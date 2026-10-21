"""Why doesn't the site open? - checked on the server computer itself, so the cause can be found from anywhere: the
bot's 🖥 Server › 🩺 Diagnostics (programmer accounts), or on the computer:

    python -m app.diagnose          # the checks
    python -m app.diagnose --logs   # and the end of every log

A Cloudflare tunnel (TUNNEL=quick or cloudflare) needs the internet, a quick tunnel also api.trycloudflare.com for
its address, and both need port 7844 to Cloudflare's tunnel servers (TCP for http2, UDP for quic) - the port a school
or office network most often closes. All the checks run at once, each with a short time limit (15 s at most).
"""
import asyncio
import re
import ssl
import subprocess
import sys
import time
from datetime import datetime

import httpx

from app.config import get_settings
from app.runtime import ROOT, address_check, server_status, tailscale_info, tunnel_status, webapp_url

LOGS = ROOT / "data" / "runtime" / "logs"
LOG_NAMES = ("server", "tunnel", "bot", "web")
EDGES = ("region1.v2.argotunnel.com", "region2.v2.argotunnel.com")   # Cloudflare's tunnel servers
TRACE = "https://www.cloudflare.com/cdn-cgi/trace"                   # any internet; its clock; this side's country
QUICK_API = "https://api.trycloudflare.com"                         # where a quick tunnel gets its address
CLOUDFLARE = ("quick", "cloudflare")
LIMIT = 10


def _why(e: BaseException) -> str:
    if isinstance(e, (asyncio.TimeoutError, httpx.TimeoutException)):
        return f"no answer in {LIMIT} s"
    text = str(e) or type(e).__name__
    return re.sub(r"\s+", " ", text)[:120]


async def _timed(coro, limit: float = LIMIT) -> tuple[bool, object, int]:
    start = time.monotonic()
    try:
        value = await asyncio.wait_for(coro, limit)
        return True, value, int((time.monotonic() - start) * 1000)
    except Exception as e:  # every failure is a finding, never an error of the check itself
        return False, _why(e), int((time.monotonic() - start) * 1000)


async def _get(url: str) -> httpx.Response:
    async with httpx.AsyncClient(timeout=LIMIT, follow_redirects=False) as client:
        return await client.get(url)


async def _edge(host: str) -> str:
    """Port 7844 open the way cloudflared's http2 uses it: TCP and a TLS handshake. Cloudflare signs these with its
    own authority (cloudflared carries it), so a finished handshake is the proof - the certificate isn't checked."""
    ctx = ssl.create_default_context()
    ctx.check_hostname, ctx.verify_mode = False, ssl.CERT_NONE
    _, writer = await asyncio.open_connection(host, 7844, ssl=ctx, server_hostname="h2.cftunnel.com")
    peer = (writer.get_extra_info("peername") or ("?",))[0]
    writer.close()
    return peer


async def _dns(host: str) -> str:
    found = await asyncio.get_running_loop().getaddrinfo(host, 7844, proto=6)
    return found[0][4][0]


def cloudflared_version() -> str:
    exe = ROOT / "tools" / ("cloudflared.exe" if sys.platform == "win32" else "cloudflared")
    if not exe.exists():
        return "not installed"
    try:
        out = subprocess.run([str(exe), "--version"], capture_output=True, text=True, timeout=10).stdout
        return (re.search(r"version (\S+)", out) or re.search(r"(\S+)", out or "?")).group(1)
    except (OSError, subprocess.SubprocessError, AttributeError):
        return "?"


def tail(name: str, lines: int) -> list[str]:
    try:
        with open(LOGS / f"{name}.log", "rb") as f:
            f.seek(0, 2)
            f.seek(max(0, f.tell() - 400 * lines))
            return f.read().decode("utf-8", "replace").splitlines()[-lines:]
    except OSError:
        return []


PRECHECK = re.compile(r'precheck component="([^"]+)" details="([^"]*)".*?status=(\w+)')
STAMP = re.compile(r"^(?:\d\d:\d\d:\d\d )?(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ) ?")  # ours (time), cloudflared's (UTC)


def _local(line: str) -> tuple[datetime | None, str]:
    """(cloudflared's UTC time in this computer's time, the rest of the line)."""
    if m := STAMP.match(line):
        return datetime.fromisoformat(m.group(1).replace("Z", "+00:00")).astimezone(), line[m.end():]
    return None, line[9:] if re.match(r"\d\d:\d\d:\d\d ", line) else line


def _short(at: datetime | None) -> str:
    return at.strftime("%d.%m %H:%M") if at else ""


def tunnel_findings(lines: list[str]) -> dict:
    """From the end of tunnel.log: when cloudflared last connected (and how), its own connectivity pre-check
    (cloudflared 2026.x: DNS, UDP and TCP 7844, Cloudflare's API - pass/fail) and its latest distinct errors."""
    connected, precheck, errors, seen = "", {}, [], set()
    for line in lines:
        if "Registered tunnel connection" in line:
            proto = re.search(r"protocol=(\w+)", line)
            connected = (_short(_local(line)[0]) or line[:8]) + (f" ({proto.group(1)})" if proto else "")
        elif m := PRECHECK.search(line):
            precheck[m.group(1)] = {"ok": m.group(3) == "pass", "details": m.group(2)}  # the latest run's wins
    day_ago = time.time() - 86400
    for line in reversed(lines):
        if " ERR " in line or "failed to" in line.lower():
            at, rest = _local(line)
            if at and at.timestamp() < day_ago:
                break  # older than a day: not today's problem
            # the same error again and again differs only by its time, connection number and address
            key = re.sub(r"\d+(\.\d+)*", "#", line.split(" ERR ", 1)[-1])[:90]
            if key not in seen:
                seen.add(key)
                errors.append((f"{_short(at)} " if at else "") + re.sub(r"\s+", " ", rest)[:240])
        if len(errors) == 5:
            break
    return {"connected": connected, "precheck": precheck, "errors": errors[::-1]}


async def report() -> dict:
    """{"verdict": key, "checks": [{"name", "ok": True/False/None (not needed), "detail"}], "tunnel": {...}, ...}"""
    s = get_settings()
    mode, url = (s.tunnel or "quick"), webapp_url()
    ts = mode == "tailscale"
    cf = mode in CLOUDFLARE or (ts and s.tunnel_backup)  # Tailscale's backup is a Cloudflare quick tunnel

    async def none():
        return None
    jobs = {
        "local": _timed(_get(f"http://127.0.0.1:{s.web_port}/healthz")),
        "internet": _timed(_get(TRACE)),
        "dns": _timed(_dns(EDGES[0])) if cf else none(),
        "api": _timed(_get(QUICK_API)) if cf and mode != "cloudflare" else none(),
        "tailscale": asyncio.to_thread(tailscale_info) if ts else none(),
        "edge1": _timed(_edge(EDGES[0])) if cf else none(),
        "edge2": _timed(_edge(EDGES[1])) if cf else none(),
        "public": _timed(address_check(url, timeout=6), 14) if url else none(),
        "version": asyncio.to_thread(cloudflared_version) if cf else none(),
    }
    got = dict(zip(jobs, await asyncio.gather(*jobs.values())))
    checks = []

    def add(name: str, ok, detail: str = "") -> None:
        checks.append({"name": name, "ok": ok, "detail": detail})

    ok, r, ms = got["local"]
    add("local", ok and r.status_code == 200, f"HTTP {r.status_code} · {ms} ms" if ok else r)
    ok, r, ms = got["internet"]
    skew = None
    if ok:
        trace = dict(line.split("=", 1) for line in r.text.splitlines() if "=" in line)
        add("internet", True, f"{ms} ms" + (f" · {trace['loc']}" if trace.get("loc") else ""))
        if trace.get("ts", "").replace(".", "", 1).isdigit():
            skew = int(time.time() - float(trace["ts"]))
    else:
        add("internet", False, r)
    if cf:
        ok, r, ms = got["dns"]
        add("dns", ok, f"{EDGES[0]} → {r}" if ok else f"{EDGES[0]}: {r}")
    if ts:
        t = got["tailscale"]
        add("tailscale", t["running"], " · ".join(x for x in (t["name"], ", ".join(t["ips"][:1])) if x) if t["running"]
            else (t["error"] or f"state {t['state']} - signed out? run scripts\\setup.bat at the computer"))
    if cf and mode != "cloudflare":
        ok, r, ms = got["api"]
        add("api", ok, f"HTTP {r.status_code} · {ms} ms" if ok else r)  # any answer: it is reachable
    if cf:
        for key, host in (("edge1", EDGES[0]), ("edge2", EDGES[1])):
            ok, r, ms = got[key]
            add(key, ok, f"{host} ({r}) · {ms} ms" if ok else f"{host}: {r}")
    if skew is not None:
        add("clock", abs(skew) < 120, f"{skew:+d} s")
    if url:
        ok, r, ms = got["public"]
        code, how = r if ok else (0, r)
        host = url.split("//", 1)[-1]
        add("public", code == 200, f"{host} · HTTP {code} · {ms} ms" + (
            " · via Cloudflare IPv4 (this network's DNS doesn't know the address yet)" if how == "edge" and code == 200
            else "")
            if code else f"{host}: {how}")
    else:
        add("public", False, "—")

    st = server_status()
    child = (st.get("children") or {}).get("tunnel") or {}
    found = tunnel_findings(tail("tunnel", 600)) if cf else {"connected": "", "precheck": {}, "errors": []}
    now = st.get("cloudflared") or {}  # what the server knows this minute (app.server.Tunnel)
    backup = st.get("backup") or {}
    tunnel = {"mode": mode, "url": url, "state": tunnel_status()["state"], "running": child.get("running"),
              "restarts": child.get("restarts"), "since": child.get("since"), "version": got["version"],
              "connected_now": now.get("connected"), "protocol": now.get("protocol"), "misses": now.get("misses"),
              "backup_on": bool(backup.get("on")), "backup_url": backup.get("url") or "", **found}

    by = {c["name"]: c["ok"] for c in checks}
    if not st:
        verdict = "server_down"
    elif not by["local"]:
        verdict = "web_down"
    elif by.get("public"):
        verdict = "ok"
    elif mode == "off":
        verdict = "off"
    elif not by["internet"]:
        verdict = "offline"
    elif ts and not by["tailscale"]:
        verdict = "tailscale"
    elif ts:
        verdict = "funnel"
    elif cf and not by["dns"]:
        verdict = "dns"
    elif cf and not by["edge1"] and not by["edge2"]:
        verdict = "port_blocked"
    elif by.get("clock") is False:
        verdict = "clock"
    elif mode == "quick" and not by["api"]:
        verdict = "api"
    else:
        verdict = "tunnel"
    return {"verdict": verdict, "checks": checks, "tunnel": tunnel, "at": int(time.time())}


def _secrets() -> list[str]:
    s = get_settings()
    return [x for x in (s.bot_token, s.cloudflare_tunnel_token) if x and len(x) > 8]


def redact(text: str) -> str:
    """Logs leave the computer (the bot sends them): no bot token, no tunnel token - even if a program printed one."""
    for secret in _secrets():
        text = text.replace(secret, "***")
    text = re.sub(r"(?<!\d)\d{6,12}:[A-Za-z0-9_-]{30,}", "***", text)  # any Telegram bot token (also in "bot<token>")
    return re.sub(r"\beyJ[A-Za-z0-9_=-]{40,}", "***", text)         # a tunnel token (base64 JSON)


def logs_text(lines: int = 300) -> str:
    parts = []
    for name in LOG_NAMES:
        got = tail(name, lines)
        parts.append(f"===== {name}.log (last {len(got)} lines) =====\n" + "\n".join(got))
    return redact("\n\n".join(parts) + "\n")


VERDICTS = {
    "ok": "The site opens on the internet - everything works.",
    "server_down": "The server program is not running on this computer.",
    "web_down": "The web server does not answer on this computer - see web.log.",
    "off": "TUNNEL=off in .env: there is no public address.",
    "offline": "This computer has no internet.",
    "dns": "This network's DNS does not resolve Cloudflare's tunnel servers.",
    "port_blocked": "The network blocks port 7844 to Cloudflare's tunnel servers - the tunnel cannot connect. "
                    "Ask the network's admin to allow outgoing TCP and UDP 7844, or use another network / TUNNEL=tailscale.",
    "clock": "This computer's clock is wrong - set the time automatically (Windows: Settings › Time).",
    "tailscale": "Tailscale is not running or is signed out on this computer - run scripts\\setup.bat there.",
    "funnel": "Tailscale runs, but its public address doesn't answer - Funnel off? (tailscale funnel status)",
    "api": "api.trycloudflare.com does not answer - Cloudflare hands out no new quick addresses right now.",
    "tunnel": "The network is fine; the tunnel itself fails - see its errors below and tunnel.log.",
}


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    r = asyncio.run(report())
    mark = {True: "OK  ", False: "FAIL", None: "--  "}
    for c in r["checks"]:
        print(f"  {mark[c['ok']]}  {c['name']:9} {c['detail']}")
    t = r["tunnel"]
    if t["backup_on"]:
        print(f"\n  backup   in use: {t['backup_url'] or 'connecting'}")
    print(f"\n  tunnel   TUNNEL={t['mode']}  cloudflared {t['version'] or '-'}  restarts {t['restarts']}"
          f"  connected now {t['connected_now']} ({t['protocol']}, failed tries {t['misses']})"
          f"  last connected {t['connected'] or 'never (in the log)'}")
    for name, p in t["precheck"].items():
        print(f"    cloudflared check: {mark[p['ok']]} {name} - {p['details']}")
    for line in t["errors"]:
        print(f"    {line}")
    print(f"\n  => {VERDICTS[r['verdict']]}")
    if "--logs" in sys.argv:
        print("\n" + logs_text())


if __name__ == "__main__":
    main()
