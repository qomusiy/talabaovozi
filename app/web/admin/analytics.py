"""Aggregate queries for the admin dashboard.

Every function takes a campaign id (None = all campaigns). "Overall" score = mean of the three criteria.
"""
from dataclasses import dataclass

from sqlalchemy import Numeric, and_, case, cast, distinct, func, literal, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import (
    Department,
    Feedback,
    Group,
    Semester,
    Student,
    SurveyCampaign,
    Teacher,
    TeachingAssignment,
)

OVERALL = (Feedback.teaching + Feedback.fairness + Feedback.professionalism) / literal(3.0)
LOCAL_DAY = func.date(func.timezone("Asia/Tashkent", Feedback.created_at))


def _r(x, digits=2):
    return round(float(x), digits) if x is not None else None


def _campaign_filter(campaign_id: int | None):
    return Feedback.campaign_id == campaign_id if campaign_id else literal(True)


async def campaigns(session: AsyncSession) -> list[SurveyCampaign]:
    return list((await session.execute(
        select(SurveyCampaign).options(selectinload(SurveyCampaign.semester)).order_by(SurveyCampaign.opens_at.desc())
    )).scalars())


async def previous_campaign_id(session: AsyncSession, campaign_id: int | None) -> int | None:
    """The survey round held just before this one (for "vs previous survey" deltas)."""
    if not campaign_id:
        return None
    opens = select(SurveyCampaign.opens_at).where(SurveyCampaign.id == campaign_id).scalar_subquery()
    return (await session.execute(
        select(SurveyCampaign.id).where(SurveyCampaign.opens_at < opens)
        .order_by(SurveyCampaign.opens_at.desc()).limit(1)
    )).scalar()


async def semester_of(session: AsyncSession, campaign_id: int | None) -> int | None:
    """Semester whose teaching assignments define 'expected' evaluations. Default: current semester."""
    if campaign_id:
        return (await session.execute(
            select(SurveyCampaign.semester_id).where(SurveyCampaign.id == campaign_id))).scalar()
    return (await session.execute(select(Semester.id).where(Semester.is_current))).scalar()


async def departments(session: AsyncSession) -> list[Department]:
    return list((await session.execute(select(Department).order_by(Department.name))).scalars())


# ---------------------------------------------------------------- Overview

async def kpis(session: AsyncSession, campaign_id: int | None) -> dict:
    cf = _campaign_filter(campaign_id)
    fb = (await session.execute(select(
        func.count(Feedback.id), func.count(distinct(Feedback.student_id)), func.count(distinct(Feedback.teacher_id)),
        func.avg(Feedback.teaching), func.avg(Feedback.fairness), func.avg(Feedback.professionalism),
        func.avg(OVERALL), func.count(Feedback.comment),
    ).where(cf))).one()
    st = (await session.execute(select(
        func.count(Student.id), func.count(Student.registered_at),
    ).where(Student.is_active))).one()
    total_students, registered = st
    return {
        "evaluations": fb[0], "participants": fb[1], "teachers_rated": fb[2],
        "teaching": _r(fb[3]), "fairness": _r(fb[4]), "professionalism": _r(fb[5]),
        "overall": _r(fb[6]), "comments": fb[7],
        "students": total_students, "registered": registered,
        "participation_pct": round(100 * fb[1] / total_students, 1) if total_students else 0,
        "registered_pct": round(100 * registered / total_students, 1) if total_students else 0,
    }


async def daily_submissions(session: AsyncSession, campaign_id: int | None) -> list[dict]:
    rows = (await session.execute(
        select(LOCAL_DAY.label("d"), func.count()).where(_campaign_filter(campaign_id)).group_by("d").order_by("d")
    )).all()
    return [{"date": d.isoformat(), "count": n} for d, n in rows]


