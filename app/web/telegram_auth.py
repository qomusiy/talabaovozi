"""Verify Telegram Mini App `initData` (https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app)."""
import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl

MAX_AGE_SECONDS = 24 * 3600


def verify_init_data(init_data: str, bot_token: str, max_age: int = MAX_AGE_SECONDS) -> dict | None:
    """Returns the Telegram user dict if the data was signed by Telegram for this bot, else None."""
    try:
        fields = dict(parse_qsl(init_data, strict_parsing=True))
    except ValueError:
        return None
    received_hash = fields.pop("hash", None)
    if not received_hash or not bot_token:
        return None
    check_string = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    expected = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, received_hash):
        return None
    if time.time() - int(fields.get("auth_date", 0)) > max_age:
        return None
    try:
        return json.loads(fields["user"])
    except (KeyError, ValueError):
        return None


def sign_init_data(user: dict, bot_token: str, auth_date: int | None = None) -> str:
    """Build valid initData - used by tests to simulate Telegram."""
    from urllib.parse import urlencode

    fields = {"auth_date": str(auth_date or int(time.time())), "user": json.dumps(user)}
    check_string = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    fields["hash"] = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
    return urlencode(fields)
