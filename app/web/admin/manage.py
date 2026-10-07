"""Dashboard pages that run the system: survey rounds, data (semester, timetable, teachers, students),
the bot (settings, messages to students) and admin accounts. Superadmins only, except "My account"."""
import asyncio
import logging
import re
import secrets
from datetime import date, datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from sqlalchemy import DateTime, delete, distinct, func, literal, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app import demo, settings_store
from app.importers import excel
from app.importers.templates import TEMPLATES, template_xlsx
from app.config import get_settings
from app.models import (Admin, Broadcast, Department, Feedback, Group, ImportLog, Semester, Student, SurveyCampaign,
                        Teacher)
from app.bot import chatlog
from app.bot import keyboards as kb
from app.bot.pictures import BadImage, normalize_photo
from app.runtime import (MENU_PHOTO_FILE, fixed_address, menu_photo, request_tunnel_restart, tunnel_status,
                         webapp_url)
from app.security import hash_password, temporary_passport, verify_password
from app.services import admin_link, broadcast, teaching
from app.web.admin import analytics as an
from app.web.admin import display
from app.web.admin.i18n import translator
from app.web.admin.dev import schema as dev_schema
from app.web.admin.views import TASHKENT, flash, get_lang, render, resolve_campaign, xlsx_response
from app.web.deps import current_admin, get_session, superadmin

router = APIRouter(prefix="/admin")
log = logging.getLogger("admin")
MAX_UPLOAD = 10 * 1024 * 1024
BOT_ONLINE_WITHIN = timedelta(minutes=3)


def back(url: str) -> RedirectResponse:
    return RedirectResponse(url, status_code=303)


def _t(request: Request):
    return translator(get_lang(request))


def local_input(dt: datetime) -> str:
    """For <input type="datetime-local"> (Tashkent time)."""
    return dt.astimezone(TASHKENT).strftime("%Y-%m-%dT%H:%M")


def parse_local(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value).replace(tzinfo=TASHKENT)
    except ValueError:
        return None


def semester_bounds(sem: Semester) -> tuple[datetime, datetime]:
    """A semester as Tashkent times: from its first day 00:00 to the end of its last day."""
    return (datetime.combine(sem.starts_on, datetime.min.time(), TASHKENT),
            datetime.combine(sem.ends_on, datetime.max.time().replace(microsecond=0), TASHKENT))


async def read_upload(file: UploadFile) -> BytesIO:
    data = await file.read(MAX_UPLOAD + 1)
    if len(data) > MAX_UPLOAD:
        raise excel.ImportFileError("too_big")
    if not data:
        raise excel.ImportFileError("empty")
    return BytesIO(data)


def report_text(t, report: excel.ImportReport) -> str:
    """'2091 ta qo‘shildi · 3 ta xato — 5-qator: ...' in the dashboard's language."""
    parts = [t(f"imp_{k}", n=v) for k, v in (("created", report.created), ("updated", report.updated),
                                             ("skipped", report.skipped), ("temporary", report.temporary),
                                             ("deactivated", report.deactivated), ("errors", len(report.errors)))
             if v or k in ("created", "updated")]
    details = "; ".join((t("imp_row", row=row) + ": " if row else "") + t(f"imp_{code}", **values)
                        for row, code, values in report.errors[:3])
    return " · ".join(parts) + (f" — {details}" if details else "")


def file_error(request: Request, e: "excel.ImportFileError") -> None:
    flash(request, "bad", _t(request)(f"impf_{e.code}", **e.params))


# ================================================================ Survey rounds

def round_status(c: SurveyCampaign, now: datetime) -> str:
    return "upcoming" if now < c.opens_at else "open" if now < c.closes_at else "closed"


@router.get("/surveys", response_class=HTMLResponse)
async def surveys(request: Request, admin: Admin = Depends(superadmin), session: AsyncSession = Depends(get_session, scope="function")):
    cid, campaigns = await resolve_campaign(session, None)
    now = datetime.now(timezone.utc)
    stats = dict((c, (n, p)) for c, n, p in (await session.execute(
        select(Feedback.campaign_id, func.count(Feedback.id), func.count(distinct(Feedback.student_id)))
        .group_by(Feedback.campaign_id))).all())
    students = await session.scalar(select(func.count(Student.id)).where(Student.is_active)) or 0
    fmt = "%d.%m.%Y %H:%M"
    rows = []
    for c in campaigns:
        start, end = semester_bounds(c.semester)
        rows.append({"c": c, "status": round_status(c, now), "n": stats.get(c.id, (0, 0))[0],
                     "participants": stats.get(c.id, (0, 0))[1], "opens": local_input(c.opens_at),
                     "closes": local_input(c.closes_at), "min": local_input(start), "max": local_input(end),
                     "days": max(1, round((c.closes_at - c.opens_at).total_seconds() / 86400)),
                     "outside": c.opens_at < start or c.closes_at > end,
                     "period": f"{c.opens_at.astimezone(TASHKENT).strftime(fmt)} – {c.closes_at.astimezone(TASHKENT).strftime(fmt)}"})
    semester = await teaching.current_semester(session)
    bounds = semester_bounds(semester) if semester else None
    start = now.astimezone(TASHKENT).replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    return await render(request, "admin/surveys.html", admin, (cid, campaigns), rows=rows, students=students,
                        semester=semester, edit_id=_edit_id(request),
                        sem_min=local_input(bounds[0]) if bounds else "", sem_max=local_input(bounds[1]) if bounds else "",
                        new_opens=local_input(start), new_closes=local_input(start + timedelta(days=10)))