async def distribution(session: AsyncSession, campaign_id: int | None, teacher_id: int | None = None) -> list[int]:
    """How many evaluations have an overall score of 1..10 (rounded)."""
    bucket = func.round(OVERALL).label("b")
    q = select(bucket, func.count()).where(_campaign_filter(campaign_id)).group_by(bucket)
    if teacher_id:
        q = q.where(Feedback.teacher_id == teacher_id)
    counts = dict((int(b), n) for b, n in (await session.execute(q)).all())
    return [counts.get(i, 0) for i in range(1, 11)]


async def specialty_criteria(session: AsyncSession, campaign_id: int | None) -> list[dict]:
    """Scores by the students' specialty (group code: IQT, BXA, FTO'IT, ...; see app.faculty.specialty_name)."""
    rows = (await session.execute(
        select(Group.code, func.count(Feedback.id), func.avg(Feedback.teaching),
               func.avg(Feedback.fairness), func.avg(Feedback.professionalism), func.avg(OVERALL))
        .join(Group, Group.id == Feedback.group_id)
        .where(_campaign_filter(campaign_id), Group.code.is_not(None))
        .group_by(Group.code).order_by(func.avg(OVERALL).desc())
    )).all()
    return [{"code": code, "n": n, "teaching": _r(a), "fairness": _r(b),
             "professionalism": _r(c), "overall": _r(o)} for code, n, a, b, c, o in rows]


async def latest_comments(session: AsyncSession, campaign_id: int | None, limit: int = 8) -> list[dict]:
    rows = (await session.execute(
        select(Feedback, Student.full_name, Teacher.full_name, Group.name)
        .join(Student, Student.id == Feedback.student_id).join(Teacher, Teacher.id == Feedback.teacher_id)
        .outerjoin(Group, Group.id == Feedback.group_id)
        .where(_campaign_filter(campaign_id), Feedback.comment.is_not(None))
        .order_by(Feedback.created_at.desc()).limit(limit)
    )).all()
    return [_comment_row(f, s, t, g) for f, s, t, g in rows]


def _comment_row(f: Feedback, student: str, teacher: str | None, group: str | None) -> dict:
    return {
        "student": student, "teacher": teacher, "teacher_id": f.teacher_id, "group": group,
        "date": f.created_at.strftime("%d.%m.%Y"), "comment": f.comment,
        "teaching": f.teaching, "fairness": f.fairness,
        "professionalism": f.professionalism,
        "overall": round((f.teaching + f.fairness + f.professionalism) / 3, 1),
    }


# ---------------------------------------------------------------- Teachers

async def _expected_students(session: AsyncSession, semester_id: int | None) -> dict[int, int]:
    """teacher_id -> number of active students in the groups they teach that semester."""
    if not semester_id:
        return {}
    pairs = (select(TeachingAssignment.teacher_id.label("t"), TeachingAssignment.group_id.label("g"))
             .where(TeachingAssignment.semester_id == semester_id).distinct().subquery())
    rows = (await session.execute(
        select(pairs.c.t, func.count(Student.id)).join(Student, and_(Student.group_id == pairs.c.g, Student.is_active))
        .group_by(pairs.c.t)
    )).all()
    return dict(rows)


