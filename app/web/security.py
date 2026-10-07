"""Protection for the dashboard once it is reachable from the internet."""
import time
from collections import defaultdict
from urllib.parse import urlparse

from fastapi import Request

MAX_FAILURES = 5
WINDOW = 15 * 60  # seconds


def client_ip(request: Request) -> str:
    """The visitor's address; behind the Cloudflare tunnel every request comes from 127.0.0.1."""
    return (request.headers.get("cf-connecting-ip") or request.headers.get("x-forwarded-for", "").split(",")[0].strip()
            or (request.client.host if request.client else "?"))


class LoginThrottle:
    """After 5 wrong passwords (per address, and per username) logging in is blocked for 15 minutes."""

    def __init__(self):
        self.failures: dict[str, list[float]] = defaultdict(list)

    def _recent(self, key: str) -> list[float]:
        now = time.monotonic()
        self.failures[key] = [t for t in self.failures[key] if now - t < WINDOW]
        return self.failures[key]

    def blocked_for(self, *keys: str) -> int:
        """Minutes until logging in is allowed again (0 = allowed)."""
        waits = [WINDOW - (time.monotonic() - r[0]) for k in keys if len(r := self._recent(k)) >= MAX_FAILURES]
        return int(max(waits) // 60) + 1 if waits else 0

    def failed(self, *keys: str) -> None:
        for k in keys:
            self._recent(k).append(time.monotonic())

    def succeeded(self, *keys: str) -> None:
        for k in keys:
            self.failures.pop(k, None)


throttle = LoginThrottle()


def same_origin(request: Request) -> bool:
    """Forms may only be posted from the dashboard itself (a second line of defence next to SameSite cookies)."""
    origin = request.headers.get("origin") or request.headers.get("referer")
    if not origin:
        return True  # old browsers / non-browser clients; the session cookie is SameSite=Lax anyway
    return urlparse(origin).netloc == request.headers.get("host")


SECURITY_HEADERS = {
    "X-Frame-Options": "DENY",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "same-origin",
    "Cache-Control": "no-store",
}
