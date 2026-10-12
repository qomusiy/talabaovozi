"""Tahrirlash: correct the data by hand - teachers (kafedra, name, position), kafedras and groups (with how many
students each has); programmer accounts also ratings.

The timetable and the Excel uploads stay the main source; this page is for fixing mistakes. What the next timetable
sync would overwrite is not editable here (a timetable group's name). Teachers who already have evaluations can't
be deleted, only switched off, so survey results stay complete.
"""
import math
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.faculty import display_code, group_key
from app.models import RATING_CRITERIA, Admin, BotUser, Department, Feedback, Group, SurveyCampaign, Teacher
from app.services import departments as kafedras
from app.services.teaching import guess_departments
from app.web.admin import analytics as an
from app.web.admin.i18n import translator
from app.web.admin.views import department_groups, flash, get_lang, render, resolve_campaign
from app.web.deps import get_session, programmer, superadmin

router = APIRouter(prefix="/admin/records")
TABS = ("teachers", "departments", "groups", "feedback")  # feedback: programmer accounts only
GROUP_LANGS = ("uz", "ru", "en")
PER_PAGE = 50


def _t(request: Request):
    return translator(get_lang(request))


def back(next_: str, tab: str) -> RedirectResponse:
    return RedirectResponse(next_ if next_.startswith("/admin/records") else f"/admin/records?tab={tab}", status_code=303)


def _id(raw: str) -> int | None:
    return int(raw) if raw.strip().isdigit() else None


def _404():
    raise HTTPException(404)


async def _feedback_counts(session: AsyncSession, column) -> dict[int, int]:
    return dict((await session.execute(select(column, func.count(Feedback.id)).group_by(column))).all())


# ---------------------------------------------------------------- Page

@router.get("", response_class=HTMLResponse)
async def records(request: Request, tab: str = "teachers", q: str = "", group: str = "", page: str = "1",
                  edit: str = "", campaign: str = "", admin: Admin = Depends(superadmin),
                  session: AsyncSession = Depends(get_session, scope="function")):
    tab = tab if tab in TABS and (tab != "feedback" or admin.is_programmer) else "teachers"
    t = _t(request)
    cid, campaigns = await resolve_campaign(session, None)
    depts = await an.departments(session)
    counts = {
        "teachers": await session.scalar(select(func.count(Teacher.id))),
        "departments": len(depts),
        "groups": await session.scalar(select(func.count(Group.id))),
    }
    # This page with its filters (and without ?edit=), to come back to after saving.
    params = {"tab": tab, **({"q": q} if q else {}), **({"group": group} if group else {}),
              **({"campaign": campaign} if campaign and tab == "feedback" else {}),
              **({"page": page} if page not in ("", "1") else {})}
    ctx: dict = {"tab": tab, "counts": counts, "here": "/admin/records?" + urlencode(params), "q": q,
                 "open_id": _id(edit), "dept_groups": department_groups(depts, t), "langs_group": GROUP_LANGS}

    if admin.is_programmer:
        counts["feedback"] = await session.scalar(select(func.count(Feedback.id)))
    if tab == "feedback":
        ctx |= await _feedback_rows(session, q, _id(campaign), max(1, _id(page) or 1))
        ctx["campaigns_all"] = campaigns
        if not admin.sees_identity:  # hidden from this panel (Ko‘rinish): found, but shown without who rated
            ctx["rows"] = [{**r, "who": None, "user_id": None, "label": r["teacher"]} for r in ctx["rows"]]
            ctx["names_hidden"] = True
    elif tab == "teachers":
        n = await _feedback_counts(session, Feedback.teacher_id)
        rows = (await session.execute(select(Teacher, Department.name).outerjoin(Department)
                                      .order_by(Teacher.is_active.desc(), Teacher.full_name))).all()
        ctx["rows"] = [{"id": x.id, "full_name": x.full_name, "short_name": x.short_name, "department": dept,
                        "department_id": x.department_id or "", "position": x.position or "",
                        "room": x.room_number or "", "active": x.is_active, "edupage": bool(x.edupage_id),
                        "n": n.get(x.id, 0)} for x, dept in rows]
    elif tab == "departments":
        n = await kafedras.teacher_counts(session)
        ctx["rows"] = [{"id": d.id, "name": d.name, "faculty": d.faculty or "", "n": n.get(d.id, 0)} for d in depts]
        ctx["faculties"] = sorted({*kafedras.KAFEDRAS.values(), *(d.faculty for d in depts if d.faculty)})
        ctx["missing"] = await session.scalar(select(func.count(Teacher.id)).where(
            Teacher.is_active, Teacher.department_id.is_(None)))
    else:
        users = dict((await session.execute(select(BotUser.group_id, func.count()).where(BotUser.group_id.is_not(None))
                                            .group_by(BotUser.group_id))).all())
        n = await _feedback_counts(session, Feedback.group_id)
        groups = (await session.execute(select(Group).order_by(Group.name))).scalars()
        ctx["rows"] = [{"id": g.id, "name": g.name, "number": g.number or "", "code": g.code, "course": g.course or "",
                        "language": g.language or "", "edupage": bool(g.edupage_id), "students": g.student_count or "",
                        "users": users.get(g.id, 0), "n": n.get(g.id, 0)} for g in groups]
    return await render(request, "admin/records.html", admin, (cid, campaigns), **ctx)


