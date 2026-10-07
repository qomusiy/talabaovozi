"""Teachers, groups and teaching assignments, kept in line with the timetable.

The timetable (downloaded from EduPage, or uploaded as Excel) says who teaches which subject to which group.
Whenever a new timetable is stored:
- the faculty's groups are created/updated (timetable name, course, language, EduPage id),
- the faculty's teachers are created/updated (a fuller name uploaded from Excel is kept),
- the current semester's assignments - which decide whom each student rates - are rebuilt from it,
  unless the admins chose to upload assignments as Excel instead (setting `assignments_source`).
"""
import re
from datetime import datetime, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import settings_store
from app.config import get_settings
from app.faculty import display_code, group_key
from app.models import (Group, ImportLog, Semester, Student, Subject, SurveyCampaign, Teacher, TeachingAssignment,
                        TimetableSnapshot)
from app.services import departments
from app.timetable import edupage

KEEP_SNAPSHOTS = 5


def name_key(name: str | None) -> str:
    """'Abdug‘aniyev  A.A' -> "abdug'aniyev aa" (case, apostrophes, dots and spacing don't matter)."""
    s = re.sub("[‘’ʻʼ`]", "'", (name or "").lower()).replace(".", " ")
    words = s.split()
    # Initials written with spaces ("A A") are joined, so "Abdug'aniyev A.A" == "Abdug'aniyev AA".
    if len(words) > 2 and all(len(w) == 1 for w in words[1:]):
        words = [words[0], "".join(words[1:])]
    return " ".join(words)


def teacher_name_keys(full_name: str) -> set[str]:
    """Every way a timetable may write this name: 'Qodirov Rustam Sobirovich' -> qodirov rustam, qodirov rs, ..."""
    key = name_key(full_name)
    words = key.split()
    keys = {key}
    if len(words) >= 2:
        surname, rest = words[0], words[1:]
        keys |= {f"{surname} {rest[0]}", f"{surname} {rest[0][0]}", f"{surname} {''.join(w[0] for w in rest)}"}
    return keys


def _now_text() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


async def current_semester(session: AsyncSession) -> Semester | None:
    return await session.scalar(select(Semester).where(Semester.is_current))


# ---------------------------------------------------------------- Timetable -> groups, teachers

async def _sync_groups(session: AsyncSession, data: dict) -> dict[str, Group]:
    """Timetable group id -> Group row, for the faculty's groups."""
    existing = list((await session.execute(select(Group))).scalars())
    by_key = {g.key or group_key(g.name): g for g in existing}
    by_edupage = {g.edupage_id: g for g in existing if g.edupage_id}
    by_name = {g.name: g for g in existing}
    out: dict[str, Group] = {}
    for g in data["groups"]:
        if not g["faculty"]:
            continue
        key = group_key(g["name"]) or g["name"]
        group = by_key.get(key) or (by_edupage.get(g["id"]) if data.get("source") == "edupage" else None)
        if group is None:
            group = by_name.get(g["name"]) or Group(name=g["name"])
            session.add(group)
        if data.get("source") == "edupage" and group.edupage_id != g["id"]:
            if (other := by_edupage.get(g["id"])) and other is not group:
                other.edupage_id = None
            group.edupage_id = g["id"]
            by_edupage[g["id"]] = group
        if group.name != g["name"] and (clash := by_name.get(g["name"])) is not None and clash is not group:
            clash.name = f"{clash.name} ({clash.id})"  # an old row still holds this name
        group.name, group.key, group.code = g["name"], key, display_code(g["name"])
        group.course = g.get("course") or group.course
        group.language = g.get("lang") or group.language
        by_key[key], by_name[g["name"]] = group, group
        out[g["id"]] = group
    await session.flush()
    return out


