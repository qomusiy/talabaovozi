"""The public address (app.server.Tunnel) and the diagnostics that say why it doesn't open (app.diagnose)."""
from datetime import datetime, timedelta, timezone

import pytest

from app import diagnose, server

NOW = datetime.now(timezone.utc)
OLD = (NOW - timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
AT = (NOW - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
LOG = [  # what cloudflared prints, as tunnel.log keeps it (our time first)
    f'21:00:00 {OLD} ERR Serve tunnel error error="connection with edge closed" connIndex=0',  # two days ago
    f"21:16:01 {AT} INF |  https://gaming-immigrants-sie-interest.trycloudflare.com    |",
    f'21:16:05 {AT} INF precheck component="UDP Connectivity" details="QUIC connection failed" '
    "run_id=1 status=fail target=region1.v2.argotunnel.com:7844",
    f'21:16:05 {AT} INF precheck component="TCP Connectivity" details="HTTP/2 connection is blocked or '
    'unreachable" run_id=1 status=fail target=region1.v2.argotunnel.com:7844',
    f'21:16:20 {AT} ERR Unable to establish connection with Cloudflare edge error="DialContext error: '
    'dial tcp 198.41.192.7:7844: i/o timeout" connIndex=0 event=0 ip=198.41.192.7',
    f'21:16:35 {AT} ERR Unable to establish connection with Cloudflare edge error="DialContext error: '
    'dial tcp 198.41.200.13:7844: i/o timeout" connIndex=0 event=0 ip=198.41.200.13',
]
URL_LINE = LOG[1]


@pytest.fixture
def tunnel(tmp_path, monkeypatch):
    said, published = [], []
    monkeypatch.setattr(server, "say", said.append)
    monkeypatch.setattr(server, "write_url", published.append)
    monkeypatch.setattr(server, "TUNNEL_STATUS_FILE", tmp_path / "tunnel_status")
    monkeypatch.setattr(server, "TUNNEL_RESTART_FILE", tmp_path / "tunnel_restart")
    t = server.Tunnel("quick")
    t.said, t.published = said, published
    return t


def test_a_quick_address_is_handed_out_only_once_connected(tunnel):
    assert tunnel.command()[3:5] == ["--protocol", "http2"]
    tunnel.started()
    tunnel.on_line(URL_LINE)
    assert tunnel.url == "https://gaming-immigrants-sie-interest.trycloudflare.com" and tunnel.published == []
    tunnel.on_line("2026-10-20T16:16:09Z INF Registered tunnel connection connIndex=0 connection=5774acb9 "
                   "event=0 ip=198.41.200.193 location=waw06 protocol=http2")
    assert tunnel.connected and tunnel.published == [tunnel.url]
    assert tunnel.ended(0) == 0 and tunnel.protocol == "http2"   # it had worked: same protocol, no pause


def test_a_tunnel_that_never_connects_tries_the_other_protocol_further_apart(tunnel):
    waits = []
    for _ in range(6):
        tunnel.started()
        tunnel.on_line(URL_LINE)
        waits.append((tunnel.protocol, tunnel.ended(1)))
    assert waits == [("http2", 0), ("quic", 60), ("http2", 120), ("quic", 240), ("http2", 480), ("quic", 600)]
    assert tunnel.published == [] and "Port 7844" in tunnel.said[-1]
    tunnel.started()
    tunnel.connect()                                               # connected (over http2 now): back to normal
    assert tunnel.misses == 0 and tunnel.ended(0) == 0


class Done(Exception):
    pass


async def test_a_tunnel_that_answers_counts_as_connected(tunnel, monkeypatch):
    """Even if cloudflared's words change one day: an address that answers is handed out."""
    async def answers(url, timeout):
        return 200, "edge"   # this computer reaches it only through Cloudflare's IPv4 edge: still a working one

    rounds = []

    async def sleep(_):  # one round of the watch, then stop
        rounds.append(1)
        if len(rounds) > 1:
            raise Done
    monkeypatch.setattr(server, "address_check", answers)
    monkeypatch.setattr(server.asyncio, "sleep", sleep)
    tunnel.started()
    tunnel.on_line(URL_LINE)
    tunnel.since -= 61                                             # past the first minute
    tunnel.child.proc = type("P", (), {"returncode": None})()      # cloudflared runs
    with pytest.raises(Done):
        await tunnel.watch()
    assert tunnel.connected and tunnel.published == [tunnel.url]


def test_the_address_check_is_not_the_update_check():
    assert server.ADDRESS_CHECK_EVERY == 60 and server.CHECK_EVERY == 6 * 3600


def test_tunnel_log_findings():
    found = diagnose.tunnel_findings(LOG)
    assert found["connected"] == ""
    assert found["precheck"] == {"UDP Connectivity": {"ok": False, "details": "QUIC connection failed"},
                                 "TCP Connectivity": {"ok": False,
                                                      "details": "HTTP/2 connection is blocked or unreachable"}}
    [error] = found["errors"]                    # the same error twice is shown once, one from 2 days ago not at all
    local = (NOW - timedelta(minutes=5)).astimezone().strftime("%d.%m %H:%M")
    assert "i/o timeout" in error and error.startswith(local + " ERR") and AT not in error


def test_logs_leave_without_secrets(monkeypatch):
    monkeypatch.setattr(diagnose, "_secrets", lambda: ["s3cr3t-token-value"])
    text = diagnose.redact("token s3cr3t-token-value, url https://api.telegram.org/bot123456789:"
                           "AAHk0Lw-abcdefghijklmnopqrstuvwxyz12/getMe, eyJhIjoiMTIzIiwidCI6IjQ1NiIsInMiOiJ4eXoifQabc")
    assert "s3cr3t" not in text and "AAHk0Lw" not in text and "eyJhIjoi" not in text and text.count("***") == 3


@pytest.mark.parametrize("edges, public, verdict", [((False, False), False, "port_blocked"),
                                                    ((True, True), False, "tunnel"),
                                                    ((True, False), True, "ok")])
async def test_the_verdict(monkeypatch, runtime_files, edges, public, verdict):
    import json
    import time

    import app.runtime
    app.runtime.SERVER_STATUS_FILE.write_text(json.dumps({"at": int(time.time()), "children": {}}))
    monkeypatch.setattr(diagnose, "server_status", app.runtime.server_status)
    monkeypatch.setattr(diagnose, "webapp_url", lambda: "https://x.trycloudflare.com")
    monkeypatch.setattr(diagnose, "tail", lambda name, lines: LOG)
    monkeypatch.setattr(diagnose, "cloudflared_version", lambda: "2026.9.3")

    class R:
        def __init__(self, code, text=""):
            self.status_code, self.text = code, text

    async def get(url):
        return R(200 if "127.0.0.1" in url else 405, f"loc=UZ\nts={time.time()}")

    async def public_check(url, timeout):
        return (200, "edge") if public else (0, "All connection attempts failed")

    async def edge(host):
        if not edges[diagnose.EDGES.index(host)]:
            raise TimeoutError
        return "198.41.192.7"

    async def dns(host):
        return "198.41.192.7"
    monkeypatch.setattr(diagnose, "_get", get)
    monkeypatch.setattr(diagnose, "address_check", public_check)
    monkeypatch.setattr(diagnose, "_edge", edge)
    monkeypatch.setattr(diagnose, "_dns", dns)
    r = await diagnose.report()
    assert r["verdict"] == verdict
    if public:
        assert "via Cloudflare IPv4" in next(c["detail"] for c in r["checks"] if c["name"] == "public")
    assert {c["name"] for c in r["checks"]} == {"local", "internet", "dns", "api", "edge1", "edge2", "clock", "public"}


async def test_an_address_this_network_cant_resolve_is_asked_through_cloudflare(monkeypatch):
    import asyncio
    import socket

    import httpx

    from app import runtime
    asked = []

    class Client:
        def __init__(self, **kw): ...
        async def __aenter__(self): return self
        async def __aexit__(self, *a): ...

        async def get(self, url, headers=None, extensions=None):
            asked.append((url, headers, extensions))
            if "104.16.230.132" not in url:
                raise httpx.ConnectError("All connection attempts failed")   # only IPv6 in this network's DNS
            return type("R", (), {"status_code": 200 if headers["Host"].startswith("live-") else 530})()

    async def resolve(host, port, family=0, type=0):
        assert host == "api.trycloudflare.com" and family == socket.AF_INET
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("104.16.230.132", 443))]
    monkeypatch.setattr(runtime.httpx, "AsyncClient", Client)
    monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", resolve)
    assert await runtime.address_check("https://live-one.trycloudflare.com") == (200, "edge")
    assert asked[-1][1] == {"Host": "live-one.trycloudflare.com"}
    assert asked[-1][2] == {"sni_hostname": "live-one.trycloudflare.com"}
    assert not await runtime.address_answers("https://dead-one.trycloudflare.com")      # 530: Cloudflare says dead
    code, why = await runtime.address_check("https://talaba.example.uz")                # not a quick address
    assert code == 0 and "All connection attempts failed" in why and len(asked) == 5   # no detour for it


def test_cloudflares_own_address_in_an_error_is_not_the_tunnels(tunnel):
    tunnel.started()
    tunnel.on_line('failed to request quick Tunnel: Post "https://api.trycloudflare.com/tunnel": context deadline '
                   "exceeded (Client.Timeout exceeded while awaiting headers)")
    assert tunnel.url == ""
    tunnel.on_line(URL_LINE)
    assert tunnel.url == "https://gaming-immigrants-sie-interest.trycloudflare.com"
