"""The survey, shared by the Telegram bot and the survey web app: the open round, whom a user may rate, saving a
rating. With a group picked, a user rates that group's teachers; without one, any teacher who teaches this semester."""
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app import settings_store
from app.models import RATING_CRITERIA, BotUser, Feedback, Semester, SurveyCampaign, Teacher, TeachingAssignment


async def current_semester(session: AsyncSession) -> Semester | None:
    return (await session.execute(select(Semester).where(Semester.is_current))).scalar_one_or_none()


@dataclass
class TeacherCard:
    teacher: Teacher
    lessons: list[tuple[str, str]] = field(default_factory=list)  # (subject name, lesson type)


async def teachers_of(session: AsyncSession, user: BotUser | None, group_id: int | None = None) -> list[TeacherCard]:
    """The user's group's teachers this semester, one card per teacher - or, without a group, every teacher who
    teaches this semester (their subjects without repeats)."""
    gid = group_id if group_id is not None else (user.group_id if user else None)
    q = (select(TeachingAssignment)
         .options(selectinload(TeachingAssignment.teacher).selectinload(Teacher.department),
                  selectinload(TeachingAssignment.subject))
         .join(Semester).where(Semester.is_current))
    if gid:
        q = q.where(TeachingAssignment.group_id == gid)
    cards: dict[int, TeacherCard] = {}
    for a in (await session.execute(q)).scalars():
        if not a.teacher.is_active:
            continue
        card = cards.setdefault(a.teacher_id, TeacherCard(a.teacher))
        if (a.subject.name, a.lesson_type) not in card.lessons:
            card.lessons.append((a.subject.name, a.lesson_type))
    return sorted(cards.values(), key=lambda c: c.teacher.full_name)


async def may_rate(session: AsyncSession, user: BotUser, teacher_id: int) -> bool:
    """A teacher of the user's group - or, without a group, any active teacher who teaches this semester."""
    q = (select(TeachingAssignment.id).join(Semester).join(Teacher, Teacher.id == TeachingAssignment.teacher_id)
         .where(Semester.is_current, Teacher.is_active, TeachingAssignment.teacher_id == teacher_id))
    if user.group_id:
        q = q.where(TeachingAssignment.group_id == user.group_id)
    return bool(await session.scalar(q.limit(1)))


async def active_campaign(session: AsyncSession) -> SurveyCampaign | None:
    now = datetime.now(timezone.utc)
    return (await session.execute(
        select(SurveyCampaign).where(SurveyCampaign.opens_at <= now, SurveyCampaign.closes_at > now)
        .order_by(SurveyCampaign.opens_at.desc()).limit(1)
    )).scalar_one_or_none()


async def rated_teacher_ids(session: AsyncSession, user: BotUser, campaign: SurveyCampaign) -> set[int]:
    return set((await session.execute(
        select(Feedback.teacher_id).where(Feedback.campaign_id == campaign.id, Feedback.user_id == user.id)
    )).scalars())


class SurveyError(Exception):
    pass


async def save_feedback(session: AsyncSession, user: BotUser, teacher_id: int, ratings: dict[str, int],
                        comment: str | None) -> Feedback:
    """Create or update the user's rating of a teacher in the open round.

    Only while a round is open, only teachers the user may rate (may_rate), and once per teacher (sending again
    updates the same rating until the round closes - unless admins turned that off).
    """
    campaign = await active_campaign(session)
    if campaign is None:
        raise SurveyError("no_campaign")
    if not await may_rate(session, user, teacher_id):
        raise SurveyError("not_your_teacher")
    if set(ratings) != set(RATING_CRITERIA):
        raise SurveyError("bad_rating")
    for value in ratings.values():
        if not (isinstance(value, int) and 1 <= value <= 10):
            raise SurveyError("bad_rating")
    settings = await settings_store.load(session)
    if not settings["survey_edit"] and teacher_id in await rated_teacher_ids(session, user, campaign):
        raise SurveyError("locked")
    if not settings["survey_comments"]:
        comment = None
    values = dict(ratings, group_id=user.group_id, comment=(comment or "").strip()[:2000] or None)
    stmt = pg_insert(Feedback).values(campaign_id=campaign.id, user_id=user.id, teacher_id=teacher_id, **values)
    stmt = stmt.on_conflict_do_update(
        index_elements=["campaign_id", "user_id", "teacher_id"],
        set_={**values, "updated_at": func.now()},
    ).returning(Feedback)
    return (await session.execute(stmt)).scalar_one()


async def feedback_by_teacher(session: AsyncSession, user: BotUser, campaign: SurveyCampaign) -> dict[int, Feedback]:
    rows = (await session.execute(
        select(Feedback).where(Feedback.campaign_id == campaign.id, Feedback.user_id == user.id)
    )).scalars()
    return {f.teacher_id: f for f in rows}
