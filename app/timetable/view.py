"""Read side of a timetable snapshot: the week of one group or teacher, plus summary numbers for the dashboard."""
from collections import Counter, defaultdict
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import TimetableSnapshot

TYPES = ("lecture", "practice", "seminar", "lab", "other")
WORKDAYS = 5  # Mon-Fri are always shown; Saturday only when something is on it
LUNCH_MIN = 30  # a break this long (minutes) between two periods is shown as lunch


def weight(lesson: dict) -> float:
    """A lesson held only in week A or B counts as half a class per week."""
    return 0.5 if lesson["week"] else 1.0


def pairs(lessons) -> float:
    return sum(weight(x) for x in lessons)


def _minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


class Timetable:
    def __init__(self, snapshot: TimetableSnapshot):
        d = snapshot.data
        self.id, self.title, self.source, self.fetched_at = snapshot.id, snapshot.title, snapshot.source, snapshot.fetched_at
        self.periods: list[dict] = d["periods"]
        self.days: list[str] = d["days"]
        self.groups: dict[str, dict] = {g["id"]: g for g in d["groups"]}
        self.teachers: dict[str, dict] = {t["id"]: t for t in d["teachers"]}
        self.lessons: list[dict] = d["lessons"]
        self.unscheduled: int = d.get("unscheduled", 0)
        self.by_group, self.by_teacher = defaultdict(list), defaultdict(list)
        for lesson in self.lessons:
            for g in lesson["groups"]:
                self.by_group[g].append(lesson)
            for t in lesson["teachers"]:
                self.by_teacher[t].append(lesson)
        self.faculty_lessons = [x for x in self.lessons if any(self.groups[g]["faculty"] for g in x["groups"])]

    # ---------- Lists ----------
    def faculty_groups(self) -> list[dict]:
        return [g | {"pairs": pairs(self.by_group[g["id"]])} for g in self.groups.values() if g["faculty"]]

    def faculty_teachers(self) -> list[dict]:
        out = []
        for t in self.teachers.values():
            if t["faculty"]:
                mine = self.by_teacher[t["id"]]
                out.append(t | {"pairs": pairs(mine), "groups": len({g for x in mine for g in x["groups"]}),
                                "subjects": len({x["subject"] for x in mine}), "days": len({x["day"] for x in mine})})
        return out

    def courses(self) -> list[tuple[int | None, list[dict]]]:
        by_course = defaultdict(list)
        for g in self.faculty_groups():
            by_course[g["course"]].append(g)
        return sorted(by_course.items(), key=lambda kv: (kv[0] is None, kv[0] or 0))

    # ---------- One week ----------
    def week(self, lessons: list[dict], now: datetime | None = None) -> dict:
        """Grid of days x periods; each cell holds that slot's lessons (every-week first, then week A, B)."""
        used_days = {x["day"] for x in lessons}
        days = [d for d in range(len(self.days)) if d < WORKDAYS or d in used_days]
        cells = defaultdict(list)
        for x in lessons:
            cells[(x["day"], x["period"])].append(x)
        today = now.weekday() if now else None
        minute = now.hour * 60 + now.minute if now else None
        rows = []
        for i, p in enumerate(self.periods):
            nxt = self.periods[i + 1] if i + 1 < len(self.periods) else None
            rows.append({
                "period": p,
                "cells": [sorted(cells[(d, p["n"])], key=lambda x: x["week"]) for d in days],
                "now": minute is not None and _minutes(p["start"]) <= minute < _minutes(p["end"]),
                "lunch": ({"start": p["end"], "end": nxt["start"]}
                          if nxt and _minutes(nxt["start"]) - _minutes(p["end"]) >= LUNCH_MIN else None),
            })
        # Periods after the last class of the week aren't shown (and no lunch line before nothing).
        while len(rows) > 1 and not any(rows[-1]["cells"]):
            rows.pop()
        rows[-1]["lunch"] = None
        return {"days": [{"n": d, "today": d == today, "pairs": pairs(x for x in lessons if x["day"] == d)}
                         for d in days],
                "rows": rows, "alternating": any(x["week"] for x in lessons)}

    def stats(self, lessons: list[dict]) -> dict:
        per_day = Counter()
        for x in lessons:
            per_day[x["day"]] += weight(x)
        busiest = max(per_day, key=lambda d: (per_day[d], -d)) if per_day else None
        return {"pairs": pairs(lessons), "days": len(per_day),
                "subjects": len({x["subject"] for x in lessons}),
                "busiest": {"day": busiest, "pairs": per_day[busiest]} if busiest is not None else None,
                "mix": self.mix(lessons)}

    @staticmethod
    def mix(lessons) -> list[dict]:
        """Share of each lesson type, in a fixed order (so colours never move)."""
        c = Counter()
        for x in lessons:
            c[x["type"]] += weight(x)
        total = sum(c.values()) or 1
        return [{"type": k, "pairs": c[k], "pct": round(100 * c[k] / total, 1)} for k in TYPES if c[k]]

    def subjects(self, lessons: list[dict], people: str) -> list[dict]:
        """One row per subject and lesson type, with the teachers (people='teachers') or groups ('groups')."""
        rows: dict[tuple, dict] = {}
        for x in lessons:
            key = (x["subject"], x["type"])
            row = rows.setdefault(key, {"subject": x["subject"], "type": x["type"], "people": {}, "pairs": 0.0})
            row["pairs"] += weight(x)
            for pid in x[people]:
                row["people"][pid] = None
        order = {k: i for i, k in enumerate(TYPES)}
        return sorted(rows.values(), key=lambda r: (r["subject"].lower(), order[r["type"]]))

    # ---------- Faculty-wide ----------
    def load(self) -> list[list[float]]:
        """Classes running for faculty groups, per [day][period] - for the heatmap."""
        grid = [[0.0] * len(self.periods) for _ in self.days]
        index = {p["n"]: i for i, p in enumerate(self.periods)}
        for x in self.faculty_lessons:
            if x["period"] in index:
                grid[x["day"]][index[x["period"]]] += weight(x)
        return grid


_cache: dict = {}


async def latest(session: AsyncSession) -> Timetable | None:
    """The newest snapshot (parsed once and kept in memory until a newer one appears)."""
    newest = (await session.execute(select(TimetableSnapshot.id, TimetableSnapshot.fetched_at)
                                    .order_by(TimetableSnapshot.id.desc()).limit(1))).first()
    if newest is None:
        return None
    if _cache.get("key") != tuple(newest):  # (id, time): ids restart if the table is ever emptied
        _cache.update(key=tuple(newest), tt=Timetable(await session.get(TimetableSnapshot, newest.id)))
    return _cache["tt"]
