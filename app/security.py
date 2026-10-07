import hashlib
import hmac
import re
import secrets

from app.config import get_settings

_PASSPORT_RE = re.compile(r"^[A-Z]{2}\d{7}$")


def normalize_passport(raw: str) -> str:
    """'as 348 0990' -> 'AS3480990'. Also maps Cyrillic look-alike letters to Latin."""
    lookalikes = str.maketrans("АВСЕНКМОРТХ", "ABCEHKMOPTX")
    return re.sub(r"[\s\-]", "", str(raw)).upper().translate(lookalikes)


def is_valid_passport(normalized: str) -> bool:
    return bool(_PASSPORT_RE.match(normalized))


def hash_passport(raw: str) -> str:
    """Keyed hash of the passport code. We never store the passport itself."""
    key = get_settings().secret_key.encode()
    return hmac.new(key, normalize_passport(raw).encode(), hashlib.sha256).hexdigest()


def verify_passport(raw: str, stored_hash: str) -> bool:
    return hmac.compare_digest(hash_passport(raw), stored_hash)


def temporary_passport(hemis_id: str) -> str:
    """Stand-in passport code until the real ones are imported, e.g. 'KT4081537'.

    Derived from the HEMIS id with SECRET_KEY: stable, not guessable, and admins can look it up in the
    dashboard (Students page) to test the bot.
    """
    digest = hmac.new(get_settings().secret_key.encode(), f"temporary:{hemis_id}".encode(), hashlib.sha256).digest()
    letters = "ABCDEFGHJKLMNPRSTUVXYZ"  # no I/O/Q/W, which are easy to misread
    number = int.from_bytes(digest[2:10], "big") % 10_000_000
    return f"{letters[digest[0] % len(letters)]}{letters[digest[1] % len(letters)]}{number:07d}"


def normalize_hemis(raw) -> str:
    """Excel often turns long IDs into floats ('368211100123.0') - strip that."""
    s = str(raw).strip()
    if s.endswith(".0"):
        s = s[:-2]
    return re.sub(r"\s", "", s)


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    return f"scrypt${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, salt, digest = stored.split("$")
    except ValueError:
        return False
    candidate = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=2**14, r=8, p=1)
    return hmac.compare_digest(candidate.hex(), digest)
