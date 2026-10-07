"""Student survey: the Telegram Mini App page and its JSON API."""

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app import settings_store
from app.models import Student
from app.services import students as svc
from app.web.templating import templates
from app.web.deps import current_student, get_session
from app.web.i18n import SURVEY_TEXTS, survey_texts

router = APIRouter()
COMMENT_MIN = 10  # characters, when the dashboard makes the comment required (survey.js uses the same number)


@router.get("/survey", response_class=HTMLResponse)
async def survey_page(request: Request):
    return templates.TemplateResponse(request, "survey.html", {"fallback_texts": SURVEY_TEXTS})


@router.get("/api/survey")
async def survey_data(student: Student = Depends(current_student), session: AsyncSession = Depends(get_session, scope="function")):
    campaign = await svc.active_campaign(session)
    settings = await settings_store.load(session)
    cards = await svc.teachers_of(session, student)
    given = await svc.feedback_by_teacher(session, student, campaign) if campaign else {}
    teachers = []
    for card in cards:
        subjects: dict[str, list[str]] = {}
        for subject, kind in card.lessons:
            subjects.setdefault(subject, []).append(kind)
        fb = given.get(card.teacher.id)
        teachers.append({
            "id": card.teacher.id,
            "name": card.teacher.full_name,
            "department": card.teacher.department.name if card.teacher.department else None,
            "room": card.teacher.room_number,
            "subjects": [{"name": n, "types": k} for n, k in subjects.items()],
            "feedback": {
                "teaching": fb.teaching,
                "fairness": fb.fairness,
                "professionalism": fb.professionalism,
                "comment": fb.comment or "",
            } if fb else None,
        })
    return {
        "lang": student.language,
        "texts": survey_texts(student.language),
        "student": {"name": student.full_name, "group": student.group.name if student.group else None},
        "campaign": {"title": campaign.title, "closes_at": campaign.closes_at.isoformat()} if campaign else None,
        "teachers": teachers,
        # Set in the dashboard (Bot page)
        "settings": {"comments": settings["survey_comments"], "edit": settings["survey_edit"],
                     "comment_required": settings["survey_comments"] and settings["survey_comment_required"],
                     "notice": settings["survey_notice"]},
    }


class FeedbackIn(BaseModel):
    teaching: int = Field(ge=1, le=10)
    fairness: int = Field(ge=1, le=10)
    professionalism: int = Field(ge=1, le=10)
    comment: str | None = Field(default=None, max_length=2000)


@router.post("/api/survey/teachers/{teacher_id}")
async def submit_feedback(teacher_id: int, body: FeedbackIn, student: Student = Depends(current_student),
                          session: AsyncSession = Depends(get_session, scope="function")):
    ratings = body.model_dump(exclude={"comment"})
    settings = await settings_store.load(session)
    if (settings["survey_comments"] and settings["survey_comment_required"]
            and len((body.comment or "").strip()) < COMMENT_MIN):
        raise HTTPException(400, "comment_required")
    try:
        await svc.save_feedback(session, student, teacher_id, ratings, body.comment)
    except svc.SurveyError as e:
        raise HTTPException(400, str(e)) from e
    return {"ok": True}
