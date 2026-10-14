"""Updating from GitHub (app.updater) against a throwaway "GitHub" (a bare repository), and what a database copy
holds (app.backup.summary) - for both the old layout (students) and the new one (bot users)."""
import gzip
import subprocess

import pytest

from app import backup, updater

ME = ["-c", "user.name=test", "-c", "user.email=test@example.com"]


def git(cwd, *args) -> str:
    return subprocess.run(["git", *ME, *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


def push(work, path: str, text: str, message: str) -> str:
    (work / path).write_text(text)
    git(work, "add", "-A")
    git(work, "commit", "-qm", message)
    git(work, "push", "-q", "origin", "HEAD:main")
    return git(work, "rev-parse", "HEAD")


@pytest.fixture
def repos(tmp_path, monkeypatch):
    """(a developer's clone, the server's clone) of one "GitHub" repository."""
    remote, work, here = tmp_path / "remote.git", tmp_path / "work", tmp_path / "here"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(remote)], check=True)
    subprocess.run(["git", "clone", "-q", str(remote), str(work)], check=True, capture_output=True)
    git(work, "checkout", "-q", "-b", "main")
    (work / "requirements.txt").write_text("fastapi\n")
    push(work, "app.txt", "v1\n", "first")
    subprocess.run(["git", "clone", "-q", str(remote), str(here)], check=True)
    monkeypatch.setattr(updater, "ROOT", here)
    monkeypatch.setattr(updater, "STATE_FILE", tmp_path / "update_state.json")
    monkeypatch.setattr(updater, "FAILED_FILE", tmp_path / "update_failed.json")
    monkeypatch.setattr(updater, "VERSION_FILE", tmp_path / "version.json")
    monkeypatch.setattr(updater, "self_check", lambda: None)
    monkeypatch.setattr(updater.backup, "make", lambda: tmp_path / "copy.sql.gz")
    monkeypatch.setattr(updater, "pip_install", lambda: None)
    return work, here


def test_an_update_moves_the_code_forward_after_a_copy(repos):
    work, here = repos
    with pytest.raises(updater.NothingToDo):
        updater.prepare()
    new = push(work, "app.txt", "v2\n", "Better survey page")
    info = updater.check()
    assert info["behind"] == 1 and info["commits"][0]["subject"] == "Better survey page" and not info["error"]
    state = updater.prepare("req-1")
    assert git(here, "rev-parse", "HEAD") == new and (here / "app.txt").read_text() == "v2\n"
    assert state["phase"] == "restart" and state["entry"] == "req-1" and state["backup"].endswith("copy.sql.gz")
    assert updater.load_state()["to"] == new and not state["requirements"]


def test_an_update_refuses_hand_edits_a_broken_version_and_a_failed_one(repos, monkeypatch):
    work, here = repos
    start = git(here, "rev-parse", "HEAD")
    push(work, "app.txt", "v2\n", "v2")
    (here / "app.txt").write_text("edited on the server\n")
    with pytest.raises(updater.UpdateError, match="app.txt"):
        updater.prepare()
    git(here, "checkout", "--", ".")

    def broken():
        raise updater.UpdateError("the new version does not load: SyntaxError")
    monkeypatch.setattr(updater, "self_check", broken)
    with pytest.raises(updater.UpdateError, match="previous version is back"):
        updater.prepare()
    assert git(here, "rev-parse", "HEAD") == start and updater.load_state() is None

    # It loads, but doesn't run properly: the launcher puts it back - and that version isn't tried again.
    monkeypatch.setattr(updater, "self_check", lambda: None)
    monkeypatch.setattr(updater, "database_at_head", lambda: True)
    state = updater.prepare()
    assert "code back" in updater.revert(state, failed=True)
    assert git(here, "rev-parse", "HEAD") == start and updater.check(fetch=False)["failed"]
    with pytest.raises(updater.UpdateError, match="did not run properly before"):
        updater.prepare()
    push(work, "app.txt", "v3\n", "fixed")  # a newer one is fine
    assert updater.prepare()["to"] == git(work, "rev-parse", "HEAD")


def test_a_rollback_restores_the_database_only_if_the_new_version_changed_it(repos, monkeypatch):
    work, here = repos
    push(work, "requirements.txt", "fastapi\nhttpx\n", "new package")
    restored, installed = [], []
    monkeypatch.setattr(updater, "pip_install", lambda: installed.append(1))
    monkeypatch.setattr(updater.backup, "restore", lambda p: restored.append(p.name))
    state = updater.prepare()
    assert state["requirements"] and installed == [1]          # requirements.txt changed: new packages
    monkeypatch.setattr(updater, "database_at_head", lambda: False)   # the new version had updated the database
    note = updater.revert(state)
    assert restored == ["copy.sql.gz"] and "database restored" in note and installed == [1, 1]


def test_commits_made_on_the_server_stop_an_update(repos):
    work, here = repos
    push(work, "app.txt", "v2\n", "v2")
    git(here, "commit", "-q", "--allow-empty", "-m", "made on the server")
    with pytest.raises(updater.UpdateError, match="history"):
        updater.prepare()


def _dump(path, tables: dict[str, tuple[list[str], list[list[str]]]]):
    lines = ["-- PostgreSQL database dump\n"]
    for name, (cols, rows) in tables.items():
        lines.append(f"COPY public.{name} ({', '.join(cols)}) FROM stdin;\n")
        lines += ["\t".join(r) + "\n" for r in rows]
        lines.append("\\.\n")
    with gzip.open(path, "wt", encoding="utf-8") as f:
        f.writelines(lines)
    return path


def test_what_a_copy_holds_old_and_new_layout(tmp_path):
    camps = (["id", "title", "is_demo"], [["1", "Real", "f"], ["2", "Demo", "t"]])
    new = _dump(tmp_path / "new.sql.gz", {
        "alembic_version": (["version_num"], [["e7a2c4d9f3b1"]]),
        "admins": (["id", "username"], [["1", "boss"]]),
        "bot_users": (["id", "first_name"], [["777", "Aziz"], ["-5", "demo"]]),
        "survey_campaigns": camps,
        "feedback": (["id", "campaign_id", "created_at"], [["1", "1", "2026-10-12 09:26:00+00"],
                                                          ["2", "2", "2026-10-13 09:00:00+00"]]),
        "bot_messages": (["id", "at"], [["1", "2026-10-12 10:29:12.5+00"]])})
    s = backup.summary(new)
    assert (s["version"], s["admins"], s["people"], s["ratings"]) == ("e7a2c4d", 1, 1, 1)  # no demo
    assert s["last_rating"].startswith("2026-10-12") and s["last_message"].startswith("2026-10-12")
    old = _dump(tmp_path / "old.sql.gz", {
        "alembic_version": (["version_num"], [["c5e9a3b7d2f1"]]),
        "students": (["id", "telegram_id"], [["1", "777"], ["2", "\\N"]]),
        "survey_campaigns": camps, "feedback": (["id", "campaign_id", "created_at"], [])})
    s = backup.summary(old)
    assert (s["version"], s["people"], s["ratings"], s["last_rating"]) == ("c5e9a3b", 1, 0, "")
    assert "1 people in the bot" in backup.describe(old)
