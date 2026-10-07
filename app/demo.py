"""Demo feedback over the real students and teachers, so the dashboard can be tried before the first real survey.

Demo survey rounds are marked `is_demo`. `clear_demo` removes them with their feedback, and the demo
"joined the bot" dates of students who never really logged in. Real rounds and real feedback are never touched.
"""
import random
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Feedback, Semester, Student, SurveyCampaign, TeachingAssignment

COMMENTS = {
    "uz": {
        "low": ["Darslar juda zerikarli o‘tadi, faqat slayddan o‘qib beriladi.",
                "Savol bersak javob bermaydi, ko‘pincha darsga kechikib keladi.",
                "Baholash adolatsiz, talablar oldindan tushuntirilmaydi.",
                "Materiallar eskirgan, amaliy misollar yo‘q.",
                "Mavzuni tushuntirish juda tez, tushunib ulgurmaymiz."],
        "mid": ["Umuman yaxshi, lekin ko‘proq amaliy misollar bo‘lsa yaxshi bo‘lardi.",
                "Bilimi yaxshi, ammo tushuntirishi biroz murakkab.",
                "Darslar normal, uy vazifalari juda ko‘p.",
                "Yaxshi o‘qituvchi, lekin talabalar bilan muloqot kamroq.",
                "Taqdimotlarni yangilash kerak, qolgani yaxshi."],
        "high": ["Juda zo‘r o‘qituvchi! Har bir mavzuni hayotiy misollar bilan tushuntiradi.",
                 "Darslar qiziqarli, har doim savollarimizga javob beradi. Rahmat!",
                 "Eng yaxshi o‘qituvchilarimizdan biri, zamonaviy manbalardan foydalanadi.",
                 "Talabalarga doim yordam berishga tayyor, adolatli baholaydi.",
                 "Fanni yaxshi ko‘rib qoldim, ustozga katta rahmat!"],
    },
    "ru": {
        "low": ["Лекции скучные, преподаватель просто читает со слайдов.",
                "На вопросы не отвечает, часто опаздывает.",
                "Оценивание несправедливое, требования не объясняются."],
        "mid": ["В целом хорошо, но хотелось бы больше практики.",
                "Знающий преподаватель, но объясняет сложно.",
                "Хорошо, но презентации стоит обновить."],
        "high": ["Отличный преподаватель! Объясняет на реальных примерах.",
                 "Интересные занятия, всегда готов помочь. Спасибо!",
                 "Справедливо оценивает и всегда поддерживает студентов."],
    },
    "en": {
        "low": ["Lectures are boring, the teacher just reads the slides.",
                "Grading feels unfair and requirements are unclear."],
        "mid": ["Generally good, but more practical examples would help.",
                "Good overall, the slides could be updated."],
        "high": ["Excellent teacher! Explains everything with real-life examples.",
                 "Fair grading and very supportive of students."],
    },
}
# Three rounds: two closed ones (for trends) and one open now, so the survey can be tried in Telegram.
ROUNDS = [("Demo so‘rovnoma · 1", -20, 5, 0.70), ("Demo so‘rovnoma · 2", -13, 5, 0.80),
          ("Demo so‘rovnoma · 3", -3, 14, 0.55)]  # title, opens (days from now), open for (days), participation
UNTOUCHED = 30  # this many students get no demo data at all, so they can be used to test the bot


def _clip(x: float) -> int:
    return max(1, min(10, round(x)))


async def create_demo(session: AsyncSession, seed: int = 7) -> dict:
    """Add demo rounds and feedback for the current semester's assignments. Returns counts."""
    rng = random.Random(seed)
    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    semester = await session.scalar(select(Semester).where(Semester.is_current))
    if semester is None:
        raise ValueError("No current semester")
    teachers_by_group: dict[int, set[int]] = {}
    for gid, tid in (await session.execute(select(TeachingAssignment.group_id, TeachingAssignment.teacher_id)
                                            .where(TeachingAssignment.semester_id == semester.id))).all():
        teachers_by_group.setdefault(gid, set()).add(tid)
    students = list((await session.execute(select(Student).options(selectinload(Student.group))
                                           .where(Student.is_active, Student.telegram_id.is_(None))
                                           .order_by(Student.id))).scalars())
    students = [s for s in students[UNTOUCHED:] if s.group_id in teachers_by_group]

    rounds = [SurveyCampaign(semester=semester, title=t, opens_at=now + timedelta(days=o),
                             closes_at=now + timedelta(days=o + d) - timedelta(minutes=1), is_demo=True)
              for t, o, d, _ in ROUNDS]
    session.add_all(rounds)
    await session.flush()

    teacher_ids = sorted({t for ts in teachers_by_group.values() for t in ts})
    quality = {t: min(9.4, max(3.8, rng.gauss(7.3, 1.1))) for t in teacher_ids}
    trend = {t: rng.choice([-0.4, -0.2, 0, 0, 0.2, 0.4]) for t in teacher_ids}
    strength = {t: [rng.gauss(0, 0.55) for _ in range(3)] for t in teacher_ids}
    engagement = {g: rng.uniform(0.45, 1.0) for g in teachers_by_group}
    joined: dict[int, datetime] = {}
    rows = []
    for i, (camp, (_, _, _, factor)) in enumerate(zip(rounds, ROUNDS)):
        end = min(camp.closes_at, now)
        span = max(1.0, (end - camp.opens_at).total_seconds())
        for st in students:
            if rng.random() > engagement[st.group_id] * factor:
                continue
            bank = COMMENTS["ru" if "(ru)" in (st.group.name if st.group else "") else "uz"]
            leniency = rng.gauss(0, 0.8)
            for t in teachers_by_group[st.group_id]:
                if rng.random() > 0.9:
                    continue
                mu = quality[t] + trend[t] * i + leniency
                scores = [_clip(rng.gauss(mu + strength[t][k], 0.9)) for k in range(3)]
                comment = None
                if rng.random() < 0.3:
                    avg = sum(scores) / 3
                    comment = rng.choice(bank["low" if avg < 5 else "mid" if avg < 7.5 else "high"])
                when = camp.opens_at + timedelta(seconds=span * rng.random() ** 1.6)  # most answer early
                joined[st.id] = min(joined.get(st.id, when), when - timedelta(minutes=rng.uniform(5, 600)))
                rows.append({"campaign_id": camp.id, "student_id": st.id, "teacher_id": t, "group_id": st.group_id,
                             "teaching": scores[0], "fairness": scores[1],
                             "professionalism": scores[2], "comment": comment, "created_at": when, "updated_at": when})
    for i in range(0, len(rows), 5000):
        await session.execute(insert(Feedback), rows[i:i + 5000])
    for sid, when in joined.items():
        await session.execute(update(Student).where(Student.id == sid, Student.registered_at.is_(None))
                              .values(registered_at=when))
    return {"rounds": len(rounds), "feedback": len(rows), "students": len(joined)}


async def has_demo(session: AsyncSession) -> bool:
    return bool(await session.scalar(select(SurveyCampaign.id).where(SurveyCampaign.is_demo).limit(1)))


async def clear_demo(session: AsyncSession) -> None:
    """Remove demo rounds (their feedback goes with them) and demo 'joined the bot' dates."""
    await session.execute(delete(SurveyCampaign).where(SurveyCampaign.is_demo))
    await session.execute(update(Student).where(Student.telegram_id.is_(None)).values(registered_at=None))