async def _sync_teachers(session: AsyncSession, data: dict) -> tuple[dict[str, Teacher], int]:
    """Timetable teacher id -> Teacher row, for the faculty's teachers. Returns (map, number created).
    Teachers without a kafedra get one guessed from their subjects (app.services.departments)."""
    existing = list((await session.execute(select(Teacher))).scalars())
    by_edupage = {t.edupage_id: t for t in existing if t.edupage_id}
    by_name: dict[str, Teacher] = {}
    for t in existing:
        for k in teacher_name_keys(t.full_name) | {name_key(t.short_name)}:
            by_name.setdefault(k, t)
    out, created = {}, 0
    for t in data["teachers"]:
        if not t["faculty"]:
            continue
        teacher = (by_edupage.get(t["id"]) if data.get("source") == "edupage" else None) or by_name.get(name_key(t["name"]))
        if teacher is None:
            teacher = Teacher(full_name=t["name"], is_active=True)  # one switched off in the dashboard stays off
            session.add(teacher)
            created += 1
        elif teacher.full_name == teacher.short_name:  # never renamed from Excel: follow the timetable
            teacher.full_name = t["name"]
        teacher.short_name = t["name"]
        if data.get("source") == "edupage":
            if (other := by_edupage.get(t["id"])) and other is not teacher:
                other.edupage_id = None
            teacher.edupage_id = t["id"]
            by_edupage[t["id"]] = teacher
        by_name.setdefault(name_key(t["name"]), teacher)
        out[t["id"]] = teacher
    await session.flush()
    await departments.fill_missing(session, data, out)
    return out, created


async def guess_departments(session: AsyncSession) -> int | None:
    """Fill in the kafedra of teachers who have none, from the newest timetable. None if there is no timetable."""
    snapshot = await session.scalar(select(TimetableSnapshot).order_by(TimetableSnapshot.id.desc()).limit(1))
    if snapshot is None:
        return None
    data = snapshot.data
    existing = list((await session.execute(select(Teacher))).scalars())
    by_edupage = {t.edupage_id: t for t in existing if t.edupage_id}
    by_name = {k: t for t in existing for k in teacher_name_keys(t.full_name) | {name_key(t.short_name)}}
    teachers = {x["id"]: by_edupage.get(x["id"]) or by_name.get(name_key(x["name"])) for x in data["teachers"]}
    return await departments.fill_missing(session, data, {k: v for k, v in teachers.items() if v is not None})


async def rebuild_assignments(session: AsyncSession) -> int | None:
    """Replace the current semester's assignments with the newest timetable. None if that can't be done."""
    semester = await current_semester(session)
    snapshot = await session.scalar(select(TimetableSnapshot).order_by(TimetableSnapshot.id.desc()).limit(1))
    if semester is None or snapshot is None:
        return None
    data = snapshot.data
    groups = await _sync_groups(session, data)
    teachers, _ = await _sync_teachers(session, data)
    excluded = {s.strip().lower() for s in await settings_store.get(session, "excluded_subjects")}
    subjects = {s.name: s for s in (await session.execute(select(Subject))).scalars()}
    seen: set[tuple] = set()
    rows = []
    for lesson in data["lessons"]:
        if lesson["subject"].strip().lower() in excluded:
            continue
        if lesson["subject"] not in subjects:
            subjects[lesson["subject"]] = Subject(name=lesson["subject"])
            session.add(subjects[lesson["subject"]])
        for tid in lesson["teachers"]:
            for gid in lesson["groups"]:
                if tid in teachers and gid in groups:
                    key = (teachers[tid], groups[gid], lesson["subject"], lesson["type"])
                    if key not in seen:
                        seen.add(key)
                        rows.append(TeachingAssignment(semester=semester, teacher=key[0], group=key[1],
                                                       subject=subjects[key[2]], lesson_type=key[3]))
    await session.execute(delete(TeachingAssignment).where(TeachingAssignment.semester_id == semester.id))
    session.add_all(rows)
    await session.flush()
    return len(rows)


