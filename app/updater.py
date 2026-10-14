"""Updating the server from GitHub, safely - used by the launcher (app.server), which runs as long as the computer is on.

prepare(), before the new version runs:
  1. refuse if code files were changed on this computer by hand, or GitHub's history doesn't simply continue this one;
  2. a database copy (data/backups) - never an update without one;
  3. move the code forward (git merge --ff-only), new packages if requirements.txt changed;
  4. check that the new code loads at all and its database updates are in order - if not, straight back.
Then the launcher starts the new version and watches it. If it doesn't come up healthy, revert() puts back the code,
the packages and - only if the new version had already changed the database - the database from that copy.

The server may run as another account than the one that cloned the folder (Windows: SYSTEM), so git is told the folder
is safe, never asks for a password (a public repository needs none) and never opens a window.
"""
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from app import backup
from app.runtime import ROOT, VERSION_FILE

STATE_FILE = ROOT / "data" / "runtime" / "update_state.json"   # an update in progress (survives a restart)
FAILED_FILE = ROOT / "data" / "runtime" / "update_failed.json"  # versions that were put back: not tried again
PY = sys.executable
SEP = "\x1f"


class UpdateError(Exception):
    """The update can't go on - the code is as it was before."""


class NothingToDo(Exception):
    """Already the newest version."""


def child_env() -> dict:
    return {**os.environ, "PYTHONUTF8": "1", "PYTHONUNBUFFERED": "1", "GIT_TERMINAL_PROMPT": "0"}


def git_exe() -> str | None:
    if found := shutil.which("git"):
        return found
    for base in (os.environ.get("ProgramFiles", ""), os.environ.get("ProgramW6432", ""), r"C:\Program Files"):
        if base and (exe := Path(base) / "Git" / "cmd" / "git.exe").is_file():
            return str(exe)
    return None


def _run(cmd: list[str], timeout: int) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(cmd, cwd=ROOT, env=child_env(), capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired:
        raise UpdateError(f"no answer within {timeout} s from: {' '.join(cmd[-3:])}")
    except OSError as e:
        raise UpdateError(f"{cmd[0]}: {e}")


def _last_line(r: subprocess.CompletedProcess) -> str:
    lines = [x.strip() for x in (r.stderr or r.stdout or "").splitlines() if x.strip()]
    return lines[-1] if lines else f"exit code {r.returncode}"


def _git(args: list[str], timeout: int = 120) -> subprocess.CompletedProcess:
    exe = git_exe()
    if not exe:
        raise UpdateError("git is not installed on this computer")
    return _run([exe, "-c", "safe.directory=*", "-c", "credential.helper=", "-c", "core.quotepath=off", *args], timeout)


def git(*args: str, timeout: int = 120) -> str:
    r = _git(list(args), timeout)
    if r.returncode != 0:
        raise UpdateError(f"git {args[0]}: {_last_line(r)}")
    return r.stdout.strip()


def git_ok(*args: str) -> bool:
    return _git(list(args)).returncode == 0


# ---------------------------------------------------------------- what runs, and what GitHub has

def current() -> dict:
    commit, short, date, subject = git("log", "-1", f"--format=%H{SEP}%h{SEP}%cI{SEP}%s").split(SEP, 3)
    return {"commit": commit, "short": short, "date": date, "subject": subject}


def upstream() -> str:
    """The GitHub branch this one follows (origin/main)."""
    try:
        return git("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}")
    except UpdateError:
        return "origin/" + git("rev-parse", "--abbrev-ref", "HEAD")


def write_version(info: dict) -> None:
    """Never raises: Windows refuses to replace a file while the web server reads it - so it tries a few times."""
    try:
        VERSION_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = VERSION_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(info, ensure_ascii=False), encoding="utf-8")
        for _ in range(50):
            try:
                os.replace(tmp, VERSION_FILE)
                return
            except PermissionError:
                time.sleep(0.1)
    except OSError:
        pass


def check(fetch: bool = True) -> dict:
    """What runs here and what GitHub has that this computer doesn't (written to VERSION_FILE for the dashboard and
    the bot). Never raises: a problem is in "error"."""
    info = {"checked": int(time.time()), "current": None, "behind": 0, "commits": [], "ahead": 0, "failed": False,
            "error": ""}
    try:
        info["current"] = current()
        up = upstream()
        if fetch:
            git("fetch", "--quiet", up.split("/", 1)[0], timeout=120)
        log = git("log", f"--format=%h{SEP}%cI{SEP}%s", f"HEAD..{up}")
        info["commits"] = [dict(zip(("short", "date", "subject"), line.split(SEP, 2))) for line in log.splitlines()]
        info["behind"] = len(info["commits"])
        info["ahead"] = int(git("rev-list", "--count", f"{up}..HEAD"))  # commits made here, not on GitHub
        info["failed"] = bool(info["behind"]) and git("rev-parse", up) in failed_versions()  # tried, put back
    except (UpdateError, ValueError) as e:
        info["error"] = str(e)
    write_version(info)
    return info