async def teacher_table(session: AsyncSession, campaign_id: int | None, department_id: int | None = None) -> list[dict]:
    q = (select(Teacher.id, Teacher.full_name, Department.name, Teacher.room_number, func.count(Feedback.id),
                func.avg(Feedback.teaching), func.avg(Feedback.fairness),
                func.avg(Feedback.professionalism), func.avg(OVERALL), func.count(Feedback.comment))
         .outerjoin(Department, Department.id == Teacher.department_id)
         .outerjoin(Feedback, and_(Feedback.teacher_id == Teacher.id, _campaign_filter(campaign_id)))
         .where(Teacher.is_active).group_by(Teacher.id, Department.name))
    semester_id = await semester_of(session, campaign_id)
    teaching = select(TeachingAssignment.teacher_id).where(TeachingAssignment.semester_id == semester_id)
    q = q.having(or_(func.count(Feedback.id) > 0, Teacher.id.in_(teaching)))
    if department_id:
        q = q.where(Teacher.department_id == department_id)
    expected = await _expected_students(session, semester_id) if campaign_id else {}
    out = []
    for tid, name, dept, room, n, a, b, c, o, comments in (await session.execute(q)).all():
        exp = expected.get(tid)
        out.append({"id": tid, "name": name, "department": dept, "room": room, "n": n,
                    "teaching": _r(a), "fairness": _r(b), "professionalism": _r(c),
                    "overall": _r(o), "comments": comments, "expected": exp,
                    "response_pct": round(100 * n / exp, 1) if exp else None})
    return sorted(out, key=lambda r: (r["overall"] is None, -(r["overall"] or 0)))


async def teacher_detail(session: AsyncSession, teacher_id: int, campaign_id: int | None) -> dict | None:
    teacher = await session.get(Teacher, teacher_id)
    if teacher is None:
        return None
    await session.refresh(teacher, ["department"])
    cf = _campaign_filter(campaign_id)
    me = (await session.execute(select(
        func.count(Feedback.id), func.avg(Feedback.teaching), func.avg(Feedback.fairness),
        func.avg(Feedback.professionalism), func.avg(OVERALL), func.count(Feedback.comment),
    ).where(cf, Feedback.teacher_id == teacher_id))).one()
    faculty = (await session.execute(select(
        func.avg(Feedback.teaching), func.avg(Feedback.fairness),
        func.avg(Feedback.professionalism), func.avg(OVERALL),
    ).where(cf))).one()
    # Rank among teachers with at least 5 evaluations.
    ranked = [t for t in await teacher_table(session, campaign_id) if t["n"] >= 5]
    rank = next((i for i, t in enumerate(ranked, 1) if t["id"] == teacher_id), None)

    by_group = (await session.execute(
        select(Group.name, func.count(Feedback.id), func.avg(Feedback.teaching),
               func.avg(Feedback.fairness), func.avg(Feedback.professionalism), func.avg(OVERALL))
        .join(Group, Group.id == Feedback.group_id).where(cf, Feedback.teacher_id == teacher_id)
        .group_by(Group.name).order_by(Group.name)
    )).all()

    semester_id = await semester_of(session, campaign_id)
    lessons = (await session.execute(
        select(Group.name, TeachingAssignment.lesson_type, TeachingAssignment.subject_id)
        .join(Group, Group.id == TeachingAssignment.group_id)
        .where(TeachingAssignment.teacher_id == teacher_id, TeachingAssignment.semester_id == semester_id)
    )).all()
    expected = (await _expected_students(session, semester_id)).get(teacher_id)

    comments = (await session.execute(
        select(Feedback, Student.full_name, Group.name)
        .join(Student, Student.id == Feedback.student_id).outerjoin(Group, Group.id == Feedback.group_id)
        .where(cf, Feedback.teacher_id == teacher_id).order_by(Feedback.created_at.desc())
    )).all()

    return {
        "teacher": {"id": teacher.id, "name": teacher.full_name, "short_name": teacher.short_name,
                    "edupage_id": teacher.edupage_id, "position": teacher.position,
                    "room": teacher.room_number, "department": teacher.department.name if teacher.department else None},
        "n": me[0], "comments_count": me[5], "rank": rank, "ranked_total": len(ranked),
        "groups_taught": len({g for g, _, _ in lessons}), "expected": expected,
        "response_pct": round(100 * me[0] / expected, 1) if expected and campaign_id else None,
        "scores": {"teaching": _r(me[1]), "fairness": _r(me[2]),
                   "professionalism": _r(me[3]), "overall": _r(me[4])},
        "faculty": {"teaching": _r(faculty[0]), "fairness": _r(faculty[1]),
                    "professionalism": _r(faculty[2]), "overall": _r(faculty[3])},
        "by_group": [{"name": g, "n": n, "teaching": _r(a), "fairness": _r(b),
                      "professionalism": _r(c), "overall": _r(o)} for g, n, a, b, c, o in by_group],
        "distribution": await distribution(session, campaign_id, teacher_id),
        "feedback": [_comment_row(f, s, None, g) for f, s, g in comments],
    }


