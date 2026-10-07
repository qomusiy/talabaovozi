"""Generate fake-but-realistic Excel files for development.

    python scripts/generate_sample_data.py                  # small + large sets
    python scripts/generate_sample_data.py --students 300 --teachers 30 --out data/sample/custom

Writes students.xlsx, teachers.xlsx and assignments.xlsx. Column headers are in Uzbek,
like a HEMIS export, so the importer's header matching gets exercised.
"""
import argparse
import random
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

MALE_FIRST = ["Aziz", "Jasur", "Bekzod", "Sardor", "Doniyor", "Javohir", "Shoxruh", "Otabek", "Asilbek", "Diyor",
              "Islom", "Sherzod", "Ulug‘bek", "Abdulloh", "Mirjalol", "Temur", "Behruz", "Nodir", "Farrux", "Akmal"]
FEMALE_FIRST = ["Madina", "Dilnoza", "Sevara", "Nilufar", "Malika", "Shahzoda", "Gulnoza", "Zarina", "Mohinur",
                "Kamola", "Sabina", "Munisa", "Durdona", "Ominaxon", "Feruza", "Nigora", "Laylo", "Maftuna"]
SURNAMES = ["Karimov", "Rahimov", "Toshmatov", "Yusupov", "Abdullayev", "Ismoilov", "Qodirov", "Nazarov", "Saidov",
            "Ergashev", "Xolmatov", "Sobirov", "Mirzayev", "Hasanov", "Aliyev", "Jo‘rayev", "Usmonov", "Rustamov",
            "Tursunov", "Normatov", "Boboyev", "Salimov", "Qosimov", "Umarov", "Olimov", "Fayzullayev"]
FATHERS = ["Botir", "Anvar", "Rustam", "Shavkat", "Alisher", "Baxtiyor", "Olim", "Farhod", "Sanjar", "Ikrom"]

SPECIALTIES = {
    "IQT": "Iqtisodiyot",
    "BXA": "Buxgalteriya hisobi va audit",
    "TUR": "Turizm",
    "STAT": "Statistika",
    "FTO‘IT": "FTO‘IT",
    "BB": "BB",
    "ATT": "ATT",
}
LANG_SUFFIX = {"uz": "", "ru": " (ru)", "en": " (ing)"}  # as in the real timetable

DEPARTMENTS = ["Iqtisodiyot nazariyasi", "Buxgalteriya hisobi va audit", "Menejment va marketing",
               "Oliy matematika", "Xorijiy tillar", "Ijtimoiy fanlar", "Axborot texnologiyalari"]
SUBJECTS = {
    "Iqtisodiyot nazariyasi": ["Mikroiqtisodiyot", "Makroiqtisodiyot", "Iqtisodiyot nazariyasi", "Xalqaro iqtisodiyot"],
    "Buxgalteriya hisobi va audit": ["Buxgalteriya hisobi", "Audit", "Moliyaviy hisobot",
                                     "Buxgalteriya hisobining xalqaro standartlari"],
    "Menejment va marketing": ["Menejment", "Marketing", "Turizm iqtisodiyoti", "Biznesni rejalashtirish"],
    "Oliy matematika": ["Oliy matematika", "Ehtimollar nazariyasi", "Ekonometrika", "Statistika"],
    "Xorijiy tillar": ["Ingliz tili", "Rus tili"],
    "Ijtimoiy fanlar": ["O‘zbekistonning eng yangi tarixi", "Falsafa", "Huquqshunoslik"],
    "Axborot texnologiyalari": ["Axborot texnologiyalari", "Iqtisodiy informatika"],
}
POSITIONS = ["assistent", "katta o‘qituvchi", "dotsent", "professor"]
LESSON_TYPES = ["Ma'ruza", "Amaliy", "Seminar", "Laboratoriya"]
CURRENT_ACADEMIC_YEAR = 2026  # 2026/2027


def full_name(rng: random.Random) -> str:
    surname = rng.choice(SURNAMES)
    father = rng.choice(FATHERS)
    if rng.random() < 0.5:
        return f"{surname} {rng.choice(MALE_FIRST)} {father} o‘g‘li"
    return f"{surname}a {rng.choice(FEMALE_FIRST)} {father} qizi"


def teacher_name(rng: random.Random) -> tuple[str, str]:
    surname = rng.choice(SURNAMES)
    female = rng.random() < 0.4
    first = rng.choice(FEMALE_FIRST if female else MALE_FIRST)
    father = rng.choice(FATHERS)
    if female:
        surname += "a"
    patronymic = f"{father}ovna" if female else f"{father}ovich"
    # Timetable style short name, e.g. "Qodirov RS"
    return f"{surname} {first} {patronymic}", f"{surname} {first[0]}{father[0]}"