def _edit_id(request: Request) -> int | None:
    """?edit=<id>: reopen that round's form (after an error, so the admin sees what to fix)."""
    raw = request.query_params.get("edit", "")
    return int(raw) if raw.isdigit() else None


def _minute(column):
    return func.date_trunc("minute", column)


async def _check_round(session: AsyncSession, t, opens: datetime | None, closes: datetime | None, semester: Semester,
                       skip_id: int | None = None) -> str | None:
    """Error text, or None if the round is fine. A round lies inside its semester, and rounds may not overlap:
    students rate in one round at a time. Times are compared to the minute, like the form shows them - a round
    closed at 19:57:09 and the next one opened at 19:57 don't overlap."""
    if opens is None or closes is None:
        return t("sv_err_format")
    if closes <= opens:
        return t("sv_err_dates")
    start, end = semester_bounds(semester)
    if opens < start or closes > end:
        return t("sv_err_outside", name=semester.name, start=semester.starts_on.strftime("%d.%m.%Y"),
                 end=semester.ends_on.strftime("%d.%m.%Y"))
    other = await session.scalar(select(SurveyCampaign).where(
        SurveyCampaign.id != (skip_id or 0),
        _minute(SurveyCampaign.opens_at) < _minute(literal(closes, DateTime(timezone=True))),
        _minute(SurveyCampaign.closes_at) > _minute(literal(opens, DateTime(timezone=True)))))
    if other:
        fmt = "%d.%m.%Y %H:%M"
        return t("sv_err_overlap", title=other.title, opens=other.opens_at.astimezone(TASHKENT).strftime(fmt),
                 closes=other.closes_at.astimezone(TASHKENT).strftime(fmt))
    return None


@router.post("/surveys/new")
async def survey_create(request: Request, title: str = Form(...), opens: str = Form(...), closes: str = Form(...),
                        admin: Admin = Depends(superadmin), session: AsyncSession = Depends(get_session, scope="function")):
    t = _t(request)
    semester = await teaching.current_semester(session)
    if semester is None:
        flash(request, "bad", t("sv_err_semester"))
        return back("/admin/surveys")
    opens_at, closes_at = parse_local(opens), parse_local(closes)
    if error := await _check_round(session, t, opens_at, closes_at, semester):
        flash(request, "bad", error)
        return back("/admin/surveys")
    session.add(SurveyCampaign(semester=semester, title=title.strip()[:255], opens_at=opens_at, closes_at=closes_at))
    flash(request, "good", t("sv_created", title=title.strip()))
    return back("/admin/surveys")


@router.post("/surveys/{cid}/edit")
async def survey_edit(request: Request, cid: int, title: str = Form(...), opens: str = Form(...),
                      closes: str = Form(...), admin: Admin = Depends(superadmin),
                      session: AsyncSession = Depends(get_session, scope="function")):
    t = _t(request)
    c = await session.get(SurveyCampaign, cid) or _404()
    await session.refresh(c, ["semester"])
    # The form shows minutes only: a time left as it was keeps its seconds (opened/closed "now" at 19:57:12).
    opens_at = c.opens_at if opens == local_input(c.opens_at) else parse_local(opens)
    closes_at = c.closes_at if closes == local_input(c.closes_at) else parse_local(closes)
    if error := await _check_round(session, t, opens_at, closes_at, c.semester, skip_id=cid):
        flash(request, "bad", error)
        return back(f"/admin/surveys?edit={cid}")
    c.title, c.opens_at, c.closes_at = title.strip()[:255], opens_at, closes_at
    flash(request, "good", t("saved"))
    return back("/admin/surveys")


@router.post("/surveys/{cid}/close")
async def survey_close(request: Request, cid: int, admin: Admin = Depends(superadmin),
                       session: AsyncSession = Depends(get_session, scope="function")):
    c = await session.get(SurveyCampaign, cid) or _404()
    now = datetime.now(timezone.utc)
    if c.opens_at < now < c.closes_at:
        c.closes_at = now
        flash(request, "good", _t(request)("sv_closed", title=c.title))
    return back("/admin/surveys")


@router.post("/surveys/{cid}/open")
async def survey_open(request: Request, cid: int, admin: Admin = Depends(superadmin),
                      session: AsyncSession = Depends(get_session, scope="function")):
    """Open a planned round now (keeps its closing time)."""
    t = _t(request)
    c = await session.get(SurveyCampaign, cid) or _404()
    await session.refresh(c, ["semester"])
    now = datetime.now(timezone.utc)
    if now < c.opens_at:
        if error := await _check_round(session, t, now, c.closes_at, c.semester, skip_id=cid):
            flash(request, "bad", error)
        else:
            c.opens_at = now
            flash(request, "good", t("sv_opened", title=c.title))
    return back("/admin/surveys")


@router.post("/surveys/{cid}/delete")
async def survey_delete(request: Request, cid: int, admin: Admin = Depends(superadmin),
                        session: AsyncSession = Depends(get_session, scope="function")):
    c = await session.get(SurveyCampaign, cid) or _404()
    await session.execute(delete(SurveyCampaign).where(SurveyCampaign.id == cid))  # feedback goes with it
    flash(request, "good", _t(request)("sv_deleted", title=c.title))
    return back("/admin/surveys")


@router.post("/surveys/demo/clear")
async def demo_clear(request: Request, admin: Admin = Depends(superadmin), session: AsyncSession = Depends(get_session, scope="function")):
    await demo.clear_demo(session)
    flash(request, "good", _t(request)("demo_cleared"))
    return back("/admin/surveys")


