from datetime import date
from io import BytesIO

import pytest
from openpyxl import Workbook
from sqlalchemy import func, select

from app.faculty import group_key
from app.importers.excel import (ImportFileError, import_assignments, import_students, import_teachers, teaching_sheets,
                                 parse_timetable, tidy_name)
from app.importers.templates import TEMPLATES, template_xlsx
from app.models import Group, Semester, Student, Teacher, TeachingAssignment
from app.security import hash_passport, normalize_passport, temporary_passport, verify_passport
from app.services.teaching import name_key, teacher_name_keys


def xlsx(*rows) -> BytesIO:
    wb = Workbook()
    for r in rows:
        wb.active.append(list(r))
    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


def test_passport_normalization():
    assert normalize_passport(" as 348-0990 ") == "AS3480990"
    assert normalize_passport("АС3480990") == "AC3480990"  # Cyrillic letters typed by mistake
    assert verify_passport("as3480990", hash_passport("AS3480990"))
    assert not verify_passport("AS3480991", hash_passport("AS3480990"))


def test_group_keys_match_hemis_and_edupage_spellings():
    assert group_key("26-01-IQT uz") == group_key("26-01 IQT") == "26-01 IQT"
    assert group_key("26-03 IQT ru") == group_key("26-03 IQT (ru)")
    assert group_key("25-03 IQT O‘zbek") == group_key("25-03 IQT (ing)")
    assert group_key("24-20 FTO‘IT") == group_key("24-20 FTO'IT ") == "24-20 FTOIT"
    assert group_key("26-13a BXA") != group_key("26-13 BXA")
    assert group_key("Iqtisodiyot") is None


def test_names():
    assert tidy_name("TOSHMATOV  ESHMAT O‘G‘LI") == "Toshmatov Eshmat O‘g‘li"
    assert tidy_name("Karimov Aziz") == "Karimov Aziz"
    assert name_key("Abdug‘aniyev A.A") == name_key("abdug'aniyev AA") == "abdug'aniyev aa"
    assert {"qodirov rs", "qodirov rustam", "qodirov r"} <= teacher_name_keys("Qodirov Rustam Sobirovich")


async def test_import_students_with_varied_headers(session):
    f = xlsx(
        ["Talabalar ro'yxati"],  # title row above the header, common in real exports
        ["Talaba ID", "Familiya ismi sharifi", "Passport", "Группа", "Talaba kursi"],
        [368211100001.0, "Karimov  Aziz", "as 1234567", "25-16 IQT", "2-kurs"],  # float id, messy spacing
        ["368211100002", "Saidova Madina", "AB7654321", "25-16-IQT uz", "2-kurs"],  # same group, HEMIS spelling
        ["368211100003", "Bad Passport", "12345", "25-16 IQT", "2-kurs"],
        ["368211100002", "Duplicate", "AB7654321", "25-16 IQT", "2-kurs"],
    )
    report = await import_students(session, f)
    assert report.created == 2 and len(report.errors) == 2
    st = (await session.execute(select(Student).where(Student.hemis_id == "368211100001"))).scalar_one()
    assert st.full_name == "Karimov Aziz" and not st.passport_temporary
    assert verify_passport("AS1234567", st.passport_hash)
    group = (await session.execute(select(Group))).scalar_one()
    assert (group.key, group.course) == ("25-16 IQT", 2)


async def test_students_without_passports_get_temporary_codes_until_real_ones_arrive(session):
    """The real HEMIS export has no passport column: students get a temporary code, later replaced."""
    await import_students(session, xlsx(["Talaba ID", "Full Name of student", "Talaba kursi", "Guruh"],
                                        ["376231103290", "TOSHMATOV ESHMAT", "4-kurs", "23-01 IQT"]))
    st = (await session.execute(select(Student))).scalar_one()
    code = temporary_passport("376231103290")
    assert st.passport_temporary and verify_passport(code, st.passport_hash)
    assert st.full_name == "Toshmatov Eshmat"

    # A file with only HEMIS + passport updates the passport and nothing else.
    report = await import_students(session, xlsx(["HEMIS ID", "Pasport"], ["376231103290", "AD1231212"]))
    assert (report.created, report.updated, report.errors) == (0, 1, [])
    await session.refresh(st)
    assert not st.passport_temporary and verify_passport("AD1231212", st.passport_hash)
    assert st.full_name == "Toshmatov Eshmat"

    # A new student needs a name and a group.
    report = await import_students(session, xlsx(["HEMIS ID", "Pasport"], ["376231103299", "AD1231213"]))
    assert report.created == 0 and "needs a name and a group" in report.messages()[0]


