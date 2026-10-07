"""Kafedras, and a best guess of each teacher's kafedra from the subjects they teach.

The timetable says who teaches what, not which kafedra a teacher belongs to. Until the real kafedras are uploaded
(teachers Excel, "kafedra" column) or set by hand (dashboard: Tahrirlash), a teacher without one gets the kafedra
that teaches most of their lessons: Makroiqtisodiyot -> "Iqtisodiyot", Oliy matematika -> "Oliy matematika"
(a kafedra of the Yer resurslari va kadastr faculty). Kafedra and faculty names are TIIAME's (tiiame.uz).
"""
import re
from collections import Counter

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.faculty import group_code
from app.models import Department, Teacher

ECON, IT, ACC, MGMT, ENG, LANG = ("Iqtisodiyot", "Axborot texnologiyalari", "Buxgalteriya hisobi va audit",
                                  "Boshqaruv va turizm", "Ingliz tili", "O‘zbek tili va adabiyoti")
HUM, LAW, MATH, PHYS, IRR, SPORT, ELEC = ("Gumanitar fanlar", "Huquqiy fanlar", "Oliy matematika", "Fizika va kimyo",
                                         "Irrigatsiya va melioratsiya", "Jismoniy tarbiya va sport",
                                         "Elektrotexnika va mexatronika")
# Kafedra -> faculty. The Economics faculty's own six come first.
KAFEDRAS = {
    ECON: "Iqtisodiyot", IT: "Iqtisodiyot", ACC: "Iqtisodiyot", MGMT: "Iqtisodiyot", ENG: "Iqtisodiyot",
    LANG: "Iqtisodiyot", HUM: "Ekologiya va huquq", LAW: "Ekologiya va huquq", MATH: "Yer resurslari va kadastr",
    PHYS: "Gidromelioratsiya", IRR: "Gidromelioratsiya", SPORT: "Gidromelioratsiya", ELEC: "Energetika",
}
# The kafedra that runs each specialty (by group code), for subjects every specialty has ("Mutaxassislikka kirish").
SPECIALTY_KAFEDRA = {"IQT": ECON, "BB": MGMT, "TUR": MGMT, "BXA": ACC, "STAT": ACC, "ATT": IT, "FTOIT": ENG, "FTORT": LANG}
# Literature, linguistics and speech practice are taught in both philology specialties: the group decides.
PHILOLOGY = {"FTOIT": ENG, "FTORT": LANG}

# (subject pattern, kafedra - or (kafedra by group code, otherwise), weight). The first match wins, so the more
# specific patterns come first ("matematik statistika" is maths, "Iqtisodiyotda axborot texnologiyalari" is IT).
RULES: list[tuple[re.Pattern, str | tuple[dict, str | None], float]] = [(re.compile(p), k, w) for p, k, w in [
    (r"kelajak soati", None, 0),
    (r"oliy matematika|amaliy matematika|chiziqli algebra|matematik analiz|calculus|differensial|ehtimollar|^matematika",
     MATH, 1),
    (r"fizika|kimyo", PHYS, 1),
    (r"elektr|elektron|mexatron|birlashtirilgan sistema", ELEC, 1),
    (r"irrigatsiya|melioratsiya|suvdan samarali|tabiiy sharoit", IRR, 1),
    (r"huquq", LAW, 1),
    (r"mediasavod", HUM, .3),
    (r"madaniyatlararo", ENG, .3),
    (r"ikkinchi chet tili", ENG, .5),
    (r"xorijiy til|chet til|ingliz|nemis|turk til|koreys|akademik yozuv", ENG, 1),
    (r"sport|jismoniy|dzyudo|futbol|voleybol|atletika|harakatli o'yin", SPORT, 1),
    (r"rus til|rus adabiyot|o'zbek (\(rus\) )?til", LANG, 1),
    (r"adabiyot|tilshunoslik|folklor|grammatika|og'zaki nutq|o'qish va yozish", (PHILOLOGY, ENG), .6),
    (r"statist|ststist|stata", ACC, 1),
    (r"buxgalter|audit|hisob|xisob|soliq|tannarx|acca", ACC, 1),
    (r"axborot|dastur|ma'lumotlar|kompyuter|tarmoq|veb|lms|mashinali|intellekt|bulutli|diskret|ekonometrika", IT, 1),
    (r"turizm|mehmon|gastronom|ziyorat|o'lkashunoslik|inson resurs|menejment|biznes", MGMT, 1),
    (r"iqtisod|tadbirkor|moliya", ECON, 1),
    (r"falsafa|mantiq|dinshunoslik|tarix|arxeologiya|psixologiya", HUM, 1),
    (r"mutaxassislikka kirish|ixtisoslikka kirish|ilmiy tadqiqot|tanqidiy", (SPECIALTY_KAFEDRA, None), .3),
]]