async def _feedback_rows(session: AsyncSession, q: str, campaign_id: int | None, page_n: int) -> dict:
    """Ratings for the programmer's "Baholar" tab: find an account's ratings (name, @username, Telegram id) or a
    teacher's."""
    query = (select(Feedback, an.WHO, Teacher.full_name, Group.name, SurveyCampaign.title)
             .join(BotUser, BotUser.id == Feedback.user_id).join(Teacher, Teacher.id == Feedback.teacher_id)
             .join(SurveyCampaign, SurveyCampaign.id == Feedback.campaign_id)
             .outerjoin(Group, Group.id == Feedback.group_id))
    if q.strip():
        query = query.where(or_(an.who_search(q), Teacher.full_name.ilike(f"%{q.strip()}%")))
    if campaign_id:
        query = query.where(Feedback.campaign_id == campaign_id)
    total = await session.scalar(select(func.count()).select_from(query.subquery()))
    found = (await session.execute(query.order_by(Feedback.created_at.desc()).offset((page_n - 1) * PER_PAGE)
                                   .limit(PER_PAGE))).all()
    rows = [{"id": f.id, "label": f"{who or f.user_id} → {teacher}", "who": who or str(f.user_id), "user_id": f.user_id,
             "teacher": teacher, "group": group, "survey": survey, "date": f.created_at, "comment": f.comment or "",
             **{k: getattr(f, k) for k in RATING_CRITERIA},
             "overall": round(sum(getattr(f, k) for k in RATING_CRITERIA) / 3, 2)}
            for f, who, teacher, group, survey in found]
    return {"rows": rows, "total": total, "page": page_n, "pages": max(1, math.ceil(total / PER_PAGE)),
            "campaign_id": campaign_id}


@router.post("/feedback/{fid}")
async def feedback_edit(request: Request, fid: int, teaching: str = Form(""), fairness: str = Form(""),
                        professionalism: str = Form(""), comment: str = Form(""), next: str = Form(""),
                        admin: Admin = Depends(programmer), session: AsyncSession = Depends(get_session, scope="function")):
    """A rating to correct (asked for, or abuse): the programmer can (the change is in the activity log)."""
    t = _t(request)
    fb = await session.get(Feedback, fid) or _404()
    scores = {k: _id(v) for k, v in (("teaching", teaching), ("fairness", fairness), ("professionalism", professionalism))}
    if any(v is None or not 1 <= v <= 10 for v in scores.values()):
        flash(request, "bad", t("rd_err_scores"))
        return back(next, "feedback")
    for k, v in scores.items():
        setattr(fb, k, v)
    fb.comment = comment.strip()[:2000] or None
    flash(request, "good", t("rd_feedback_saved"))
    return back(next, "feedback")