def make_groups(rng: random.Random, n_students: int) -> list[dict]:
    n_groups = max(4, round(n_students / 25))
    groups, used = [], set()
    while len(groups) < n_groups:
        admission = rng.choice([2023, 2024, 2025, 2026])
        code = rng.choice(list(SPECIALTIES))
        lang = rng.choices(["uz", "ru", "en"], weights=[7, 2, 1])[0]
        name = f"{admission % 100:02d}-{rng.randint(1, 40):02d} {code}{LANG_SUFFIX[lang]}"
        if name in used:
            continue
        used.add(name)
        groups.append({"name": name, "course": CURRENT_ACADEMIC_YEAR - admission + 1,
                       "specialty": SPECIALTIES[code], "language": lang})
    return groups


def write_xlsx(path: Path, headers: list[str], rows: list[list]) -> None:
    wb = Workbook()
    ws = wb.active
    ws.append(headers)
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="1F4E78")
    for row in rows:
        ws.append(row)
    for i, h in enumerate(headers, 1):
        width = max(len(str(h)), *(len(str(r[i - 1])) for r in rows)) if rows else len(h)
        ws.column_dimensions[get_column_letter(i)].width = min(width + 2, 60)
    ws.freeze_panes = "A2"
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)


def generate(n_students: int, n_teachers: int, out: Path, seed: int = 42) -> None:
    rng = random.Random(seed)
    groups = make_groups(rng, n_students)

    # Students: spread across groups, unique HEMIS ids and passports.
    students, passports = [], set()
    for i in range(n_students):
        g = groups[i % len(groups)]
        while True:
            passport = rng.choice(["AA", "AB", "AC", "AD", "AE", "AS", "FA"]) + f"{rng.randint(0, 9_999_999):07d}"
            if passport not in passports:
                passports.add(passport)
                break
        hemis = f"3682{2026 - g['course'] + 1 - 2000:02d}1{i + 1:05d}"
        students.append([hemis, full_name(rng), passport, g["name"], g["course"], g["specialty"],
                         {"uz": "O‘zbek", "ru": "Rus", "en": "Ingliz"}[g["language"]]])
    write_xlsx(out / "students.xlsx",
               ["HEMIS ID", "F.I.Sh.", "Pasport seriya va raqami", "Guruh", "Kurs", "Mutaxassislik", "Ta'lim tili"],
               students)

    # Teachers: each belongs to a department and can teach that department's subjects.
    teachers, short_names = [], set()
    for i in range(n_teachers):
        dept = DEPARTMENTS[i % len(DEPARTMENTS)]
        while True:
            name, short = teacher_name(rng)
            if short not in short_names:
                short_names.add(short)
                break
        teachers.append([f"T{i + 1:03d}", name, short, dept, rng.choice(POSITIONS),
                         f"{rng.randint(1, 4)}-{rng.randint(1, 30):02d}"])
    write_xlsx(out / "teachers.xlsx",
               ["O‘qituvchi ID", "F.I.Sh.", "Qisqa ism", "Kafedra", "Lavozim", "Xona raqami"], teachers)

    # Assignments: every group gets 5-7 subjects, each taught by a teacher from the right department.
    by_dept: dict[str, list[list]] = {}
    for t in teachers:
        by_dept.setdefault(t[3], []).append(t)
    all_subjects = [(d, s) for d, subs in SUBJECTS.items() for s in subs if d in by_dept]
    assignments = []
    for g in groups:
        for dept, subject in rng.sample(all_subjects, k=min(len(all_subjects), rng.randint(5, 7))):
            lecturer = rng.choice(by_dept[dept])
            assignments.append([lecturer[0], lecturer[1], g["name"], subject, "Ma'ruza"])
            # Sometimes a different teacher runs the practical classes.
            if rng.random() < 0.5:
                practice = rng.choice(by_dept[dept])
                kind = rng.choice(LESSON_TYPES[1:])
                assignments.append([practice[0], practice[1], g["name"], subject, kind])
    # Dedupe (same teacher could be drawn twice for the same subject+type).
    assignments = [list(x) for x in dict.fromkeys(tuple(a) for a in assignments)]
    write_xlsx(out / "assignments.xlsx",
               ["O‘qituvchi ID", "O‘qituvchi F.I.Sh.", "Guruh", "Fan", "Mashg‘ulot turi"], assignments)

    print(f"✅ {out}: {len(students)} students, {len(groups)} groups, {len(teachers)} teachers, "
          f"{len(assignments)} assignments")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--students", type=int)
    p.add_argument("--teachers", type=int)
    p.add_argument("--out", type=Path)
    a = p.parse_args()
    if a.students:
        generate(a.students, a.teachers or 15, a.out or Path("data/sample/custom"))
    else:
        generate(50, 15, Path("data/sample/small"))
        generate(2000, 100, Path("data/sample/large"))
