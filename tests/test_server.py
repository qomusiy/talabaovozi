"""The Windows server program (app.server) and its backups (app.backup)."""
import asyncio
import os
import shutil
from datetime import datetime

import pytest
from sqlalchemy import delete, select

from app import backup, server
from app.models import Department


async def test_backup_and_restore_with_the_apps_own_database_user(session, tmp_path, monkeypatch):
    if not shutil.which("pg_dump"):
        pytest.skip("pg_dump is not installed here")
    monkeypatch.setattr(backup, "BACKUPS", tmp_path)
    monkeypatch.setattr(backup, "MEDIA_DIR", tmp_path / "media")
    for day in range(1, 16):  # older copies: only the newest 14 are kept
        old = tmp_path / f"feedback-2020-01-{day:02d}_0330.sql.gz"
        old.write_bytes(b"")
        os.utime(old, (day, day))
    session.add(Department(name="Iqtisodiyot kafedrasi"))
    await session.commit()

    out = await asyncio.to_thread(backup.make)
    assert backup.newest() == out and len(list(tmp_path.glob("feedback-*.sql.gz"))) == 14

    await session.execute(delete(Department))
    await session.commit()
    await asyncio.to_thread(backup.restore, out)
    assert (await session.execute(select(Department.name))).scalars().all() == ["Iqtisodiyot kafedrasi"]


def test_nightly_backup_is_due_once_after_half_past_three():
    day = datetime(2026, 10, 8)
    assert not server.backup_due(day.replace(hour=3), None)
    assert server.backup_due(day.replace(hour=3, minute=30), None)
    assert server.backup_due(day.replace(hour=9), day.replace(day=7, hour=3, minute=31))  # was off at night
    assert not server.backup_due(day.replace(hour=9), day.replace(hour=3, minute=31))


def test_quick_tunnel_address_is_published_and_replaced_when_cloudflare_drops_it(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "WEBAPP_URL_FILE", tmp_path / "webapp_url")
    monkeypatch.setattr(server, "TUNNEL_STATUS_FILE", tmp_path / "tunnel_status")
    monkeypatch.setattr(server, "LOGS", tmp_path)
    tunnel = server.Tunnel("quick")
    tunnel.started()
    tunnel.on_line("INF |  https://two-calm-words.trycloudflare.com                    |")
    assert (tmp_path / "webapp_url").read_text() == "https://two-calm-words.trycloudflare.com"

    stopped = []
    monkeypatch.setattr(tunnel.child, "stop", lambda: stopped.append(True))
    tunnel.on_line('ERR Register tunnel error error="Tunnel not found"')
    assert stopped and (tmp_path / "tunnel_status").read_text().startswith("starting|")
