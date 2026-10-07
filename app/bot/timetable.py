"""📅 Dars jadvali: a student's group week from the latest EduPage snapshot - as a picture, plus the day's classes
in the caption (today's, or the next day with classes once today's are over)."""
import asyncio
from datetime import datetime
from html import escape

from app.bot.i18n import DAY_NAMES, t
from app.bot.pictures import timetable_png
from app.faculty import group_key
from app.models import Group
from app.timetable.view import Timetable, _minutes

_photos: dict[tuple, str] = {}  # (snapshot, group, language, date) -> Telegram file_id: the same picture isn't drawn twice


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


def _rows(tt: Timetable, lessons: list[dict], day: int) -> list[dict]:
    periods = {p["n"]: p for p in tt.periods}
    rows = []
    for x in sorted((x for x in lessons if x["day"] == day), key=lambda x: (x["period"], x["week"])):
        p = periods.get(x["period"], {"start": "?", "end": "?"})
        rows.append({"start": p["start"], "end": p["end"], "subject": x["subject"], "type": x["type"],
                     "week": x["week"], "room": x["room"].split(" (")[0] if x["room"] else "",
                     "teachers": [tt.teachers[i]["name"] for i in x["teachers"] if i in tt.teachers]})
    return rows


def caption_day(tt: Timetable, lessons: list[dict], lang: str, now: datetime) -> str:
    """Today's classes, or (after the last one, or on a free day) the next day that has classes."""
    days_with = sorted({x["day"] for x in lessons})
    if not days_with:
        return t(lang, "tt_free_week")
    today, minute = now.weekday(), now.hour * 60 + now.minute
    rows_today = _rows(tt, lessons, today) if today in days_with else []
    if rows_today and minute < _minutes(rows_today[-1]["end"]):
        day, when = today, t(lang, "tt_today")
    else:
        day = next((d for d in days_with if d > today), days_with[0])
        when = t(lang, "tt_tomorrow") if day == (today + 1) % 7 else ""
    name = DAY_NAMES[lang][day]
    head = f"<b>{when}, {name.lower() if lang != 'en' else name}</b>" if when else f"<b>{name}</b>"
    lines = [head]
    for i, r in enumerate(_rows(tt, lessons, day), 1):
        extra = [t(lang, f"lesson_{r['type']}")]
        if r["week"]:
            extra.append(t(lang, f"tt_week_{r['week']}"))
        room = f" · {escape(r['room'])}" if r["room"] else ""
        lines.append(f"{i}. <b>{r['start']}</b> — {escape(r['subject'])} <i>({', '.join(extra)})</i>{room}")
    return "\n".join(lines)


async def picture(tt: Timetable, gid: str, lang: str, now: datetime) -> tuple[bytes | str, str]:
    """(png bytes, or the file_id of the same picture sent before; caption)."""
    g = tt.groups[gid]
    lessons = tt.by_group[gid]
    updated = tt.fetched_at.strftime("%d.%m.%Y")
    caption = t(lang, "tt_caption", group=escape(g["name"]), day=caption_day(tt, lessons, lang, now), date=updated)
    key = (tt.id, gid, lang, now.date())
    if key in _photos:
        return _photos[key], caption
    week = tt.week(lessons, now.replace(tzinfo=None))  # the same grid as the dashboard's week view
    days = [{"name": DAY_NAMES[lang][d["n"]], "today": d["today"],
             "count": t(lang, "tt_count", n=f"{d['pairs']:g}") if d["pairs"] else "—"} for d in week["days"]]
    rows = [{"n": r["period"]["n"], "start": r["period"]["start"], "end": r["period"]["end"],
             "lunch": f"{r['lunch']['start']}–{r['lunch']['end']}" if r["lunch"] else None,
             "cells": [[_lesson(tt, x) for x in cell] for cell in r["cells"]]} for r in week["rows"]]
    about = " · ".join(x for x in (t(lang, "tt_course", n=g["course"]) if g.get("course") else "",
                                   g.get("specialty") or "") if x)
    labels = {"title": t(lang, "tt_title"), "today": t(lang, "tt_today"), "lunch": t(lang, "tt_lunch"),
              "week_A": t(lang, "tt_week_A"), "week_B": t(lang, "tt_week_B"), "room": t(lang, "tt_room"),
              **{f"type_{k}": _type_label(lang, k) for k in ("lecture", "practice", "seminar", "lab", "other")}}
    png = await asyncio.to_thread(timetable_png, group=g["name"], about=about, days=days, rows=rows, labels=labels,
                                  footer=t(lang, "tt_footer", date=updated))
    return png, caption


def remember(tt: Timetable, gid: str, lang: str, now: datetime, file_id: str) -> None:
    if len(_photos) > 500:
        _photos.clear()
    _photos[(tt.id, gid, lang, now.date())] = file_id