@router.post("/feedback/{fid}/delete")
async def feedback_delete(request: Request, fid: int, next: str = Form(""), admin: Admin = Depends(programmer),
                          session: AsyncSession = Depends(get_session, scope="function")):
    fb = await session.get(Feedback, fid) or _404()
    await session.delete(fb)
    flash(request, "good", _t(request)("rd_feedback_deleted"))
    return back(next, "feedback")


# ---------------------------------------------------------------- Teachers

async def _save_teacher(request, session, teacher: Teacher, full_name: str, department: str, position: str,
                        room: str, active: bool) -> bool:
    t = _t(request)
    name = " ".join(full_name.split())[:255]
    dept_id = _id(department)
    if not name:
        flash(request, "bad", t("rd_err_name"))
        return False
    if dept_id and await session.get(Department, dept_id) is None:
        dept_id = None
    teacher.full_name, teacher.department_id, teacher.is_active = name, dept_id, active
    teacher.position, teacher.room_number = position.strip()[:128] or None, room.strip()[:32] or None
    return True


@router.post("/teachers/new")
async def teacher_new(request: Request, full_name: str = Form(""), department: str = Form(""), position: str = Form(""),
                      room: str = Form(""), next: str = Form(""), admin: Admin = Depends(superadmin),
                      session: AsyncSession = Depends(get_session, scope="function")):
    teacher = Teacher(full_name="")
    if await _save_teacher(request, session, teacher, full_name, department, position, room, True):
        session.add(teacher)
        flash(request, "good", _t(request)("rd_created", name=teacher.full_name))
    return back(next, "teachers")


@router.post("/teachers/{tid}")
async def teacher_edit(request: Request, tid: int, full_name: str = Form(""), department: str = Form(""),
                       position: str = Form(""), room: str = Form(""), active: bool = Form(False), next: str = Form(""),
                       admin: Admin = Depends(superadmin), session: AsyncSession = Depends(get_session, scope="function")):
    teacher = await session.get(Teacher, tid) or _404()
    if await _save_teacher(request, session, teacher, full_name, department, position, room, active):
        flash(request, "good", _t(request)("rd_saved", name=teacher.full_name))
    return back(next, "teachers")


@router.post("/teachers/{tid}/delete")
async def teacher_delete(request: Request, tid: int, next: str = Form(""), admin: Admin = Depends(superadmin),
                         session: AsyncSession = Depends(get_session, scope="function")):
    t = _t(request)
    teacher = await session.get(Teacher, tid) or _404()
    if n := await session.scalar(select(func.count(Feedback.id)).where(Feedback.teacher_id == tid)):
        flash(request, "bad", t("rd_err_teacher_feedback", n=n))
    else:
        await session.execute(delete(Teacher).where(Teacher.id == tid))
        flash(request, "good", t("rd_deleted", name=teacher.full_name))
    return back(next, "teachers")


# ---------------------------------------------------------------- Kafedras

async def _name_taken(session, model, name: str, skip_id: int | None) -> bool:
    return bool(await session.scalar(select(model.id).where(func.lower(model.name) == name.lower(),
                                                            model.id != (skip_id or 0))))


# "/new" is registered first (decorators apply bottom-up), so it isn't read as an id.
@router.post("/departments/{did}")
@router.post("/departments/new")
async def department_save(request: Request, did: int | None = None, name: str = Form(""), faculty: str = Form(""),
                          next: str = Form(""), admin: Admin = Depends(superadmin),
                          session: AsyncSession = Depends(get_session, scope="function")):
    t = _t(request)
    name = " ".join(name.split())[:255]
    if not name:
        flash(request, "bad", t("rd_err_name"))
    elif await _name_taken(session, Department, name, did):
        flash(request, "bad", t("rd_err_exists", name=name))
    else:
        dept = (await session.get(Department, did) or _404()) if did else Department()
        dept.name, dept.faculty = name, " ".join(faculty.split())[:128] or None
        session.add(dept)
        flash(request, "good", t("rd_saved" if did else "rd_created", name=name))
    return back(next, "departments")