async def store_timetable(session: AsyncSession, data: dict, *, title: str, source: str, admin: str) -> bool:
    """Save a downloaded/uploaded timetable as the newest one. Returns False if nothing changed."""
    latest = await session.scalar(select(TimetableSnapshot).order_by(TimetableSnapshot.id.desc()).limit(1))
    if latest is not None and latest.data == data:
        return False
    session.add(TimetableSnapshot(source=source, title=title, faculty=get_settings().edupage_faculty, data=data))
    await session.flush()
    keep = select(TimetableSnapshot.id).order_by(TimetableSnapshot.id.desc()).limit(KEEP_SNAPSHOTS)
    await session.execute(delete(TimetableSnapshot).where(TimetableSnapshot.id.not_in(keep)))
    groups = await _sync_groups(session, data)
    _, new_teachers = await _sync_teachers(session, data)
    note = f"{len(groups)} groups, {sum(t['faculty'] for t in data['teachers'])} teachers, {len(data['lessons'])} lessons"
    if await settings_store.get(session, "assignments_source") == "timetable":
        n = await rebuild_assignments(session)
        note += f"; assignments: {n}" if n is not None else "; assignments not built (no current semester)"
    session.add(ImportLog(kind="timetable", filename=title[:255], created=new_teachers, updated=len(groups),
                          errors=0, note=note, admin=admin))
    return True


async def refresh_from_edupage(session: AsyncSession, admin: str = "system") -> tuple[bool, str | None]:
    """Download the timetable; store it (and update everything built from it) if it changed.

    Returns (changed, error). A failure is also saved in the settings, for the Data page.
    """
    settings = get_settings()
    try:
        info, raw = await edupage.download(settings.edupage_url)
        data = edupage.parse(raw, settings.edupage_faculty) | {"source": "edupage"}
    except edupage.TimetableError as e:
        await settings_store.save(session, timetable_error=str(e), timetable_checked_at=_now_text())
        return False, str(e)
    changed = await store_timetable(session, data, title=info.get("text", "EduPage"),
                                    source=f"{settings.edupage_url.rstrip('/')}/timetable/", admin=admin)
    await settings_store.save(session, timetable_error="", timetable_checked_at=_now_text())
    return changed, None


# ---------------------------------------------------------------- Health checks for the dashboard

async def health(session: AsyncSession) -> dict:
    """What is set up and what needs attention - shown on the Data page."""
    semester = await current_semester(session)
    now = datetime.now(timezone.utc)
    students = await session.scalar(select(func.count(Student.id)).where(Student.is_active))
    temporary = await session.scalar(select(func.count(Student.id)).where(Student.is_active, Student.passport_temporary))
    no_group = await session.scalar(select(func.count(Student.id)).where(Student.is_active, Student.group_id.is_(None)))
    assigned = (select(TeachingAssignment.group_id).join(Semester).where(Semester.is_current)).scalar_subquery()
    orphan_groups = (await session.execute(
        select(Group.id, Group.name, func.count(Student.id)).join(Student, Student.group_id == Group.id)
        .where(Student.is_active, Group.id.not_in(assigned)).group_by(Group.id).order_by(Group.name)
    )).all()
    assignments = await session.scalar(select(func.count(TeachingAssignment.id)).join(Semester).where(Semester.is_current))
    teachers = await session.scalar(select(func.count(func.distinct(TeachingAssignment.teacher_id)))
                                    .join(Semester).where(Semester.is_current))
    snapshot = (await session.execute(select(TimetableSnapshot.id, TimetableSnapshot.title, TimetableSnapshot.source,
                                             TimetableSnapshot.fetched_at)
                                      .order_by(TimetableSnapshot.id.desc()).limit(1))).first()
    open_campaign = await session.scalar(select(SurveyCampaign).where(SurveyCampaign.opens_at <= now,
                                                                      SurveyCampaign.closes_at > now).limit(1))
    return {"semester": semester, "students": students, "temporary": temporary, "no_group": no_group,
            "orphan_groups": [{"id": i, "name": n, "students": c} for i, n, c in orphan_groups],
            "assignments": assignments, "teachers": teachers, "snapshot": snapshot, "open_campaign": open_campaign}