@router.post("/surveys/demo/create")
async def demo_create(request: Request, admin: Admin = Depends(superadmin), session: AsyncSession = Depends(get_session, scope="function")):
    t = _t(request)
    if await demo.has_demo(session):
        return back("/admin/surveys")
    now = datetime.now(timezone.utc)
    if await session.scalar(select(SurveyCampaign.id).where(SurveyCampaign.closes_at > now - timedelta(days=21)).limit(1)):
        flash(request, "bad", t("demo_err_rounds"))
        return back("/admin/surveys")
    try:
        r = await demo.create_demo(session)
    except ValueError:
        flash(request, "bad", t("sv_err_semester"))
        return back("/admin/surveys")
    flash(request, "good", t("demo_created", n=f"{r['feedback']:,}".replace(",", " ")))
    return back("/admin/surveys")


def _404():
    raise HTTPException(404)


# ================================================================ Data: semester, timetable, teachers, students

@router.get("/data", response_class=HTMLResponse)
async def data_page(request: Request, admin: Admin = Depends(superadmin), session: AsyncSession = Depends(get_session, scope="function")):
    cid, campaigns = await resolve_campaign(session, None)
    settings = await settings_store.load(session, fresh=True)
    checked = settings["timetable_checked_at"]
    history = list((await session.execute(select(ImportLog).order_by(ImportLog.id.desc()).limit(15))).scalars())
    semesters = list((await session.execute(select(Semester).order_by(Semester.starts_on.desc()))).scalars())
    today = date.today()
    return await render(
        request, "admin/data.html", admin, (cid, campaigns), h=await teaching.health(session), settings=settings,
        checked=datetime.fromisoformat(checked).astimezone(TASHKENT).strftime("%d.%m.%Y %H:%M") if checked else None,
        history=history, semesters=semesters, new_year=today.year if today.month >= 8 else today.year - 1,
        schema=await dev_schema(session) if admin.is_programmer else None,
        hidden_users=await hidden_usernames(session, admin),
    )


def _upload_result(request: Request, report: excel.ImportReport) -> None:
    t = _t(request)
    flash(request, "bad" if report.errors and not (report.created or report.updated) else "good",
          t("data_upload_done", result=report_text(t, report)))


@router.post("/data/students")
async def upload_students(request: Request, file: UploadFile = File(...), deactivate_missing: bool = Form(False),
                          admin: Admin = Depends(superadmin), session: AsyncSession = Depends(get_session, scope="function")):
    try:
        report = await excel.import_students(session, await read_upload(file), file.filename or "students.xlsx",
                                             deactivate_missing, admin.username)
    except excel.ImportFileError as e:
        file_error(request, e)
        return back("/admin/data#students")
    _upload_result(request, report)
    return back("/admin/data#students")


@router.post("/data/teachers")
async def upload_teachers(request: Request, file: UploadFile = File(...), admin: Admin = Depends(superadmin),
                          session: AsyncSession = Depends(get_session, scope="function")):
    try:
        report = await excel.import_teachers(session, await read_upload(file), file.filename or "teachers.xlsx",
                                             admin.username)
    except excel.ImportFileError as e:
        file_error(request, e)
        return back("/admin/data#teaching")
    _upload_result(request, report)
    return back("/admin/data#teaching")


@router.post("/data/teaching")
async def upload_teaching(request: Request, file: UploadFile = File(...), admin: Admin = Depends(superadmin),
                          session: AsyncSession = Depends(get_session, scope="function")):
    """One file for both: teacher details ("O‘qituvchilar" sheet) and who teaches whom ("Biriktirishlar")."""
    t = _t(request)
    name = file.filename or "teaching.xlsx"
    try:
        data = await read_upload(file)
        teacher_rows, assignment_rows = excel.teaching_sheets(data)
    except excel.ImportFileError as e:
        file_error(request, e)
        return back("/admin/data#teaching")
    if not teacher_rows and not assignment_rows:
        flash(request, "bad", t("impf_no_rows"))
        return back("/admin/data#teaching")
    results = []
    if teacher_rows:
        report = await excel.import_teachers(session, data, name, admin.username, rows=teacher_rows)
        results.append(t("up_part_teachers") + ": " + report_text(t, report))
    if assignment_rows:
        semester = await teaching.current_semester(session)
        if semester is None:
            flash(request, "bad", t("sv_err_semester"))
            return back("/admin/data#teaching")
        report = await excel.import_assignments(session, data, semester, name, admin.username, rows=assignment_rows)
        if report.created:
            await settings_store.save(session, assignments_source="excel")
        results.append(t("up_part_assignments") + ": " + report_text(t, report))
    flash(request, "good", t("data_upload_done", result=" | ".join(results)))
    return back("/admin/data#teaching")


@router.post("/data/assignments")
async def upload_assignments(request: Request, file: UploadFile = File(...), admin: Admin = Depends(superadmin),
                             session: AsyncSession = Depends(get_session, scope="function")):
    """Who teaches whom, from Excel. From now on the timetable no longer rebuilds it (until switched back)."""
    semester = await teaching.current_semester(session)
    if semester is None:
        flash(request, "bad", _t(request)("sv_err_semester"))
        return back("/admin/data#teaching")
    try:
        report = await excel.import_assignments(session, await read_upload(file), semester,
                                                file.filename or "assignments.xlsx", admin.username)
    except excel.ImportFileError as e:
        file_error(request, e)
        return back("/admin/data#teaching")
    if report.created:
        await settings_store.save(session, assignments_source="excel")
    _upload_result(request, report)
    return back("/admin/data#teaching")