# ---------------------------------------------------------------- Groups & students

async def _expected_teachers_per_group(session: AsyncSession, semester_id: int | None) -> dict[int, int]:
    if not semester_id:
        return {}
    rows = (await session.execute(
        select(TeachingAssignment.group_id, func.count(distinct(TeachingAssignment.teacher_id)))
        .where(TeachingAssignment.semester_id == semester_id).group_by(TeachingAssignment.group_id)
    )).all()
    return dict(rows)


def _per_student_counts(campaign_id: int | None):
    return (select(Feedback.student_id.label("sid"), func.count(distinct(Feedback.teacher_id)).label("rated"),
                   func.max(Feedback.created_at).label("last"))
            .where(_campaign_filter(campaign_id)).group_by(Feedback.student_id).subquery())


async def group_table(session: AsyncSession, campaign_id: int | None, course: int | None = None) -> list[dict]:
    expected = await _expected_teachers_per_group(session, await semester_of(session, campaign_id))
    per_student = _per_student_counts(campaign_id)
    q = (select(Group.id, Group.name, Group.course, func.count(Student.id), func.count(Student.registered_at),
                func.count(per_student.c.sid), func.coalesce(func.sum(per_student.c.rated), 0),
                func.array_agg(per_student.c.rated))
         .join(Student, and_(Student.group_id == Group.id, Student.is_active))
         .outerjoin(per_student, per_student.c.sid == Student.id).group_by(Group.id))
    if course:
        q = q.where(Group.course == course)
    avg_by_group = dict((await session.execute(
        select(Feedback.group_id, func.avg(OVERALL)).where(_campaign_filter(campaign_id)).group_by(Feedback.group_id)
    )).all())
    out = []
    for gid, name, crs, students, registered, participants, rated_sum, rated_list in (await session.execute(q)).all():
        exp = expected.get(gid, 0)
        rated_sum = int(rated_sum)
        completed = sum(1 for r in rated_list if r is not None and exp and r >= exp)
        out.append({"id": gid, "name": name, "course": crs, "students": students, "registered": registered,
                    "participants": participants, "completed": completed, "teachers": exp,
                    "participation_pct": round(100 * participants / students, 1) if students else 0,
                    "registered_pct": round(100 * registered / students, 1) if students else 0,
                    "coverage_pct": round(100 * rated_sum / (students * exp), 1) if students and exp else 0,
                    "overall": _r(avg_by_group.get(gid))})
    return sorted(out, key=lambda r: r["name"])


def course_summary(groups: list[dict]) -> list[dict]:
    by: dict = {}
    for g in groups:
        c = by.setdefault(g["course"] or 0, {"course": g["course"], "students": 0, "participants": 0, "registered": 0})
        c["students"] += g["students"]
        c["participants"] += g["participants"]
        c["registered"] += g["registered"]
    for c in by.values():
        c["participation_pct"] = round(100 * c["participants"] / c["students"], 1) if c["students"] else 0
    return [by[k] for k in sorted(by)]


STUDENT_STATUSES = ("not_registered", "registered", "partial", "completed")


@dataclass
class StudentPage:
    rows: list[dict]
    total: int
    counts: dict[str, int]