def local_changes() -> list[str]:
    """Code files changed on this computer by hand (an update would overwrite them, so it refuses)."""
    r = _git(["status", "--porcelain", "--untracked-files=no"])
    if r.returncode != 0:
        raise UpdateError(f"git status: {_last_line(r)}")
    return [line[3:] for line in r.stdout.splitlines() if line.strip()]  # "XY path": not stripped, X may be a space


# ---------------------------------------------------------------- an update

def save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state), encoding="utf-8")
    os.replace(tmp, STATE_FILE)


def load_state() -> dict | None:
    try:
        state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        return state if isinstance(state, dict) and state.get("from") else None
    except (OSError, ValueError):
        return None


def clear_state() -> None:
    STATE_FILE.unlink(missing_ok=True)


def pip_install() -> None:
    r = _run([PY, "-m", "pip", "install", "-q", "--disable-pip-version-check", "-r", "requirements.txt"], 1800)
    if r.returncode != 0:
        raise UpdateError(f"installing the packages failed: {_last_line(r)}")


def self_check() -> None:
    """Does the code on disk load at all - the launcher, the server, the web server, the bot - and are its database
    updates in order (one line of them)? Catches a broken version before anything is restarted."""
    imports = "import app.server, app.updater, app.web.main, app.bot.__main__, app.cli"
    r = _run([PY, "-X", "utf8", "-c", imports], 300)
    if r.returncode != 0:
        raise UpdateError(f"the new version does not load: {_last_line(r)}")
    r = _run([PY, "-m", "alembic", "heads"], 120)
    heads = [line for line in r.stdout.splitlines() if line.strip()]
    if r.returncode != 0 or len(heads) != 1:
        raise UpdateError("the new version's database updates are not in order: "
                          + (_last_line(r) if r.returncode else f"{len(heads)} heads"))


def prepare(entry_id: str = "") -> dict:
    """Everything up to restarting the server; returns the update's state (for watch and revert). Raises
    NothingToDo, or UpdateError with the code as it was."""
    if changed := local_changes():
        raise UpdateError("code files were changed on this computer: " + ", ".join(changed[:4])
                          + (" …" if len(changed) > 4 else "") + " - undo that first (git checkout -- .)")
    info = check()
    if info["error"]:
        raise UpdateError(f"could not reach GitHub: {info['error']}")
    if not info["behind"]:
        raise NothingToDo("already the newest version")
    up = upstream()
    start, target = git("rev-parse", "HEAD"), git("rev-parse", up)
    if target in failed_versions():
        raise UpdateError(f"version {target[:7]} did not run properly before and was put back - "
                          "waiting for a newer one on GitHub")
    if not git_ok("merge-base", "--is-ancestor", start, target):
        raise UpdateError("GitHub's history doesn't continue this computer's (commits made here?) - update by hand")
    try:
        copy = backup.make()
    except (Exception, SystemExit) as e:
        raise UpdateError(f"no database copy could be made ({e}) - nothing was changed")
    state = {"from": start, "to": target, "entry": entry_id, "backup": str(copy), "at": int(time.time()),
             "requirements": not git_ok("diff", "--quiet", start, target, "--", "requirements.txt"), "phase": "code"}
    save_state(state)
    try:
        git("merge", "--ff-only", "--quiet", target)
        if state["requirements"]:
            pip_install()
        self_check()
    except UpdateError as e:
        try:
            revert_code(state)
        finally:
            clear_state()
        raise UpdateError(f"{e} - the previous version is back")
    state["phase"] = "restart"
    save_state(state)
    check(fetch=False)
    return state


def revert_code(state: dict) -> None:
    git("reset", "--hard", "--quiet", state["from"])
    if state.get("requirements"):
        pip_install()


def database_at_head() -> bool | None:
    """With the code on disk: is the database at its newest update (True), at one this code doesn't know - the
    new version changed it (False)? None: the database can't be asked."""
    r = _run([PY, "-m", "alembic", "current"], 120)
    if r.returncode == 0:
        return "(head)" in r.stdout
    return False if "Can't locate revision" in (r.stderr + r.stdout) else None


def failed_versions() -> list[str]:
    try:
        found = json.loads(FAILED_FILE.read_text(encoding="utf-8"))
        return found if isinstance(found, list) else []
    except (OSError, ValueError):
        return []


def revert(state: dict, failed: bool = False) -> str:
    """Put the version from before the update back (the server must be stopped). Returns what was done.
    failed: the new version didn't run properly - it isn't tried again (a newer one is)."""
    if failed:
        FAILED_FILE.parent.mkdir(parents=True, exist_ok=True)
        FAILED_FILE.write_text(json.dumps((failed_versions() + [state["to"]])[-20:]), encoding="utf-8")
    notes = []
    revert_code(state)
    notes.append(f"code back at {state['from'][:7]}")
    at_head = database_at_head()
    if at_head is False:
        backup.restore(Path(state["backup"]))
        notes.append(f"database restored from {Path(state['backup']).name} (changes since the update are lost)")
    elif at_head is None:
        notes.append("the database could not be checked - if the server doesn't start, restore "
                     + Path(state["backup"]).name)
    clear_state()
    check(fetch=False)
    return "; ".join(notes)