@router.post("/data/timetable")
async def upload_timetable(request: Request, file: UploadFile = File(...), admin: Admin = Depends(superadmin),
                           session: AsyncSession = Depends(get_session, scope="function")):
    """A timetable from Excel, for when EduPage can't be used. Automatic EduPage checks are switched off."""
    t = _t(request)
    try:
        data, report = excel.parse_timetable(await read_upload(file))
    except excel.ImportFileError as e:
        file_error(request, e)
        return back("/admin/data#timetable")
    if not data["lessons"]:
        flash(request, "bad", t("data_upload_done", result=report_text(t, report)))
        return back("/admin/data#timetable")
    name = file.filename or "timetable.xlsx"
    await teaching.store_timetable(session, data, title=name, source=f"excel:{name}", admin=admin.username)
    await settings_store.save(session, timetable_auto_sync=False)
    _upload_result(request, report)
    return back("/admin/data#timetable")


@router.post("/data/settings")
async def data_settings(request: Request, timetable_auto_sync: bool = Form(False), timetable_sync_hours: int = Form(6),
                        assignments_source: str = Form("timetable"), excluded_subjects: str = Form(""),
                        admin: Admin = Depends(superadmin), session: AsyncSession = Depends(get_session, scope="function")):
    t = _t(request)
    before = await settings_store.load(session, fresh=True)
    excluded = sorted({line.strip() for line in excluded_subjects.splitlines() if line.strip()})
    source = assignments_source if assignments_source in ("timetable", "excel") else "timetable"
    await settings_store.save(session, timetable_auto_sync=timetable_auto_sync,
                              timetable_sync_hours=max(1, min(168, timetable_sync_hours)),
                              assignments_source=source, excluded_subjects=excluded)
    message = t("saved")
    if source == "timetable" and (before["assignments_source"] != source or sorted(before["excluded_subjects"]) != excluded):
        n = await teaching.rebuild_assignments(session)
        if n is not None:
            message = t("data_rebuilt", n=n)
    flash(request, "good", message)
    return back("/admin/data#teaching")


@router.post("/data/assignments/rebuild")
async def rebuild(request: Request, admin: Admin = Depends(superadmin), session: AsyncSession = Depends(get_session, scope="function")):
    t = _t(request)
    n = await teaching.rebuild_assignments(session)
    if n is None:
        flash(request, "bad", t("data_rebuild_failed"))
    else:
        await settings_store.save(session, assignments_source="timetable")
        flash(request, "good", t("data_rebuilt", n=n))
    return back("/admin/data#teaching")


@router.post("/data/semester")
async def semester_save(request: Request, name: str = Form(...), starts: date = Form(...), ends: date = Form(...),
                        semester_id: int | None = Form(None), admin: Admin = Depends(superadmin),
                        session: AsyncSession = Depends(get_session, scope="function")):
    """Create a new semester (it becomes the current one) or edit an existing one."""
    t = _t(request)
    if ends <= starts:
        flash(request, "bad", t("sv_err_dates"))
        return back("/admin/data#semester")
    name = name.strip()[:64]
    clash = await session.scalar(select(Semester).where(Semester.name == name, Semester.id != (semester_id or 0)))
    if clash:
        flash(request, "bad", t("sem_err_name"))
        return back("/admin/data#semester")
    if semester_id:
        sem = await session.get(Semester, semester_id) or _404()
        sem.name, sem.starts_on, sem.ends_on = name, starts, ends
        flash(request, "good", t("saved"))
    else:
        await session.execute(update(Semester).values(is_current=False))
        session.add(Semester(name=name, starts_on=starts, ends_on=ends, is_current=True))
        await session.flush()
        n = await teaching.rebuild_assignments(session) if await settings_store.get(session, "assignments_source") == "timetable" else None
        flash(request, "good", t("sem_created", name=name) + (" " + t("data_rebuilt", n=n) if n is not None else ""))
    return back("/admin/data#semester")


@router.post("/data/semester/{sid}/current")
async def semester_current(request: Request, sid: int, admin: Admin = Depends(superadmin),
                           session: AsyncSession = Depends(get_session, scope="function")):
    sem = await session.get(Semester, sid) or _404()
    await session.execute(update(Semester).values(is_current=False))
    sem.is_current = True
    await session.flush()
    if await settings_store.get(session, "assignments_source") == "timetable":
        await teaching.rebuild_assignments(session)
    flash(request, "good", _t(request)("sem_now_current", name=sem.name))
    return back("/admin/data#semester")


