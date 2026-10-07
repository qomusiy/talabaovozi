"""Download the timetable from EduPage and keep the Economics Faculty part.

EduPage (https://tiiame.edupage.org/timetable/) serves the whole university timetable as JSON through the
endpoints its own web viewer uses. Its group list is split into faculty sections: a section title
("Iqtisodiyot", "Energetika", ...), then course headers ("1-bosqich", ...) each followed by that course's groups.

Storing it and updating teachers/groups/assignments from it: app.services.teaching.

We keep:
- every group in the faculty's section;
- every lesson of those groups;
- the whole week of every teacher who teaches those groups (so a teacher's timetable is complete,
  including lessons they give in other faculties - those groups are marked `faculty: false`).
"""
import re
from datetime import date

import httpx

from app.faculty import is_faculty_group

# Lesson type is the suffix of the subject name: "Makroiqtisodiyot (Ma)".
TYPE_SUFFIXES = {"Ma": "lecture", "A": "practice", "S": "seminar", "L": "lab"}
WEEKS = {"10": "A", "01": "B"}  # "11" (or empty) = every week

_GROUP = re.compile(r"^\d{2}-\d+\w?\s+[^(]+")
_COURSE = re.compile(r"^(\d)-bosqich")
_LANG_TAGS = {"ru": "ru", "rus": "ru", "ing": "en", "eng": "en", "en": "en"}


class TimetableError(Exception):
    pass


def split_subject(name: str) -> tuple[str, str]:
    """'Audit (Ma)' -> ('Audit', 'lecture');  'Ingliz tili' -> ('Ingliz tili', 'other')."""
    m = re.match(r"^(.*?)\s*\((Ma|A|S|L)\)\s*$", name.strip())
    return (m.group(1), TYPE_SUFFIXES[m.group(2)]) if m else (name.strip(), "other")


def describe_group(name: str) -> dict:
    """'25-12 BXA (ing)' -> specialty 'BXA', lang 'en';  '23-04 STMT (Amaliyotda)' -> note 'Amaliyotda'."""
    m = re.match(r"^\d{2}-\d+\w?\s+([^(]+)(.*)$", name)
    specialty = m.group(1).strip() if m else ""
    tags = re.findall(r"\(([^)]*)\)", m.group(2) if m else "")
    lang = next((_LANG_TAGS[x.lower()] for x in tags if x.lower() in _LANG_TAGS), "uz")
    notes = [x for x in tags if x.lower() not in _LANG_TAGS]
    return {"specialty": specialty, "lang": lang, "note": ", ".join(notes)}


def slug(edupage_id: str) -> str:
    """URL-friendly id: '*420' -> '420', '-663' -> 'n663' (EduPage ids start with * or -)."""
    return edupage_id.replace("*", "").replace("-", "n")


