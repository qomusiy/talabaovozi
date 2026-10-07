"""Student-facing queries shared by the Telegram bot and the survey web app."""
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app import settings_store
from app.models import RATING_CRITERIA, Feedback, Semester, Student, SurveyCampaign, Teacher, TeachingAssignment
from app.security import normalize_hemis, verify_passport


class AlreadyLinkedError(Exception):
    """The student is already linked to a different Telegram account."""


async def get_by_telegram(session: AsyncSession, telegram_id: int) -> Student | None:
    return (await session.execute(
        select(Student).options(selectinload(Student.group))
        .where(Student.telegram_id == telegram_id, Student.is_active)
    )).scalar_one_or_none()


async def authenticate(session: AsyncSession, hemis_id: str, passport: str) -> Student | None:
    student = (await session.execute(
        select(Student).options(selectinload(Student.group))
        .where(Student.hemis_id == normalize_hemis(hemis_id), Student.is_active)
    )).scalar_one_or_none()
    if student and verify_passport(passport, student.passport_hash):
        return student
    return None


async def link_telegram(session: AsyncSession, student: Student, telegram_id: int, language: str) -> None:
    if student.telegram_id not in (None, telegram_id):
        raise AlreadyLinkedError
    # If this Telegram account was linked to another student before, unlink it.
    previous = await get_by_telegram(session, telegram_id)
    if previous and previous.id != student.id:
        previous.telegram_id = None
        await session.flush()
    student.telegram_id = telegram_id
    student.language = language
    student.registered_at = student.registered_at or datetime.now(timezone.utc)


async def current_semester(session: AsyncSession) -> Semester | None:
    return (await session.execute(select(Semester).where(Semester.is_current))).scalar_one_or_none()


@dataclass
class TeacherCard:
    teacher: Teacher
    lessons: list[tuple[str, str]] = field(default_factory=list)  # (subject name, lesson type)


async def teachers_of(session: AsyncSession, student: Student) -> list[TeacherCard]:
    """Teachers assigned to the student's group this semester, one card per teacher."""
    if student.group_id is None:
        return []
    rows = (await session.execute(
        select(TeachingAssignment)
        .options(selectinload(TeachingAssignment.teacher).selectinload(Teacher.department),
                 selectinload(TeachingAssignment.subject))
        .join(Semester)
        .where(Semester.is_current, TeachingAssignment.group_id == student.group_id)
    )).scalars()
    cards: dict[int, TeacherCard] = {}
    for a in rows:
        if not a.teacher.is_active:
            continue
        card = cards.setdefault(a.teacher_id, TeacherCard(a.teacher))
        card.lessons.append((a.subject.name, a.lesson_type))
    return sorted(cards.values(), key=lambda c: c.teacher.full_name)


async def active_campaign(session: AsyncSession) -> SurveyCampaign | None:
    now = datetime.now(timezone.utc)
    return (await session.execute(
        select(SurveyCampaign).where(SurveyCampaign.opens_at <= now, SurveyCampaign.closes_at > now)
        .order_by(SurveyCampaign.opens_at.desc()).limit(1)
    )).scalar_one_or_none()


async def rated_teacher_ids(session: AsyncSession, student: Student, campaign: SurveyCampaign) -> set[int]:
    return set((await session.execute(
        select(Feedback.teacher_id).where(Feedback.campaign_id == campaign.id, Feedback.student_id == student.id)
    )).scalars())


class SurveyError(Exception):
    pass


async def save_feedback(session: AsyncSession, student: Student, teacher_id: int, ratings: dict[str, int],
                        comment: str | None) -> Feedback:
    """Create or update the student's evaluation of a teacher in the active campaign.

    A student may only rate their own teachers, only while a campaign is open, and only once per teacher
    (re-submitting updates the same evaluation until the campaign closes - unless admins turned that off).
    """
    campaign = await active_campaign(session)
    if campaign is None:
        raise SurveyError("no_campaign")
    if teacher_id not in {c.teacher.id for c in await teachers_of(session, student)}:
        raise SurveyError("not_your_teacher")
    if set(ratings) != set(RATING_CRITERIA):
        raise SurveyError("bad_rating")
    for value in ratings.values():
        if not (isinstance(value, int) and 1 <= value <= 10):
            raise SurveyError("bad_rating")
    settings = await settings_store.load(session)
    if not settings["survey_edit"] and teacher_id in await rated_teacher_ids(session, student, campaign):
        raise SurveyError("locked")
    if not settings["survey_comments"]:
        comment = None
    values = dict(ratings, group_id=student.group_id, comment=(comment or "").strip()[:2000] or None)
    stmt = pg_insert(Feedback).values(campaign_id=campaign.id, student_id=student.id, teacher_id=teacher_id, **values)
    stmt = stmt.on_conflict_do_update(
        index_elements=["campaign_id", "student_id", "teacher_id"],
        set_={**values, "updated_at": func.now()},
    ).returning(Feedback)
    feedback = (await session.execute(stmt)).scalar_one()
    return feedback


async def feedback_by_teacher(session: AsyncSession, student: Student, campaign: SurveyCampaign) -> dict[int, Feedback]:
    rows = (await session.execute(
        select(Feedback).where(Feedback.campaign_id == campaign.id, Feedback.student_id == student.id)
    )).scalars()
    return {f.teacher_id: f for f in rows}