@router.get("/data/template/{kind}.xlsx")
async def template(kind: str, admin: Admin = Depends(superadmin), session: AsyncSession = Depends(get_session, scope="function")):
    """A template with drop-downs filled from the database: groups, teachers (as the timetable writes them), kafedras."""
    if kind not in TEMPLATES:
        raise HTTPException(404)
    lists = {
        "groups": list((await session.execute(select(Group.name).order_by(Group.name))).scalars()),
        "teachers": sorted({n for n in (await session.execute(
            select(func.coalesce(Teacher.short_name, Teacher.full_name)).where(Teacher.is_active))).scalars() if n}),
        "departments": list((await session.execute(select(Department.name).order_by(Department.name))).scalars()),
    }
    names = {"students": "talabalar", "teaching": "oqituvchilar_va_biriktirishlar", "timetable": "dars_jadvali"}
    return StreamingResponse(template_xlsx(kind, lists), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": f'attachment; filename="{names.get(kind, kind)}_namuna.xlsx"'})


@router.get("/data/temporary-codes.xlsx")
async def temporary_codes(request: Request, admin: Admin = Depends(superadmin), session: AsyncSession = Depends(get_session, scope="function")):
    """Login codes of students who don't have their real passport code imported yet (for testing the bot)."""
    t = _t(request)
    rows = (await session.execute(
        select(Student.hemis_id, Student.full_name, Group.name).outerjoin(Group, Group.id == Student.group_id)
        .where(Student.is_active, Student.passport_temporary).order_by(Group.name, Student.full_name))).all()
    return xlsx_response("temporary_codes", ["HEMIS ID", t("col_student"), t("col_group"), t("col_temp_code")],
                         [(h, n, g, temporary_passport(h)) for h, n, g in rows])


@router.post("/students/{sid}/unlink")
async def student_unlink(request: Request, sid: int, admin: Admin = Depends(superadmin),
                         session: AsyncSession = Depends(get_session, scope="function")):
    """Free a student's account from its Telegram link (new phone, or someone else logged in by mistake)."""
    st = await session.get(Student, sid) or _404()
    st.telegram_id, st.survey_message_id = None, None
    flash(request, "good", _t(request)("st_unlinked", name=st.full_name))
    return back(request.headers.get("referer") or "/admin/students")


# ================================================================ Bot

def _bot_status(settings: dict) -> dict:
    seen = settings["bot_seen_at"]
    seen_at = datetime.fromisoformat(seen) if seen else None
    online = bool(seen_at and datetime.now(timezone.utc) - seen_at < BOT_ONLINE_WITHIN)
    return {"online": online, "seen": seen_at.astimezone(TASHKENT).strftime("%d.%m.%Y %H:%M") if seen_at else None,
            "username": settings["bot_username"]}


@router.get("/bot", response_class=HTMLResponse)
async def bot_page(request: Request, admin: Admin = Depends(superadmin), session: AsyncSession = Depends(get_session, scope="function")):
    cid, campaigns = await resolve_campaign(session, None)
    settings = await settings_store.load(session, fresh=True)
    support, tech = settings_store.contacts(settings)
    in_bot = await session.scalar(select(func.count(Student.id)).where(Student.is_active, Student.telegram_id.is_not(None)))
    history = list((await session.execute(select(Broadcast).order_by(Broadcast.id.desc()).limit(10))).scalars())
    groups = await an.all_groups(session)
    courses = sorted({g.course for g in groups if g.course})
    departments = list((await session.execute(select(Department).order_by(Department.name))).scalars())
    specialties = sorted({g.code for g in groups if g.code})
    names = {"group": {str(g.id): g.name for g in groups}, "department": {str(d.id): d.name for d in departments}}
    t = _t(request)
    now = datetime.now(timezone.utc)
    open_round = next((c for c in campaigns if c.opens_at <= now < c.closes_at), None)
    return await render(request, "admin/bot.html", admin, (cid, campaigns), settings=settings, status=_bot_status(settings),
                        support=support, tech=tech, in_bot=in_bot, history=history, groups=groups, courses=courses,
                        departments=departments, specialties=specialties,
                        audiences={b.id: audience_label(t, b, names) for b in history}, env=get_settings(),
                        menu_custom=MENU_PHOTO_FILE.is_file(), menu_stamp=_stamp(menu_photo()),
                        public_url=webapp_url(), open_round=open_round, tunnel=_tunnel_view(),
                        hidden_users=await hidden_usernames(session, admin),
                        sending=any(b.status in ("queued", "sending") for b in history))


def _stamp(path) -> int:
    """Changes when the file changes (so the browser shows a new menu picture at once)."""
    return path.stat().st_mtime_ns // 1_000_000 if path else 0


def _tunnel_view() -> dict:
    """The public address as scripts/tunnel.sh last checked it, for the Bot page."""
    st = tunnel_status()
    ago = int(datetime.now(timezone.utc).timestamp()) - st["at"] if st["at"] else None
    state = st["state"]
    if state == "ok" and ago is not None and ago > 300:  # the watchdog stopped checking: don't claim it works
        state = "unknown"
    return {"state": state, "fails": st["fails"], "ago_min": ago // 60 if ago is not None else None,
            "fixed": fixed_address()}


async def hidden_usernames(session: AsyncSession, admin: Admin) -> set[str]:
    """Programmer accounts, shown as "tizim" (system) to everyone else (e.g. who sent a message)."""
    if admin.is_programmer:
        return set()
    return set((await session.execute(select(Admin.username).where(Admin.role == "programmer"))).scalars())


@router.post("/bot/tunnel")
async def new_address(request: Request, admin: Admin = Depends(superadmin)):
    """A fresh public address (the old one stopped working). The bot moves its buttons there by itself."""
    request_tunnel_restart()
    flash(request, "good", _t(request)("tun_requested"))
    return back("/admin/bot")


@router.post("/bot/online")
async def dashboard_online_switch(request: Request, admin_online: bool = Form(False), admin: Admin = Depends(superadmin),
                                  session: AsyncSession = Depends(get_session, scope="function")):
    """Open the dashboard through the public address too (phones, other computers) - or keep it on this computer."""
    await settings_store.save(session, admin_online=admin_online)
    flash(request, "good", _t(request)("online_on" if admin_online else "online_off"))
    return back("/admin/bot")


def channel_link(value: str) -> str | None:
    """'@iqtisodiyot_uz1', 't.me/x' or 'https://t.me/x' -> 'https://t.me/x'; '' stays ''; None if it isn't one."""
    v = value.strip()
    if not v:
        return ""
    if v.startswith("@"):
        v = "https://t.me/" + v[1:]
    v = re.sub(r"^(https?://)?(www\.)?(t\.me|telegram\.me)/", "https://t.me/", v)
    return v if re.fullmatch(r"https://t\.me/[A-Za-z0-9_+/-]{3,}", v) else None


@router.post("/bot/settings")
async def bot_settings(request: Request, login_open: bool = Form(False), survey_comments: bool = Form(False),
                       survey_edit: bool = Form(False), reminders: bool = Form(False), bot_reactions: bool = Form(False),
                       survey_comment_required: bool = Form(False),
                       survey_notice: str = Form(""), support_contact: str = Form(""), tech_contact: str = Form(""),
                       admin_telegram_ids: str = Form(""), channel_url: str = Form(""),
                       admin: Admin = Depends(superadmin), session: AsyncSession = Depends(get_session, scope="function")):
    t = _t(request)
    ids = []
    for part in admin_telegram_ids.replace(",", " ").split():
        if not part.lstrip("-").isdigit():
            flash(request, "bad", t("bot_err_ids", value=part))
            return back("/admin/bot")
        ids.append(int(part))
    channel = channel_link(channel_url)
    if channel is None:
        flash(request, "bad", t("bot_err_channel", value=channel_url.strip()))
        return back("/admin/bot")
    await settings_store.save(session, login_open=login_open, survey_comments=survey_comments, survey_edit=survey_edit,
                              reminders=reminders, bot_reactions=bot_reactions, channel_url=channel,
                              survey_comment_required=survey_comment_required,
                              survey_notice=survey_notice.strip()[:500], support_contact=support_contact.strip()[:64],
                              tech_contact=tech_contact.strip()[:64], admin_telegram_ids=ids)
    flash(request, "good", t("bot_saved"))
    return back("/admin/bot")


# ---------- The picture on the bot's menu card ----------

@router.get("/bot/menu-photo")
async def menu_photo_file(admin: Admin = Depends(superadmin)):
    path = menu_photo()
    if path is None:
        raise HTTPException(404)
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "no-cache"})


