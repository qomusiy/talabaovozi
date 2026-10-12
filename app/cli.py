"""Admin command line.

Everything here can also be done in the dashboard (Data, Surveys, Admins pages).

    python -m app.cli semester-create "2026–2027 kuzgi semestr" 2026-09-07 2027-01-24
    python -m app.cli import-group-sizes hemis_export.xlsx [--clear-missing]   # students per group (no names kept)
    python -m app.cli import-teachers    teachers.xlsx
    python -m app.cli import-assignments assignments.xlsx [--semester "..."]
    python -m app.cli campaign-create "Oraliq so‘rovnoma" --days 14
    python -m app.cli admin-create admin          # asks for a password  (--role viewer | programmer)
    python -m app.cli timetable-sync           # EduPage timetable -> teachers, groups, assignments
    python -m app.cli departments-guess        # kafedra of teachers who have none, guessed from their subjects
    python -m app.cli demo                     # demo feedback over the real data (--clear removes it)
    python -m app.cli reset-data --yes         # delete everything except admins, settings and timetables
    python -m app.cli stats
    python -m app.cli group "25-16 IQT"        # who teaches this group?
"""
import argparse
import asyncio
import getpass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import func, select, text, update
from sqlalchemy.orm import selectinload

from app import demo
from app.db import engine, session_scope
from app.security import hash_password
from app.importers.excel import ImportFileError, import_assignments, import_group_sizes, import_teachers
from app.models import (Admin, Base, BotUser, Feedback, Group, Semester, Subject, SurveyCampaign, Teacher,
                        TeachingAssignment)
from app.services.teaching import guess_departments, health, rebuild_assignments, refresh_from_edupage

KEEP_ON_RESET = ("admins", "app_settings", "timetable_snapshots")


async def current_semester(session, name: str | None) -> Semester:
    q = select(Semester).where(Semester.name == name) if name else select(Semester).where(Semester.is_current)
    semester = (await session.execute(q)).scalar_one_or_none()
    if semester is None:
        raise SystemExit("❌ No such semester. Create one first:  python -m app.cli semester-create "
                         "\"2026-2027 Fall\" 2026-09-07 2027-01-20")
    return semester


def print_report(report) -> None:
    print(("✅ " if not report.errors else "⚠️  ") + report.summary())
    for e in report.messages()[:30]:
        print("   ", e)
    if len(report.errors) > 30:
        print(f"    ... and {len(report.errors) - 30} more")


