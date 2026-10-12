"""Demo feedback over the real groups and teachers, so the dashboard can be tried before the first real survey.

Demo survey rounds are marked `is_demo`, and so are the made-up accounts that "rated" in them (negative ids - never
a real Telegram account): about as many per group as the group has students. `clear_demo` removes both, with their
feedback. Real rounds, real accounts and real feedback are never touched.
"""
import random
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import BotUser, Feedback, Group, Semester, SurveyCampaign, TeachingAssignment

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
DEFAULT_GROUP_SIZE = 25  # demo accounts for a group whose number of students is unknown


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
    groups = {g.id: g for g in (await session.execute(select(Group).where(Group.id.in_(teachers_by_group))))
              .scalars()}
    next_id = min(-1, (await session.scalar(select(func.min(BotUser.id))) or 0) - 1)
    people = []  # (account id, group)
    for gid in sorted(groups):
        for _ in range(groups[gid].student_count or DEFAULT_GROUP_SIZE):
            people.append((next_id, groups[gid]))
            next_id -= 1

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
    joined: dict[int, tuple[datetime, int]] = {}  # account -> (first rating, group)
    rows = []
    for i, (camp, (_, _, _, factor)) in enumerate(zip(rounds, ROUNDS)):
        end = min(camp.closes_at, now)
        span = max(1.0, (end - camp.opens_at).total_seconds())
        for uid, group in people:
            if rng.random() > engagement[group.id] * factor:
                continue
            bank = COMMENTS["ru" if "(ru)" in group.name else "uz"]
            leniency = rng.gauss(0, 0.8)
            for t in teachers_by_group[group.id]:
                if rng.random() > 0.9:
                    continue
                mu = quality[t] + trend[t] * i + leniency
                scores = [_clip(rng.gauss(mu + strength[t][k], 0.9)) for k in range(3)]
                comment = None
                if rng.random() < 0.3:
                    avg = sum(scores) / 3
                    comment = rng.choice(bank["low" if avg < 5 else "mid" if avg < 7.5 else "high"])
                when = camp.opens_at + timedelta(seconds=span * rng.random() ** 1.6)  # most answer early
                first = when - timedelta(minutes=rng.uniform(5, 600))
                joined[uid] = (min(joined[uid][0], first) if uid in joined else first, group.id)
                rows.append({"campaign_id": camp.id, "user_id": uid, "teacher_id": t, "group_id": group.id,
                             "teaching": scores[0], "fairness": scores[1],
                             "professionalism": scores[2], "comment": comment, "created_at": when, "updated_at": when})
    accounts = [{"id": uid, "group_id": gid, "language": "uz", "onboarded_at": when, "first_seen_at": when,
                 "last_seen_at": when, "is_demo": True} for uid, (when, gid) in joined.items()]
    for i in range(0, len(accounts), 5000):
        await session.execute(insert(BotUser), accounts[i:i + 5000])
    for i in range(0, len(rows), 5000):
        await session.execute(insert(Feedback), rows[i:i + 5000])
    return {"rounds": len(rounds), "feedback": len(rows), "students": len(joined)}


async def has_demo(session: AsyncSession) -> bool:
    return bool(await session.scalar(select(SurveyCampaign.id).where(SurveyCampaign.is_demo).limit(1)))


async def clear_demo(session: AsyncSession) -> None:
    """Remove demo rounds and the demo accounts (their feedback goes with them)."""
    await session.execute(delete(SurveyCampaign).where(SurveyCampaign.is_demo))
    await session.execute(delete(BotUser).where(BotUser.is_demo))