@router.post("/bot/menu-photo")
async def menu_photo_upload(request: Request, photo: UploadFile = File(...), admin: Admin = Depends(superadmin)):
    """A new picture for the menu card: the bot shows it on cards it sends from now on (old cards keep theirs)."""
    t = _t(request)
    data = await photo.read(MEDIA_LIMITS["photo"] + 1)
    try:
        if len(data) > MEDIA_LIMITS["photo"]:
            raise BadImage("too big")
        jpeg = await asyncio.to_thread(normalize_photo, data, 1600)
    except BadImage:
        flash(request, "bad", t("mp_err"))
        return back("/admin/bot#menu-photo")
    MENU_PHOTO_FILE.parent.mkdir(parents=True, exist_ok=True)
    MENU_PHOTO_FILE.write_bytes(jpeg)
    flash(request, "good", t("mp_saved"))
    return back("/admin/bot#menu-photo")


@router.post("/bot/menu-photo/reset")
async def menu_photo_reset(request: Request, admin: Admin = Depends(superadmin)):
    MENU_PHOTO_FILE.unlink(missing_ok=True)
    flash(request, "good", _t(request)("mp_reset_done"))
    return back("/admin/bot#menu-photo")


# ---------- Messages to students ----------

MEDIA_LIMITS = {"photo": 10 * 1024 * 1024, "video": 50 * 1024 * 1024, "document": 50 * 1024 * 1024}
PHOTO_TYPES = {"image/jpeg", "image/png", "image/webp"}
VIDEO_TYPES = {".mp4", ".mov", ".m4v", ".webm"}


class MediaError(Exception):
    def __init__(self, code: str):
        self.code = code


async def save_media(file: UploadFile, stem: str) -> tuple[str, str]:
    """Stores an uploaded photo / video / file next to the message; returns (kind, file name)."""
    name = file.filename or "file"
    ext = Path(name).suffix.lower()[:8]
    ctype = (file.content_type or "").lower()
    kind = ("photo" if ctype in PHOTO_TYPES or ext in (".jpg", ".jpeg", ".png", ".webp")
            else "video" if ctype.startswith("video/") or ext in VIDEO_TYPES else "document")
    data = await file.read(MEDIA_LIMITS[kind] + 1)
    if not data:
        raise MediaError("empty_file")
    if len(data) > MEDIA_LIMITS[kind]:
        raise MediaError(f"too_big_{kind}")
    if kind == "photo":
        try:
            data, ext = await asyncio.to_thread(normalize_photo, data), ".jpg"
        except BadImage:
            raise MediaError("bad_image") from None
    stored = f"{stem}{ext or '.bin'}"
    broadcast.BROADCAST_MEDIA.mkdir(parents=True, exist_ok=True)
    (broadcast.BROADCAST_MEDIA / stored).write_bytes(data)
    return kind, stored


def _audience_ok(audience: str, survey: str) -> bool:
    return audience in broadcast.AUDIENCES and audience != "unfinished" and survey in broadcast.SURVEY_FILTERS


@router.get("/bot/audience")
async def audience_size(request: Request, audience: str = "all", survey: str = "", admin: Admin = Depends(superadmin),
                        session: AsyncSession = Depends(get_session, scope="function")):
    values = request.query_params.getlist("values")
    if not _audience_ok(audience, survey):
        return JSONResponse({"n": 0})
    return JSONResponse({"n": len(await broadcast.recipients(session, audience, values, survey))})


