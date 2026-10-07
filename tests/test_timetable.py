from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.models import Admin, Teacher, TimetableSnapshot
from app.security import hash_password
from app.timetable import edupage
from app.timetable.view import Timetable
from app.web.main import create_app

INFO = {"tt_num": "11", "text": '"TIIAME" MTU 2026/2027'}


def edupage_raw() -> dict:
    """A tiny timetable in EduPage's format: two faculty sections, a lecture stream, A/B weeks, an unplaced lesson."""
    def table(name, rows):
        return {"id": name, "data_rows": rows}
    days = ["Dushanba", "Seshanba", "Chorshanba", "Payshanba", "Juma", "Shanba"]
    return {"r": {"dbiAccessorRes": {"tables": [
        table("periods", [{"id": str(n), "period": str(n), "starttime": a, "endtime": b} for n, a, b in
                          [(1, "08:00", "09:20"), (2, "09:30", "10:50"), (3, "11:00", "12:20"), (4, "13:00", "14:20")]]),
        table("days", [{"id": str(i), "name": d} for i, d in enumerate(days)]),
        table("classes", [
            {"id": "*1", "name": "Energetika"}, {"id": "*2", "name": "1-bosqich (mx)"}, {"id": "*3", "name": "26-01 EnM"},
            {"id": "*4", "name": "-"},
            {"id": "*5", "name": "Iqtisodiyot"}, {"id": "*6", "name": "1-bosqich (mx)"}, {"id": "*7", "name": "26-01 IQT"},
            {"id": "*8", "name": "26-03  IQT (ru)"}, {"id": "*9", "name": "2-bosqich"}, {"id": "*10", "name": "25-38 FTO‘IT"},
        ]),
        table("subjects", [{"id": "s1", "name": "Makroiqtisodiyot (Ma)"}, {"id": "s2", "name": "Makroiqtisodiyot (A)"},
                           {"id": "s3", "name": "Ingliz tili"}, {"id": "s4", "name": "Fizika (L)"}]),
        table("teachers", [{"id": "-1", "name": "Qodirov RS"}, {"id": "-2", "name": "Saidova  Madina"},
                           {"id": "-3", "name": "Physics Teacher"}]),
        table("classrooms", [{"id": "r1", "name": "A-203 (A)"}, {"id": "r0", "name": "-"}]),
        table("lessons", [
            {"id": "L1", "subjectid": "s1", "teacherids": ["-1"], "classids": ["*7", "*8"]},  # lecture for 2 groups
            {"id": "L2", "subjectid": "s2", "teacherids": ["-2"], "classids": ["*7"]},
            {"id": "L3", "subjectid": "s3", "teacherids": ["-2"], "classids": ["*3"]},  # our teacher, other faculty
            {"id": "L4", "subjectid": "s4", "teacherids": ["-3"], "classids": ["*3"]},  # nothing to do with us
            {"id": "L5", "subjectid": "s2", "teacherids": ["-2"], "classids": ["*10"]},
        ]),
        table("cards", [
            {"lessonid": "L1", "period": "1", "days": "100000", "weeks": "11", "classroomids": ["r1"]},
            {"lessonid": "L1", "period": "4", "days": "001000", "weeks": "11", "classroomids": ["r1"]},
            {"lessonid": "L2", "period": "3", "days": "100000", "weeks": "10", "classroomids": ["r0"]},
            {"lessonid": "L2", "period": "3", "days": "100000", "weeks": "01", "classroomids": []},
            {"lessonid": "L3", "period": "2", "days": "010000", "weeks": "11", "classroomids": ["r1"]},
            {"lessonid": "L4", "period": "1", "days": "001000", "weeks": "11", "classroomids": []},
            {"lessonid": "L5", "period": "", "days": "", "weeks": "", "classroomids": []},  # not placed yet
        ]),
    ]}}}


def test_parse_keeps_the_faculty_and_its_teachers():
    d = edupage.parse(edupage_raw(), "Iqtisodiyot")
    groups = {g["name"]: g for g in d["groups"]}
    assert [n for n, g in groups.items() if g["faculty"]] == ["26-01 IQT", "26-03 IQT (ru)", "25-38 FTO‘IT"]
    assert groups["26-03 IQT (ru)"] | {} == {"id": "8", "name": "26-03 IQT (ru)", "course": 1, "specialty": "IQT",
                                            "lang": "ru", "note": "", "faculty": True}
    assert groups["25-38 FTO‘IT"]["course"] == 2
    assert groups["26-01 EnM"]["faculty"] is False  # shown only because our teacher teaches it
    assert [(t["name"], t["faculty"]) for t in d["teachers"]] == [("Qodirov RS", True), ("Saidova Madina", True)]
    assert [(x["subject"], x["type"], x["week"], x["room"]) for x in d["lessons"]] == [
        ("Makroiqtisodiyot", "lecture", "", "A-203 (A)"),
        ("Makroiqtisodiyot", "practice", "A", ""),
        ("Makroiqtisodiyot", "practice", "B", ""),
        ("Ingliz tili", "other", "", "A-203 (A)"),
        ("Makroiqtisodiyot", "lecture", "", "A-203 (A)"),
    ]
    assert d["lessons"][0]["groups"] == ["7", "8"] and d["unscheduled"] == 1