async def student_table(session: AsyncSession, campaign_id: int | None, group_id: int | None = None,
                        status: str | None = None, search: str | None = None,
                        page: int = 1, per_page: int = 50) -> StudentPage:
    """Students with their participation status in the campaign.

    Status: not_registered (never logged in to the bot) / registered (logged in, rated nobody) /
    partial (rated some of their teachers) / completed (rated all of them).
    """
    semester_id = await semester_of(session, campaign_id)
    exp_sub = (select(TeachingAssignment.group_id.label("gid"),
                      func.count(distinct(TeachingAssignment.teacher_id)).label("exp"))
               .where(TeachingAssignment.semester_id == semester_id).group_by(TeachingAssignment.group_id).subquery())
    ps = _per_student_counts(campaign_id)
    rated = func.coalesce(ps.c.rated, 0)
    expected = func.coalesce(exp_sub.c.exp, 0)
    status_expr = case(
        (Student.registered_at.is_(None) & (rated == 0), "not_registered"),
        (rated == 0, "registered"),
        (rated < expected, "partial"),
        else_="completed",
    ).label("status")

    base = (select(Student.id, Student.full_name, Student.hemis_id, Group.name.label("group"), Student.telegram_id,
                   Student.registered_at, Student.passport_temporary, rated.label("rated"), expected.label("expected"), ps.c.last, status_expr)
            .outerjoin(Group, Group.id == Student.group_id)
            .outerjoin(exp_sub, exp_sub.c.gid == Student.group_id)
            .outerjoin(ps, ps.c.sid == Student.id)
            .where(Student.is_active))
    if group_id:
        base = base.where(Student.group_id == group_id)
    if search:
        like = f"%{search.strip()}%"
        base = base.where(or_(Student.full_name.ilike(like), Student.hemis_id.ilike(like)))
    sub = base.subquery()

    counts = dict((await session.execute(select(sub.c.status, func.count()).group_by(sub.c.status))).all())
    q = select(sub)
    if status in STUDENT_STATUSES:
        q = q.where(sub.c.status == status)
    total = (await session.execute(select(func.count()).select_from(q.subquery()))).scalar()
    rows = (await session.execute(
        q.order_by(sub.c.group, sub.c.full_name).offset((page - 1) * per_page).limit(per_page))).mappings().all()
    return StudentPage(
        rows=[{**r, "last": r["last"].strftime("%d.%m.%Y %H:%M") if r["last"] else None,
               "registered": r["registered_at"] is not None, "in_bot": r["telegram_id"] is not None}
              for r in rows],
        total=total, counts={s: counts.get(s, 0) for s in STUDENT_STATUSES},
    )


async def all_groups(session: AsyncSession) -> list[Group]:
    return list((await session.execute(select(Group).order_by(Group.name))).scalars())


# ---------------------------------------------------------------- Overview extras

async def participation_curve(session: AsyncSession, campaign_id: int | None) -> list[dict]:
    """Cumulative number of students who had rated at least one teacher, day by day (one campaign)."""
    if not campaign_id:
        return []
    first = (select(Feedback.student_id, func.min(LOCAL_DAY).label("d"))
             .where(Feedback.campaign_id == campaign_id).group_by(Feedback.student_id).subquery())
    rows = (await session.execute(select(first.c.d, func.count()).group_by(first.c.d).order_by(first.c.d))).all()
    total, out = 0, []
    for d, n in rows:
        total += n
        out.append({"date": d.isoformat(), "count": total})
    return out


COMMENT_BANDS = {"lo": (0, 6), "mid": (6, 8), "hi": (8, 11)}


@dataclass
class CommentPage:
    rows: list[dict]
    total: int
    counts: dict[str, int]


def _comment_filters(campaign_id: int | None, q: str | None, teacher_id: int | None, group_id: int | None,
                     by_student: bool = True) -> list:
    """Filters of the comments page, shared with its Excel export (the query must join Student and Teacher).
    by_student=False: the search doesn't match student names (for viewers who may not see them)."""
    conditions = [_campaign_filter(campaign_id), Feedback.comment.is_not(None)]
    if teacher_id:
        conditions.append(Feedback.teacher_id == teacher_id)
    if group_id:
        conditions.append(Feedback.group_id == group_id)
    if q:
        like = f"%{q.strip()}%"
        conditions.append(or_(Feedback.comment.ilike(like), Teacher.full_name.ilike(like),
                              *([Student.full_name.ilike(like)] if by_student else [])))
    return conditions