@router.post("/bot/broadcast")
async def send_broadcast(request: Request, text: str = Form(""), audience: str = Form("all"),
                         values: list[str] = Form([]), survey: str = Form(""), survey_button: bool = Form(False),
                         media: UploadFile | None = File(None),
                         admin: Admin = Depends(superadmin), session: AsyncSession = Depends(get_session, scope="function")):
    t = _t(request)
    text = text.strip()
    has_media = bool(media and media.filename)
    if (not text and not has_media) or len(text) > 3500 or not _audience_ok(audience, survey):
        flash(request, "bad", t("bc_err_text"))
        return back("/admin/bot")
    n = len(await broadcast.recipients(session, audience, values, survey))
    if not n:
        flash(request, "bad", t("bc_err_empty"))
        return back("/admin/bot")
    b = Broadcast(text=text, audience=audience, filters={"values": values, "survey": survey},
                  survey_button=survey_button, total=n, created_by=admin.username)
    session.add(b)
    await session.flush()
    if has_media:
        try:
            b.media_kind, b.media_name = await save_media(media, str(b.id))
        except MediaError as e:
            await session.rollback()
            flash(request, "bad", t(f"bc_err_{e.code}"))
            return back("/admin/bot")
    await session.commit()  # the sender reads it from its own session
    broadcast.start(b.id)
    flash(request, "good", t("bc_started", n=n))
    return back("/admin/bot")


@router.post("/bot/broadcast/test")
async def test_broadcast(request: Request, text: str = Form(""), survey_button: bool = Form(False),
                         media: UploadFile | None = File(None), admin: Admin = Depends(superadmin),
                         session: AsyncSession = Depends(get_session, scope="function")):
    """Send the message only to the admins' own Telegram (the ids in the settings), to see it before everyone."""
    t = _t(request)
    ids = [admin.telegram_id] if admin.telegram_id else (await settings_store.load(session, fresh=True))["admin_telegram_ids"]
    if not ids:
        return JSONResponse({"ok": False, "error": t("bc_test_no_ids")})
    text = text.strip()[:3500]
    if not text and not (media and media.filename):
        return JSONResponse({"ok": False, "error": t("bc_err_text")})
    stored = None
    try:
        if media and media.filename:
            kind, stored = await save_media(media, f"test-{secrets.token_hex(4)}")
            files = {"kind": kind, "path": str(broadcast.BROADCAST_MEDIA / stored)}
        else:
            files = None
    except MediaError as e:
        return JSONResponse({"ok": False, "error": t(f"bc_err_{e.code}")})
    url = webapp_url() if survey_button else ""
    token = chatlog.origin.set("broadcast:test")
    bot = chatlog.new_bot()
    sent, errors = 0, []
    try:
        for chat_id in ids:
            try:
                await broadcast.deliver(bot, chat_id, text, kb.open_survey("uz", f"{url}/survey") if url else None, files)
                sent += 1
            except Exception as e:  # noqa: BLE001 - shown to the admin as it is
                errors.append(f"{chat_id}: {e}")
    finally:
        await bot.session.close()
        chatlog.origin.reset(token)
        if stored:
            (broadcast.BROADCAST_MEDIA / stored).unlink(missing_ok=True)
    if not sent:
        return JSONResponse({"ok": False, "error": t("bc_test_failed", error="; ".join(errors)[:300])})
    return JSONResponse({"ok": True, "message": t("bc_test_sent", n=sent)})


def audience_label(t, b: Broadcast, names: dict) -> str:
    """'Guruhlar: 23-01 IQT, 23-02 IQT · tugatmaganlar' for the history table."""
    filters = b.filters or {}
    values = filters.get("values") or ([b.audience_value] if b.audience_value else [])
    audience, survey = b.audience, filters.get("survey", "")
    if audience == "unfinished":
        audience, survey = "all", "unfinished"
    label = t(f"aud_{audience}")
    if audience != "all" and values:
        shown = [names.get(audience, {}).get(str(v), str(v)) for v in values]
        if audience == "course":
            shown = [t("course_n", n=v) for v in values]
        label += ": " + ", ".join(shown[:4]) + (f" +{len(shown) - 4}" if len(shown) > 4 else "")
    if survey:
        label += " · " + t(f"bc_survey_{survey}")
    return label


# ================================================================ Admins & my account

@router.get("/admins", response_class=HTMLResponse)
async def admins_page(request: Request, admin: Admin = Depends(superadmin), session: AsyncSession = Depends(get_session, scope="function")):
    cid, campaigns = await resolve_campaign(session, None)
    query = select(Admin).order_by(Admin.username)
    if not admin.is_programmer:  # programmer accounts are not shown to anyone else
        query = query.where(Admin.role != "programmer")
    rows = list((await session.execute(query)).scalars())
    return await render(request, "admin/admins.html", admin, (cid, campaigns), rows=rows)


async def _other_admin(session: AsyncSession, admin: Admin, aid: int) -> Admin:
    """The account to change. A programmer account is "not found" for everyone but programmers."""
    other = await session.get(Admin, aid)
    if other is None or (other.is_programmer and not admin.is_programmer):
        raise HTTPException(404)
    return other


async def telegram_username_error(session: AsyncSession, t, value: str, owner_id: int | None) -> tuple[str | None, str | None]:
    """(clean username or None, error text or None) for a "Telegram username" field."""
    if not value.strip():
        return None, None
    name = admin_link.clean_username(value)
    if name is None:
        return None, t("tg_err_username", value=value.strip())
    taken = await session.scalar(select(Admin.username).where(func.lower(Admin.telegram_username) == name,
                                                              Admin.id != (owner_id or 0)))
    if taken:
        return None, t("tg_err_taken", value=name)
    return name, None


