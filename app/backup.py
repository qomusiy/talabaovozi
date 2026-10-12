"""Database backups - the server (app.server) makes one every night; `scripts/server.sh` (Linux) and
`scripts\\server.bat` (Windows) run them by hand: backup | backups | restore <file> | transfer.

    python -m app.backup                  # a copy now
    python -m app.backup list
    python -m app.backup restore <file>   # replaces ALL data (the scripts stop the server around it)
    python -m app.backup transfer         # one file for moving to another computer (.env + database + uploads)

Copies are data/backups/feedback-<date>.sql.gz (+ media-<date>.tar.gz), the newest 14 of each kept. On Linux the
PostgreSQL tools of the database's Docker container are used (scripts/db.sh), on Windows those installed with it.
"""
import glob
import gzip
import os
import re
import shutil
import subprocess
import sys
import tarfile
from datetime import datetime
from pathlib import Path

from sqlalchemy.engine import make_url

from app.config import get_settings
from app.runtime import MEDIA_DIR, ROOT, SETUP_SCRIPT

BACKUPS = ROOT / "data" / "backups"
KEEP = 14
DONE = b"PostgreSQL database dump complete"
# What a new computer needs that is not on GitHub, besides .env and the database.
TRANSFER_DIRS = ("data/media", "data/uploads", "data/runtime/chatfiles")
DOCKER_DB = "feedback-db"  # the database's container on Linux (scripts/db.sh)


def pg_tool(name: str) -> str:
    """pg_dump / psql: on PATH, else the newest PostgreSQL installed in Program Files (Windows)."""
    if found := shutil.which(name):
        return found
    pattern = os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "PostgreSQL", "*", "bin", f"{name}.exe")
    found = sorted(glob.glob(pattern), key=lambda p: [int(n) for n in re.findall(r"\d+", Path(p).parents[1].name)])
    if not found:
        raise SystemExit(f"❌ {name} not found - is the database set up? ({SETUP_SCRIPT} does it)")
    return found[-1]


def in_docker(port: int | None) -> bool:
    """Is the app's database the Docker container of scripts/db.sh? Its own tools always match its version."""
    if os.name == "nt" or not shutil.which("docker"):
        return False
    published = subprocess.run(["docker", "port", DOCKER_DB, "5432"], capture_output=True, text=True).stdout.split()
    return any(p.endswith(f":{port}") for p in published)


def pg_command(name: str) -> tuple[list[str], dict | None]:
    """pg_dump / psql connected to the app's database, and the environment to run it with."""
    url = make_url(get_settings().database_url)
    user, db, quiet = url.username or "postgres", url.database or "postgres", "--client-min-messages=warning"
    if in_docker(url.port):
        return ["docker", "exec", "-i", "-e", f"PGOPTIONS={quiet}", DOCKER_DB, name, "-U", user, "-d", db], None
    env = {**os.environ, "PGPASSWORD": url.password or "", "PGOPTIONS": quiet}
    return [pg_tool(name), "-h", url.host or "127.0.0.1", "-p", str(url.port or 5432), "-U", user, "-d", db], env


def newest() -> Path | None:
    files = sorted(BACKUPS.glob("feedback-*.sql.gz"), key=lambda p: p.stat().st_mtime)
    return files[-1] if files else None


def make() -> Path:
    """A complete copy of the database (and the uploaded pictures/videos); an incomplete one is never kept."""
    BACKUPS.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    out = BACKUPS / f"feedback-{stamp}.sql.gz"
    part = out.with_name(out.name + ".part")
    pg_dump, env = pg_command("pg_dump")
    tail = b""
    try:
        with subprocess.Popen([*pg_dump, "--clean", "--if-exists", "--no-owner"], stdout=subprocess.PIPE,
                              env=env) as dump, gzip.open(part, "wb", 9) as gz:
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
    """Put a copy back into the database (the app's database user is enough: the copies own nothing).

    Everything in the database goes first - also tables the copy doesn't have (a copy from a newer or older version
    of the app, e.g. the old students table), which would otherwise block it - all in one transaction: if the copy
    fails to load, the database stays as it was."""
    psql, env = pg_command("psql")
    with gzip.open(file, "rb") as src:
        # \restrict / \unrestrict guard lines of newer pg_dump; older psql versions don't know them.
        sql = b"".join(line for line in src if not line.startswith((b"\\restrict ", b"\\unrestrict ")))
    sql = b"DROP SCHEMA IF EXISTS public CASCADE;\nCREATE SCHEMA public;\n" + sql
    subprocess.run([*psql, "-q", "-v", "ON_ERROR_STOP=1", "--single-transaction"], input=sql, env=env,
                   stdout=subprocess.DEVNULL, check=True)


def transfer() -> Path:
    """.env + a fresh copy of the database + uploaded files, for scripts/setup.sh or scripts\\setup.bat elsewhere."""
    dump = make()
    out = BACKUPS / f"talaba-transfer-{datetime.now():%Y-%m-%d_%H%M}.tar.gz"
    out.touch(mode=0o600)  # secrets inside: only this account may read it (Linux)
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
        print(f"⚠️  This replaces ALL current data (users, ratings, settings) with the copy {file}.")
        if input("Type YES (in capital letters) to continue: ").strip() != "YES":
            raise SystemExit("Cancelled.")
        print(f"ℹ️  The current data is saved first: {make().name}")
        restore(file)
        print(f"✅ Restored from {file}")
    elif command == "transfer":
        out = transfer()
        print(f"✅ {out} - it holds the bot token, SECRET_KEY and all the data: copy it by USB, never to GitHub.")
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main(sys.argv[1:])