async def test_reimport_updates_keeps_telegram_link_and_deactivates_missing(session):
    await import_students(session, xlsx(["HEMIS ID", "F.I.Sh.", "Pasport", "Guruh"],
                                        ["368211100001", "Old Name", "AA1111111", "25-01 IQT"],
                                        ["368211100002", "Graduated", "AA1111112", "25-01 IQT"]))
    st = (await session.execute(select(Student).where(Student.hemis_id == "368211100001"))).scalar_one()
    st.telegram_id = 999
    report = await import_students(session, xlsx(["HEMIS ID", "F.I.Sh.", "Guruh"],
                                                 ["368211100001", "New Name", "25-02 IQT"]),
                                   deactivate_missing=True)
    assert (report.created, report.updated, report.deactivated, report.temporary) == (0, 1, 1, 0)
    await session.refresh(st)
    assert st.full_name == "New Name" and st.telegram_id == 999 and verify_passport("AA1111111", st.passport_hash)


async def test_missing_column_gives_clear_error(session):
    with pytest.raises(ImportFileError, match="HEMIS ID"):
        await import_students(session, xlsx(["F.I.Sh.", "Guruh"], ["A", "G"]))


async def test_assignments_match_teacher_by_id_name_or_timetable_name(session):
    await import_teachers(session, xlsx(["O‘qituvchi ID", "F.I.Sh.", "Jadvaldagi ism", "Kafedra", "Xona raqami"],
                                        ["T1", "Qodirov Rustam Sanjarovich", "Qodirov RS", "Iqtisodiyot", "2-14"]))
    sem = Semester(name="S", starts_on=date(2026, 9, 1), ends_on=date(2027, 1, 20), is_current=True)
    session.add(sem)
    report = await import_assignments(session, xlsx(
        ["O‘qituvchi ID", "O‘qituvchi F.I.Sh.", "Guruh", "Fan", "Mashg‘ulot turi"],
        ["T1", "", "25-16 IQT", "Makroiqtisodiyot", "Ma'ruza"],
        ["", "qodirov rustam sanjarovich", "25-16 IQT", "Makroiqtisodiyot", "Amaliy"],
        ["", "Qodirov R.S.", "25-17 IQT", "Makroiqtisodiyot (S)", ""],  # type from the subject suffix
        ["", "", "25-17 IQT", "Makroiqtisodiyot", "Seminar"],
    ), sem)
    assert report.created == 3 and len(report.errors) == 1
    types = set((await session.execute(select(TeachingAssignment.lesson_type))).scalars())
    assert types == {"lecture", "practice", "seminar"}
    assert (await session.scalar(select(func.count(Teacher.id)))) == 1

    # Re-import replaces instead of duplicating.
    await import_assignments(session, xlsx(["O‘qituvchi ID", "Guruh", "Fan"], ["T1", "25-16 IQT", "Fan"]), sem)
    assert (await session.execute(select(func.count()).select_from(TeachingAssignment))).scalar() == 1


def test_timetable_from_excel():
    data, report = parse_timetable(template_xlsx("timetable", sample=True))
    assert report.errors == [] and data["source"] == "excel"
    assert [g["name"] for g in data["groups"]] == ["25-16 IQT", "25-17 IQT"]
    first, second = data["lessons"]
    assert (first["day"], first["period"], first["type"], len(first["groups"])) == (0, 1, "lecture", 2)
    assert (second["week"], second["type"]) == ("A", "practice")


async def test_every_template_imports(session):
    """Templates offered in the dashboard must always be accepted by their importer."""
    session.add(Semester(name="S", starts_on=date(2026, 9, 1), ends_on=date(2027, 1, 20), is_current=True))
    await session.flush()
    sem = await session.scalar(select(Semester))
    assert not (await import_students(session, template_xlsx("students", sample=True))).errors
    teachers, assignments = teaching_sheets(template_xlsx("teaching", sample=True))
    assert len(teachers) == 2 and len(assignments) == 3
    assert not (await import_teachers(session, None, rows=teachers)).errors
    assert not (await import_assignments(session, None, sem, rows=assignments)).errors
    # The single-purpose importers find their sheet in the two-sheet file too.
    assert not (await import_teachers(session, template_xlsx("teaching", sample=True))).errors
    assert set(TEMPLATES) == {"students", "teaching", "timetable"}


async def test_template_examples_are_never_imported(session):
    """A downloaded template has the example only on its "Namuna" sheet: uploading it unchanged adds nothing."""
    from openpyxl import load_workbook
    wb = load_workbook(template_xlsx("students", {"groups": ["25-16 IQT"]}))
    assert wb.sheetnames[:3] == ["Talabalar", "Yo‘riqnoma", "Namuna"] and wb.active.title == "Talabalar"
    sheet = wb["Talabalar"]
    assert sheet["A2"].value is None and sheet["A2"].number_format == "@"           # empty; HEMIS kept as text
    report = await import_students(session, template_xlsx("students"))
    assert report.created == 0
    assert teaching_sheets(template_xlsx("teaching")) == ([], [])