def parse(raw: dict, faculty: str) -> dict:
    """EduPage JSON -> our compact snapshot (see module docstring)."""
    try:
        tables = {t["id"]: t["data_rows"] for t in raw["r"]["dbiAccessorRes"]["tables"]}
    except (KeyError, TypeError) as e:
        raise TimetableError("Unexpected EduPage response") from e
    rows = lambda name: tables.get(name) or []  # noqa: E731
    by_id = lambda name: {r["id"]: r for r in rows(name)}  # noqa: E731

    # Groups, with their faculty section and course.
    groups: dict[str, dict] = {}
    section, course = None, None
    for c in rows("classes"):
        name = " ".join(c["name"].split())
        if m := _COURSE.match(name):
            course = int(m.group(1))
        elif _GROUP.match(name):
            groups[c["id"]] = {"id": slug(c["id"]), "name": name, "course": course, "in_section": section == faculty,
                               **describe_group(name)}
        elif name != "-":
            section, course = name, None
    ours = {gid for gid, g in groups.items() if g.pop("in_section")}
    if not ours:  # EduPage changed its sections: fall back to the specialty codes in .env
        ours = {gid for gid, g in groups.items() if is_faculty_group(g["name"])}
    if not ours:
        raise TimetableError(f"No groups of '{faculty}' found in EduPage")
    for gid, g in groups.items():
        g["faculty"] = gid in ours

    lessons = by_id("lessons")
    our_teachers = {t for lesson in lessons.values() if set(lesson["classids"]) & ours for t in lesson["teacherids"]}
    subjects, teachers, rooms = by_id("subjects"), by_id("teachers"), by_id("classrooms")

    out, unscheduled, used_groups, used_teachers = [], 0, set(ours), set(our_teachers)
    for card in rows("cards"):
        lesson = lessons.get(card["lessonid"])
        if not lesson or not (set(lesson["classids"]) & ours or set(lesson["teacherids"]) & our_teachers):
            continue
        days = card.get("days") or ""
        if not card.get("period") or "1" not in days:
            unscheduled += bool(set(lesson["classids"]) & ours)
            continue
        subject, kind = split_subject(subjects.get(lesson["subjectid"], {}).get("name", "?"))
        group_ids = [g for g in lesson["classids"] if g in groups]
        teacher_ids = [t for t in lesson["teacherids"] if t in teachers]
        used_groups.update(group_ids)
        used_teachers.update(teacher_ids)
        room = ", ".join(rooms[r]["name"] for r in card.get("classroomids") or [] if r in rooms and rooms[r]["name"] != "-")
        for day, bit in enumerate(days):
            if bit != "1":
                continue
            for k in range(int(lesson.get("durationperiods") or 1)):
                out.append({"day": day, "period": int(card["period"]) + k, "week": WEEKS.get(card.get("weeks"), ""),
                            "subject": subject, "type": kind, "room": room,
                            "teachers": [slug(t) for t in teacher_ids], "groups": [slug(g) for g in group_ids]})

    periods = sorted(({"n": int(p["period"]), "start": p["starttime"], "end": p["endtime"]} for p in rows("periods")),
                     key=lambda p: p["n"])
    return {
        "periods": periods,
        "days": [d["name"] for d in sorted(rows("days"), key=lambda d: int(d["id"]))],
        "groups": [groups[g] for g in groups if g in used_groups],
        "teachers": sorted(({"id": slug(t), "name": " ".join(teachers[t]["name"].split()), "faculty": t in our_teachers}
                            for t in used_teachers), key=lambda t: t["name"].lower()),
        "lessons": sorted(out, key=lambda x: (x["day"], x["period"], x["week"])),
        "unscheduled": unscheduled,
    }


async def _call(client: httpx.AsyncClient, url: str, args: list) -> dict:
    r = await client.post(url, json={"__args": args, "__gsh": "00000000"})
    r.raise_for_status()
    return r.json()["r"]


async def download(base_url: str) -> tuple[dict, dict]:
    """(timetable info, raw timetable) of EduPage's default timetable for the current school year."""
    today = date.today()
    school_year = today.year if today.month >= 8 else today.year - 1
    server = f"{base_url.rstrip('/')}/timetable/server"
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(60, connect=15)) as client:
            for year in (school_year, school_year - 1):
                regular = (await _call(client, f"{server}/ttviewer.js?__func=getTTViewerData", [None, year]))["regular"]
                timetables = [t for t in regular.get("timetables") or [] if not t.get("hidden")]
                if timetables:
                    info = next((t for t in timetables if t["tt_num"] == regular.get("default_num")), timetables[-1])
                    r = await client.post(f"{server}/regulartt.js?__func=regularttGetData",
                                          json={"__args": [None, info["tt_num"]], "__gsh": "00000000"})
                    r.raise_for_status()
                    return info, r.json()
    except (httpx.HTTPError, ValueError, KeyError) as e:
        raise TimetableError(f"Could not download the timetable from {base_url}: {e}") from e
    raise TimetableError(f"EduPage has no timetable for {school_year}/{school_year + 1}")

