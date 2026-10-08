"""Database backups made with the PostgreSQL tools on this computer - used on Windows (the server makes one every
night, app.server); Linux uses scripts/backup.sh, which writes the same files:
data/backups/feedback-<date>.sql.gz (+ media-<date>.tar.gz), the newest 14 of each kept.

    python -m app.backup                  # a copy now
    python -m app.backup list
    python -m app.backup restore <file>   # replaces ALL data; stop the server first (scripts\\server.bat stop)
    python -m app.backup transfer         # one file for moving to another computer (.env + database + uploads)
"""
import glob
import gzip
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from datetime import datetime
from pathlib import Path

from sqlalchemy.engine import make_url

from app.config import get_settings
from app.runtime import MEDIA_DIR, ROOT

BACKUPS = ROOT / "data" / "backups"
KEEP = 14
DONE = b"PostgreSQL database dump complete"
# What a new computer needs that is not on GitHub (scripts/backup.sh transfer packs the same).
TRANSFER_DIRS = ("data/media", "data/uploads", "data/runtime/chatfiles")


def pg_tool(name: str) -> str:
    """pg_dump / psql: on PATH, else the newest PostgreSQL installed in Program Files (Windows)."""
    if found := shutil.which(name):
        return found
    pattern = os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "PostgreSQL", "*", "bin", f"{name}.exe")
    found = sorted(glob.glob(pattern), key=lambda p: [int(n) for n in re.findall(r"\d+", Path(p).parents[1].name)])
    if not found:
        raise SystemExit(f"❌ {name} not found - is PostgreSQL installed? (scripts\\setup.bat installs it)")
    return found[-1]


def _connection() -> tuple[list[str], dict]:
    """Command-line arguments and environment that connect the PostgreSQL tools to the app's database."""
    url = make_url(get_settings().database_url)
    args = ["-h", url.host or "127.0.0.1", "-p", str(url.port or 5432), "-U", url.username or "postgres"]
    env = {**os.environ, "PGPASSWORD": url.password or "", "PGOPTIONS": "--client-min-messages=warning"}
    return args + ["-d", url.database or "postgres"], env


def newest() -> Path | None:
    files = sorted(BACKUPS.glob("feedback-*.sql.gz"), key=lambda p: p.stat().st_mtime)
    return files[-1] if files else None


def make() -> Path:
    """A complete copy of the database (and the uploaded pictures/videos); an incomplete one is never kept."""
    BACKUPS.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    out = BACKUPS / f"feedback-{stamp}.sql.gz"
    part = out.with_name(out.name + ".part")
    conn, env = _connection()
    tail = b""
    try:
        with subprocess.Popen([pg_tool("pg_dump"), *conn, "--clean", "--if-exists", "--no-owner"],
                              stdout=subprocess.PIPE, env=env) as dump, gzip.open(part, "wb", 9) as gz:
            while chunk := dump.stdout.read(1 << 16):
                gz.write(chunk)
                tail = (tail + chunk)[-4096:]
        if dump.returncode != 0 or DONE not in tail:  # pg_dump writes that line last
            raise RuntimeError(f"pg_dump failed (exit code {dump.returncode}) - nothing was replaced")
        os.replace(part, out)
    finally:
        part.unlink(missing_ok=True)
    if MEDIA_DIR.is_dir() and any(MEDIA_DIR.iterdir()):
        with tarfile.open(BACKUPS / f"media-{stamp}.tar.gz", "w:gz") as tar:
            tar.add(MEDIA_DIR, arcname="media")
    for kind in ("feedback-*.sql.gz", "media-*.tar.gz"):  # keep the newest KEEP of each
        for old in sorted(BACKUPS.glob(kind), key=lambda p: p.stat().st_mtime)[:-KEEP]:
            old.unlink()
    return out


def restore(file: Path) -> None:
    """Put a copy back into the database (the app's database user is enough: the copies own nothing)."""
    conn, env = _connection()
    with tempfile.TemporaryDirectory() as tmp:
        sql = Path(tmp) / "restore.sql"
        with gzip.open(file, "rb") as src, open(sql, "wb") as dst:
            for line in src:
                # \restrict / \unrestrict guard lines of newer pg_dump; older psql versions don't know them.
                if not line.startswith((b"\\restrict ", b"\\unrestrict ")):
                    dst.write(line)
        subprocess.run([pg_tool("psql"), *conn, "-q", "-v", "ON_ERROR_STOP=1", "-f", str(sql)], env=env,
                       stdout=subprocess.DEVNULL, check=True)


def transfer() -> Path:
    """.env + a fresh copy of the database + uploaded files, for scripts/setup.sh or scripts\\setup.bat elsewhere."""
    dump = make()
    out = BACKUPS / f"talaba-transfer-{datetime.now():%Y-%m-%d_%H%M}.tar.gz"
    with tarfile.open(out, "w:gz") as tar:
        tar.add(ROOT / ".env", arcname=".env")
        tar.add(dump, arcname=f"data/backups/{dump.name}")
        for d in TRANSFER_DIRS:
            if (ROOT / d).is_dir():
                tar.add(ROOT / d, arcname=d)
    return out


def main(argv: list[str]) -> None:
    command = argv[0] if argv else "now"
    if command == "now":
        out = make()
        print(f"✅ {out} ({out.stat().st_size // 1024} KB)")
    elif command == "list":
        for f in sorted(BACKUPS.glob("*.gz"), key=lambda p: p.stat().st_mtime, reverse=True):
            st = f.stat()
            print(f"{datetime.fromtimestamp(st.st_mtime):%Y-%m-%d %H:%M}  {st.st_size // 1024:>7} KB  {f.name}")
    elif command == "restore" and len(argv) == 2:
        file = Path(argv[1])
        if not file.is_file():
            raise SystemExit(f"❌ No such file: {file}")
        print(f"⚠️  This replaces ALL current data (students, ratings, settings) with the copy {file}.")
        if input("Type YES to continue: ").strip() != "YES":
            raise SystemExit("Cancelled.")
        print(f"ℹ️  The current data is saved first: {make().name}")
        restore(file)
        print(f"✅ Restored from {file}")
    elif command == "transfer":
        out = transfer()
        print(f"✅ {out} - it holds the bot token, SECRET_KEY and all student data: copy it by USB, never to GitHub.")
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main(sys.argv[1:])