def test_parse_rejects_a_faculty_it_cannot_find():
    raw = edupage_raw()
    classes = raw["r"]["dbiAccessorRes"]["tables"][2]["data_rows"]
    for c in classes:
        c["name"] = c["name"].replace("IQT", "XYZ").replace("FTO‘IT", "XYZ")
    with pytest.raises(edupage.TimetableError):
        edupage.parse(raw, "Nonexistent")


def make_timetable() -> Timetable:
    return Timetable(TimetableSnapshot(id=1, title="T", source="https://x/timetable/", faculty="Iqtisodiyot",
                                       fetched_at=datetime.now(timezone.utc),
                                       data=edupage.parse(edupage_raw(), "Iqtisodiyot")))


def test_week_grid_and_stats():
    tt = make_timetable()
    lessons = tt.by_group["7"]
    week = tt.week(lessons, now=datetime(2026, 9, 28, 8, 30))  # a Monday, during period 1
    assert [d["n"] for d in week["days"]] == [0, 1, 2, 3, 4]  # Saturday hidden: nothing on it
    assert week["days"][0]["today"] and week["rows"][0]["now"]
    assert week["rows"][2]["lunch"] == {"start": "12:20", "end": "13:00"}
    assert [x["week"] for x in week["rows"][2]["cells"][0]] == ["A", "B"]
    # A week that ends before lunch: later periods and the lunch line are left out.
    short = tt.week(tt.by_teacher["n2"])
    assert len(short["rows"]) == 3 and short["rows"][-1]["lunch"] is None

    stats = tt.stats(lessons)
    assert stats["pairs"] == 3 and stats["days"] == 2 and stats["busiest"]["day"] == 0
    assert [(m["type"], m["pct"]) for m in stats["mix"]] == [("lecture", 66.7), ("practice", 33.3)]
    assert [(r["subject"], r["type"], list(r["people"]), r["pairs"]) for r in tt.subjects(lessons, "teachers")] == [
        ("Makroiqtisodiyot", "lecture", ["n1"], 2.0), ("Makroiqtisodiyot", "practice", ["n2"], 1.0)]
    # Faculty load: Monday period 1 (the lecture) and period 3 (A + B = one class a week); English is another faculty's.
    assert tt.load()[0] == [1.0, 0.0, 1.0, 0.0] and tt.load()[1][1] == 0.0 and tt.load()[2][3] == 1.0


@pytest.fixture
async def admin_client(session, monkeypatch):
    async def fake_download(url):
        return INFO, edupage_raw()
    monkeypatch.setattr(edupage, "download", fake_download)
    session.add_all([Admin(username="admin", password_hash=hash_password("secret123"), role="superadmin"),
                     Teacher(full_name="Qodirov Rustam", short_name="Qodirov RS")])
    await session.commit()
    async with AsyncClient(transport=ASGITransport(app=create_app()), base_url="http://test") as c:
        await c.post("/admin/login", data={"username": "admin", "password": "secret123"})
        yield c


async def test_timetable_pages(admin_client, session):
    c = admin_client
    r = await c.get("/admin/timetable")
    assert r.status_code == 200 and "Dars jadvali hali yuklanmagan" in r.text

    r = await c.post("/admin/timetable/sync", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/admin/timetable"
    r = await c.get("/admin/timetable")
    assert "Jadval yangilandi" in r.text  # shown once
    assert "Jadval yangilandi" not in (await c.get("/admin/timetable")).text
    assert "26-01 IQT" in r.text and "26-01 EnM" not in r.text  # only our groups are listed
    assert "Qodirov RS" in (await c.get("/admin/timetable?tab=teachers")).text

    r = await c.get("/admin/timetable/group/7")
    assert r.status_code == 200
    assert "Makroiqtisodiyot" in r.text and "A hafta" in r.text and "Tushlik" in r.text
    assert 'href="/admin/timetable/teacher/n1' in r.text

    r = await c.get("/admin/timetable/teacher/n2")
    assert r.status_code == 200 and "26-01 EnM" in r.text and "Ingliz tili" in r.text
    assert 'href="/admin/timetable/group/7' in r.text

    # A teacher in our database with the same name is linked both ways.
    ours = await session.scalar(select(Teacher.id))
    assert f'href="/admin/teachers/{ours}' in (await c.get("/admin/timetable/teacher/n1")).text
    assert 'href="/admin/timetable/teacher/n1' in (await c.get(f"/admin/teachers/{ours}")).text

    c.cookies.set("admin_lang", "en")
    assert "Monday" in (await c.get("/admin/timetable/group/7")).text
    assert (await c.get("/admin/timetable/group/999")).status_code == 404
    assert (await c.get("/admin/timetable/teacher/n3")).status_code == 404  # teaches no faculty group


async def test_timetable_sync_failure(admin_client, monkeypatch):
    async def broken(url):
        raise edupage.TimetableError("offline")
    monkeypatch.setattr(edupage, "download", broken)
    r = await admin_client.post("/admin/timetable/sync", data={"next": "/admin/data"}, follow_redirects=False)
    assert r.headers["location"] == "/admin/data"
    page = (await admin_client.get("/admin/data")).text
    assert "EduPage’dan yuklab bo‘lmadi" in page and "offline" in page  # the saved error is shown too