def _in_band(band: str):
    lo, hi = COMMENT_BANDS[band]
    return and_(OVERALL >= lo, OVERALL < hi)


async def comment_feed(session: AsyncSession, campaign_id: int | None, q: str | None = None,
                       band: str | None = None, teacher_id: int | None = None, group_id: int | None = None,
                       page: int = 1, per_page: int = 30, by_student: bool = True) -> CommentPage:
    """Evaluations that have a written comment, newest first, with filters."""
    base = (select(Feedback, Student.full_name, Teacher.full_name, Group.name)
            .join(Student, Student.id == Feedback.student_id).join(Teacher, Teacher.id == Feedback.teacher_id)
            .outerjoin(Group, Group.id == Feedback.group_id)
            .where(*_comment_filters(campaign_id, q, teacher_id, group_id, by_student)))
    counts = {}
    for key in COMMENT_BANDS:
        counts[key] = (await session.execute(
            select(func.count()).select_from(base.where(_in_band(key)).subquery()))).scalar()
    if band in COMMENT_BANDS:
        base = base.where(_in_band(band))
    total = (await session.execute(select(func.count()).select_from(base.subquery()))).scalar()
    rows = (await session.execute(
        base.order_by(Feedback.created_at.desc()).offset((page - 1) * per_page).limit(per_page))).all()
    return CommentPage(rows=[_comment_row(f, s, t, g) for f, s, t, g in rows], total=total, counts=counts)


async def comment_export_rows(session: AsyncSession, campaign_id: int | None, q: str | None = None,
                              band: str | None = None, teacher_id: int | None = None,
                              group_id: int | None = None, by_student: bool = True) -> list[tuple]:
    """The comments page for Excel: the same filters, every page, newest first."""
    query = (select(SurveyCampaign.title, LOCAL_DAY, Teacher.full_name, Department.name, Student.full_name,
                    Student.hemis_id, Group.name, Feedback.teaching, Feedback.fairness, Feedback.professionalism,
                    func.round(cast(OVERALL, Numeric), 1), Feedback.comment)
             .join(SurveyCampaign, SurveyCampaign.id == Feedback.campaign_id)
             .join(Teacher, Teacher.id == Feedback.teacher_id).outerjoin(Department, Department.id == Teacher.department_id)
             .join(Student, Student.id == Feedback.student_id).outerjoin(Group, Group.id == Feedback.group_id)
             .where(*_comment_filters(campaign_id, q, teacher_id, group_id, by_student)))
    if band in COMMENT_BANDS:
        query = query.where(_in_band(band))
    return (await session.execute(query.order_by(Feedback.created_at.desc()))).all()


async def all_teachers(session: AsyncSession) -> list[Teacher]:
    return list((await session.execute(select(Teacher).where(Teacher.is_active).order_by(Teacher.full_name))).scalars())


async def teacher_group_links(session: AsyncSession, campaign_id: int | None) -> set[tuple[int, int]]:
    """(teacher id, group id) pairs: who teaches whom in the survey's semester, plus every pair that has feedback
    in it. The comments page offers only the teachers of the chosen group, and the groups of the chosen teacher."""
    semester_id = await semester_of(session, campaign_id)
    taught = select(TeachingAssignment.teacher_id, TeachingAssignment.group_id).where(
        TeachingAssignment.semester_id == semester_id)
    rated = select(Feedback.teacher_id, Feedback.group_id).where(
        _campaign_filter(campaign_id), Feedback.group_id.is_not(None))
    return {(t, g) for t, g in (await session.execute(taught.union(rated))).all()}