async def main(args) -> None:
    try:
        async with session_scope() as s:
            match args.cmd:
                case "semester-create":
                    await s.execute(update(Semester).values(is_current=False))
                    s.add(Semester(name=args.name, starts_on=date.fromisoformat(args.starts),
                                   ends_on=date.fromisoformat(args.ends), is_current=True))
                    await s.flush()
                    n = await rebuild_assignments(s)
                    print(f"✅ Semester '{args.name}' created and set as current"
                          + (f"; {n} teaching assignments from the timetable" if n is not None else ""))
                case "admin-create":
                    password = args.password or getpass.getpass("Password: ")
                    if len(password) < 8:
                        raise SystemExit("❌ Password must be at least 8 characters")
                    admin = (await s.execute(select(Admin).where(Admin.username == args.username))).scalar_one_or_none()
                    if admin is None:
                        admin = Admin(username=args.username, role=args.role or "superadmin")
                        s.add(admin)
                    elif args.role:
                        admin.role = args.role
                    admin.password_hash = hash_password(password)
                    admin.is_active = True
                    print(f"✅ Admin '{args.username}' saved")
                case "campaign-create":
                    semester = await current_semester(s, None)
                    now = datetime.now(timezone.utc)
                    s.add(SurveyCampaign(semester=semester, title=args.title, opens_at=now,
                                         closes_at=now + timedelta(days=args.days)))
                    print(f"✅ Survey '{args.title}' is open for {args.days} days")
                case "import-group-sizes":
                    print_report(await import_group_sizes(s, args.file, args.file.name, args.clear_missing, "cli"))
                case "import-teachers":
                    print_report(await import_teachers(s, args.file, args.file.name, "cli"))
                case "import-assignments":
                    semester = await current_semester(s, args.semester)
                    print_report(await import_assignments(s, args.file, semester, args.file.name, "cli"))
                case "timetable-sync":
                    changed, error = await refresh_from_edupage(s, admin="cli")
                    if error:
                        raise SystemExit(f"❌ {error}")
                    h = await health(s)
                    print(("✅ Timetable updated" if changed else "✅ No changes since the last download")
                          + f": {h['snapshot'].title}; {h['assignments']} teaching assignments, {h['teachers']} teachers")
                case "departments-guess":
                    n = await guess_departments(s)
                    if n is None:
                        raise SystemExit("❌ No timetable yet. Run: python -m app.cli timetable-sync")
                    print(f"✅ Kafedra filled in for {n} teachers (from the subjects they teach)")
                case "demo":
                    if args.clear:
                        await demo.clear_demo(s)
                        print("✅ Demo survey rounds and their feedback deleted")
                    else:
                        r = await demo.create_demo(s)
                        print(f"✅ {r['rounds']} demo survey rounds, {r['feedback']:,} evaluations by {r['students']} students")
                case "reset-data":
                    if not args.yes:
                        raise SystemExit("Deletes all bot users, teachers, groups, assignments, surveys and feedback "
                                         "(keeps admins, settings and timetables). Run again with --yes.")
                    tables = [t.name for t in Base.metadata.sorted_tables if t.name not in KEEP_ON_RESET]
                    await s.execute(text(f"TRUNCATE {', '.join(tables)} RESTART IDENTITY CASCADE"))
                    print("✅ Data deleted")
                case "stats":
                    for model in (BotUser, Group, Teacher, Subject, TeachingAssignment, SurveyCampaign, Feedback):
                        n = (await s.execute(select(func.count()).select_from(model))).scalar()
                        print(f"  {model.__tablename__:22} {n}")
                    students = await s.scalar(select(func.coalesce(func.sum(Group.student_count), 0)))
                    print(f"  {'students (group sizes)':22} {students}")
                case "group":
                    group = await s.scalar(select(Group).where(Group.name == args.name))
                    if group is None:
                        raise SystemExit("❌ Group not found")
                    print(f"{group.name} — {group.student_count or '?'} students")
                    rows = (await s.execute(
                        select(TeachingAssignment)
                        .options(selectinload(TeachingAssignment.teacher), selectinload(TeachingAssignment.subject))
                        .join(Semester).where(Semester.is_current, TeachingAssignment.group_id == group.id)
                    )).scalars()
                    for a in rows:
                        print(f"  👨‍🏫 {a.teacher.full_name:40} {a.subject.name} ({a.lesson_type})")
    except (ImportFileError, ValueError) as e:
        raise SystemExit(f"❌ {e}")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("semester-create")
    c.add_argument("name"); c.add_argument("starts", help="YYYY-MM-DD"); c.add_argument("ends", help="YYYY-MM-DD")
    c = sub.add_parser("import-group-sizes", help="how many students each group has (HEMIS export or a count column)")
    c.add_argument("file", type=Path)
    c.add_argument("--clear-missing", action="store_true",
                   help="clear the number of groups that are not in the file")
    c = sub.add_parser("import-teachers"); c.add_argument("file", type=Path)
    c = sub.add_parser("import-assignments"); c.add_argument("file", type=Path)
    c.add_argument("--semester", help="semester name (default: current)")
    c = sub.add_parser("admin-create", help="create an admin or reset their password")
    c.add_argument("username"); c.add_argument("--password")
    c.add_argument("--role", choices=["superadmin", "viewer", "programmer"],
                   help="programmer: also the activity log; hidden from other admins")
    c = sub.add_parser("campaign-create"); c.add_argument("title")
    c.add_argument("--days", type=int, default=14)
    sub.add_parser("timetable-sync", help="download the faculty timetable from EduPage")
    sub.add_parser("departments-guess", help="fill in missing kafedras from the subjects teachers teach")
    c = sub.add_parser("demo", help="demo feedback over the real data"); c.add_argument("--clear", action="store_true")
    c = sub.add_parser("reset-data"); c.add_argument("--yes", action="store_true")
    sub.add_parser("stats")
    c = sub.add_parser("group"); c.add_argument("name")
    asyncio.run(main(p.parse_args()))
