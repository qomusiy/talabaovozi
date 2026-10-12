"""📅 Dars jadvali: a student's group week from the latest EduPage snapshot, as one picture to keep - the same
whatever the day, so it can be saved and looked at every day."""
import asyncio
from html import escape

from app.bot.i18n import DAY_NAMES, t
from app.bot.pictures import timetable_png
from app.faculty import group_key
from app.models import Group
from app.timetable.view import Timetable

_photos: dict[tuple, str] = {}  # (snapshot, group, language, title) -> Telegram file_id: the same picture isn't drawn twice


def find_group(tt: Timetable, group: Group | None) -> str | None:
    """The timetable's id of the student's group (by EduPage id, else by name)."""
    if group is None:
        return None
    if group.edupage_id and group.edupage_id in tt.groups:
        return group.edupage_id
    key = group.key or group_key(group.name)
    return next((gid for gid, g in tt.groups.items() if key and group_key(g["name"]) == key), None)


def _type_label(lang: str, kind: str) -> str:
    label = t(lang, f"lesson_{kind}")
    return label[:1].upper() + label[1:]


def _lesson(tt: Timetable, x: dict) -> dict:
    return {"subject": x["subject"], "type": x["type"], "week": x["week"], "room": x["room"],
            "teachers": [tt.teachers[i]["name"] for i in x["teachers"] if i in tt.teachers]}


async def picture(tt: Timetable, gid: str, lang: str, title: str) -> tuple[bytes | str, str]:
    """(png bytes, or the file_id of the same picture sent before; caption). title: how the bot names the group
    ("302-guruh", or its name)."""
    g = tt.groups[gid]
    lessons = tt.by_group[gid]
    updated = tt.fetched_at.strftime("%d.%m.%Y")
    caption = t(lang, "tt_caption", group=escape(title), date=updated)
    key = (tt.id, gid, lang, title)
    if key in _photos:
        return _photos[key], caption
    week = tt.week(lessons)  # the same grid as the dashboard's week view, without "today"
    days = [{"name": DAY_NAMES[lang][d["n"]], "count": t(lang, "tt_count", n=f"{d['pairs']:g}") if d["pairs"] else "—"}
            for d in week["days"]]
    rows = [{"n": r["period"]["n"], "start": r["period"]["start"], "end": r["period"]["end"],
             "lunch": f"{r['lunch']['start']}–{r['lunch']['end']}" if r["lunch"] else None,
             "cells": [[_lesson(tt, x) for x in cell] for cell in r["cells"]]} for r in week["rows"]]
    about = " · ".join(x for x in (t(lang, "tt_course", n=g["course"]) if g.get("course") else "",
                                   g.get("specialty") or "") if x)
    labels = {"title": t(lang, "tt_title"), "lunch": t(lang, "tt_lunch"),
              "week_A": t(lang, "tt_week_A"), "week_B": t(lang, "tt_week_B"), "room": t(lang, "tt_room"),
              **{f"type_{k}": _type_label(lang, k) for k in ("lecture", "practice", "seminar", "lab", "other")}}
    png = await asyncio.to_thread(timetable_png, group=title, about=about, days=days, rows=rows, labels=labels,
                                  footer=t(lang, "tt_footer", date=updated))
    return png, caption


def remember(tt: Timetable, gid: str, lang: str, title: str, file_id: str) -> None:
    if len(_photos) > 500:
        _photos.clear()
    _photos[(tt.id, gid, lang, title)] = file_id