@router.post("/departments/{did}/delete")
async def department_delete(request: Request, did: int, next: str = Form(""), admin: Admin = Depends(superadmin),
                            session: AsyncSession = Depends(get_session, scope="function")):
    dept = await session.get(Department, did) or _404()
    await session.execute(delete(Department).where(Department.id == did))  # its teachers are left without a kafedra
    flash(request, "good", _t(request)("rd_deleted", name=dept.name))
    return back(next, "departments")


@router.post("/departments-guess")
async def departments_guess(request: Request, next: str = Form(""), admin: Admin = Depends(superadmin),
                            session: AsyncSession = Depends(get_session, scope="function")):
    t = _t(request)
    n = await guess_departments(session)
    flash(request, "bad" if n is None else "good", t("tt_empty") if n is None else t("rd_guessed", n=n))
    return back(next, "departments")


# ---------------------------------------------------------------- Groups

@router.post("/groups/{gid}")
@router.post("/groups/new")
async def group_save(request: Request, gid: int | None = None, name: str = Form(""), number: str = Form(""),
                     course: str = Form(""), language: str = Form(""), students: str = Form(""), next: str = Form(""),
                     admin: Admin = Depends(superadmin), session: AsyncSession = Depends(get_session, scope="function")):
    t = _t(request)
    group = (await session.get(Group, gid) or _404()) if gid else Group()
    size = _id(students)
    if students.strip() and (size is None or size > 1000):
        flash(request, "bad", t("rd_err_students"))
        return back(next, "groups")
    number = " ".join(number.split())[:16] or None
    if number and await session.scalar(select(Group.name).where(func.lower(Group.number) == number.lower(),
                                                                Group.id != (gid or 0))):
        flash(request, "bad", t("rd_err_number", number=number))
        return back(next, "groups")
    if group.edupage_id:  # name, course and language come from the timetable: the number and size change here
        group.student_count, group.number = size or None, number
        flash(request, "good", t("rd_saved", name=group.name))
        return back(next, "groups")
    name = " ".join(name.split())[:64]
    if not name:
        flash(request, "bad", t("rd_err_name"))
        return back(next, "groups")
    key = group_key(name)
    clash = await session.scalar(select(Group.id).where(
        or_(func.lower(Group.name) == name.lower(), Group.key == key) if key else func.lower(Group.name) == name.lower(),
        Group.id != (gid or 0)))
    if clash:
        flash(request, "bad", t("rd_err_exists", name=name))
        return back(next, "groups")
    c = _id(course)
    group.name, group.key, group.code = name, key, display_code(name)
    group.course = c if c and 1 <= c <= 6 else None
    group.language = language if language in GROUP_LANGS else None
    group.student_count, group.number = size or None, number
    session.add(group)
    flash(request, "good", t("rd_saved" if gid else "rd_created", name=name))
    return back(next, "groups")


@router.post("/groups/{gid}/delete")
async def group_delete(request: Request, gid: int, next: str = Form(""), admin: Admin = Depends(superadmin),
                       session: AsyncSession = Depends(get_session, scope="function")):
    t = _t(request)
    group = await session.get(Group, gid) or _404()
    if n := await session.scalar(select(func.count(Feedback.id)).where(Feedback.group_id == gid)):
        flash(request, "bad", t("rd_err_group_feedback", n=n))
    else:
        await session.execute(delete(Group).where(Group.id == gid))
        flash(request, "good", t("rd_deleted", name=group.name))
    return back(next, "groups")