@router.post("/admins/new")
async def admin_create(request: Request, username: str = Form(...), password: str = Form(...),
                       role: str = Form("viewer"), show_identity: bool = Form(False), telegram_username: str = Form(""),
                       admin: Admin = Depends(superadmin), session: AsyncSession = Depends(get_session, scope="function")):
    t = _t(request)
    username = username.strip()
    tg_name, tg_error = await telegram_username_error(session, t, telegram_username, None)
    if not username or len(password) < 8 or role not in ("superadmin", "viewer"):
        flash(request, "bad", t("adm_err_input"))
    elif tg_error:
        flash(request, "bad", tg_error)
    elif await session.scalar(select(Admin.id).where(func.lower(Admin.username) == username.lower())):
        flash(request, "bad", t("adm_err_exists", name=username))
    else:
        session.add(Admin(username=username[:64], password_hash=hash_password(password), role=role,
                          show_identity=show_identity, telegram_username=tg_name))
        flash(request, "good", t("adm_created", name=username))
    return back("/admin/admins")


@router.post("/admins/{aid}/edit")
async def admin_edit(request: Request, aid: int, role: str = Form(""), is_active: bool = Form(False),
                     show_identity: bool = Form(False), password: str = Form(""), telegram_username: str = Form(""),
                     tg_unlink: bool = Form(False), admin: Admin = Depends(superadmin),
                     session: AsyncSession = Depends(get_session, scope="function")):
    t = _t(request)
    other = await _other_admin(session, admin, aid)
    tg_name, tg_error = await telegram_username_error(session, t, telegram_username, other.id)
    if tg_error:
        flash(request, "bad", tg_error)
        return back("/admin/admins")
    if tg_unlink:
        admin_link.unlink(other)
    elif other.telegram_id is None:  # once linked, the bot knows the account by its Telegram ID
        other.telegram_username = tg_name
    role = other.role if other.is_programmer or role not in ("superadmin", "viewer") else role
    if other.id == admin.id and (role != admin.role or not is_active):
        flash(request, "bad", t("adm_err_self"))
        return back("/admin/admins")
    if password and len(password) < 8:
        flash(request, "bad", t("adm_err_input"))
        return back("/admin/admins")
    other.role, other.is_active, other.show_identity = role, is_active, show_identity
    if password:
        other.password_hash = hash_password(password)
    flash(request, "good", t("saved"))
    return back("/admin/admins")


@router.post("/admins/{aid}/delete")
async def admin_delete(request: Request, aid: int, admin: Admin = Depends(superadmin),
                       session: AsyncSession = Depends(get_session, scope="function")):
    t = _t(request)
    other = await _other_admin(session, admin, aid)
    if other.id == admin.id:
        flash(request, "bad", t("adm_err_self"))
    else:
        await session.execute(delete(Admin).where(Admin.id == aid))
        flash(request, "good", t("adm_deleted"))
    return back("/admin/admins")


@router.get("/account", response_class=HTMLResponse)
async def account(request: Request, admin: Admin = Depends(current_admin), session: AsyncSession = Depends(get_session, scope="function")):
    cid, campaigns = await resolve_campaign(session, None)
    bot = await settings_store.get(session, "bot_username")
    token_ok = bool(admin.tg_link_token and admin.tg_link_until and admin.tg_link_until > datetime.now(timezone.utc))
    link = f"https://t.me/{bot}?start={admin_link.TOKEN_PREFIX}{admin.tg_link_token}" if token_ok and bot else ""
    return await render(request, "admin/account.html", admin, (cid, campaigns), bot_username=bot,
                        tg_link=link, tg_token=f"{admin_link.TOKEN_PREFIX}{admin.tg_link_token}" if token_ok else "",
                        tg_until=local_time_hm(admin.tg_link_until) if token_ok else "")


def local_time_hm(dt: datetime) -> str:
    return dt.astimezone(TASHKENT).strftime("%H:%M")


@router.post("/account/telegram/link")
async def telegram_link(request: Request, admin: Admin = Depends(current_admin)):
    """A one-time link (15 minutes) that opens the bot and links this account to whoever taps it."""
    admin_link.new_token(admin)
    return back("/admin/account#telegram")


@router.post("/account/telegram/username")
async def telegram_username(request: Request, telegram_username: str = Form(""), admin: Admin = Depends(current_admin),
                            session: AsyncSession = Depends(get_session, scope="function")):
    t = _t(request)
    name, error = await telegram_username_error(session, t, telegram_username, admin.id)
    if error:
        flash(request, "bad", error)
    else:
        admin.telegram_username = name
        flash(request, "good", t("tg_username_saved", value=name) if name else t("saved"))
    return back("/admin/account#telegram")


@router.post("/account/telegram/unlink")
async def telegram_unlink(request: Request, admin: Admin = Depends(current_admin)):
    admin_link.unlink(admin)
    flash(request, "good", _t(request)("tg_unlinked"))
    return back("/admin/account#telegram")


@router.post("/account/display")
async def save_display(request: Request, admin: Admin = Depends(current_admin)):
    """Ko‘rinish (text size, theme, ...): saved with the account; the page applies it at once by itself."""
    form = await request.form()
    admin.prefs = {**(admin.prefs or {}), **display.clean({key: form.get(key, False) for key in display.DEFAULTS})}
    return JSONResponse({"ok": True, "prefs": admin.prefs})


@router.post("/account/password")
async def change_password(request: Request, current: str = Form(...), new: str = Form(...), repeat: str = Form(...),
                          admin: Admin = Depends(current_admin)):
    t = _t(request)
    if not verify_password(current, admin.password_hash):
        flash(request, "bad", t("acc_err_current"))
    elif len(new) < 8 or new != repeat:
        flash(request, "bad", t("acc_err_new"))
    else:
        admin.password_hash = hash_password(new)
        flash(request, "good", t("acc_changed"))
    return back("/admin/account")