_CYRILLIC_LOOKALIKES = str.maketrans("АаВЕеКМНОоРрСсТуХх", "AaBEeKMHOoPpCcTyXx")


def _subject_key(name: str) -> str:
    """'STАTА dasturi' (Cyrillic А) -> 'stata dasturi';  'Ma’lumotlar' -> "ma'lumotlar"."""
    return re.sub("[‘’ʻʼ`]", "'", name.translate(_CYRILLIC_LOOKALIKES)).lower().strip()


def guess(lessons: list[tuple[str, list[str]]]) -> str | None:
    """The likeliest kafedra for a teacher, from their lessons as (subject, group names)."""
    votes: Counter = Counter()
    for subject, groups in lessons:
        key = _subject_key(subject)
        rule = next(((k, w) for p, k, w in RULES if p.search(key)), None)
        if rule is None or rule[0] is None:
            continue
        kafedra, weight = rule
        if isinstance(kafedra, str):
            votes[kafedra] += weight
            continue
        by_code, otherwise = kafedra
        for g in groups or [""]:
            if target := by_code.get(group_code(g) or "") or otherwise:
                votes[target] += weight / max(1, len(groups))
    if not votes:
        return None
    best = max(votes.values())
    return next(k for k in (*KAFEDRAS, *votes) if votes.get(k) == best)


def _name_key(name: str) -> str:
    return re.sub("[‘’ʻʼ`']", "", name).lower().strip()


async def fill_missing(session: AsyncSession, data: dict, teachers: dict[str, Teacher]) -> int:
    """Give every teacher without a kafedra the guessed one. `data` is a timetable (app/timetable), `teachers` maps
    its teacher ids to rows. A kafedra set by hand or from Excel is never changed. Returns how many were filled."""
    missing = {tid: t for tid, t in teachers.items() if t.department_id is None}
    if not missing:
        return 0
    group_names = {g["id"]: g["name"] for g in data["groups"]}
    lessons: dict[str, list] = {tid: [] for tid in missing}
    for lesson in data["lessons"]:
        for tid in lesson["teachers"]:
            if tid in lessons:
                lessons[tid].append((lesson["subject"], [group_names.get(g, "") for g in lesson["groups"]]))
    guesses = {tid: name for tid in missing if (name := guess(lessons[tid]))}
    existing = {_name_key(d.name): d for d in (await session.execute(select(Department))).scalars()}
    for name in set(guesses.values()):
        if _name_key(name) not in existing:
            existing[_name_key(name)] = Department(name=name, faculty=KAFEDRAS.get(name))
            session.add(existing[_name_key(name)])
    await session.flush()
    for tid, name in guesses.items():
        missing[tid].department_id = existing[_name_key(name)].id
    await session.flush()
    return len(guesses)


def home_faculty() -> str:
    return get_settings().edupage_faculty


async def teacher_counts(session: AsyncSession) -> dict[int, int]:
    """department id -> number of active teachers."""
    return dict((await session.execute(
        select(Teacher.department_id, func.count(Teacher.id)).where(Teacher.is_active, Teacher.department_id.is_not(None))
        .group_by(Teacher.department_id))).all())
