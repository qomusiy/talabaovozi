"""The admins' Mini App (opened from the bot's admin menu: 📊 Statistika): the survey's numbers on a phone.

Telegram signs who opened it (initData), so no password is asked - only a dashboard account linked to that
Telegram account gets the data (app.services.admin_link). It lives outside /admin, so it also works while the
dashboard itself is closed to the internet; it only reads, never changes anything.
"""
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import settings_store
from app.config import get_settings
from app.models import Admin
from app.services import admin_stats
from app.web.admin import analytics as an
from app.web.admin.i18n import translator
from app.web.deps import get_session
from app.web.telegram_auth import verify_init_data
from app.web.templating import templates

router = APIRouter()

TEXTS = {
    "uz": {"title": "Statistika", "open": "Ochiq", "closed": "Yopiq", "closes": "{date} gacha", "left": "{n} kun qoldi",
           "left_today": "bugun yopiladi", "participation": "Ishtirok", "of_students": "{p} / {n} talaba",
           "ratings": "Baholar", "today": "bugun +{n}", "average": "O‘rtacha ball", "completed": "Hammasini baholagan",
           "comments": "Izohlar", "criteria": "Mezonlar", "teaching": "O‘qitish", "fairness": "Adolat",
           "professionalism": "Kasbiylik", "by_course": "Kurslar bo‘yicha ishtirok", "course": "{n}-kurs",
           "low": "Eng past ishtirok", "daily": "Kunlik baholar", "latest": "So‘nggi izohlar",
           "student": "Talaba", "links": "Manzillar", "survey_link": "So‘rovnoma", "admin_link": "Admin sayt",
           "admin_closed": "Internetda yopiq — faqat server kompyuterida", "copy": "Nusxa", "copied": "Nusxa olindi",
           "open_link": "Ochish", "refresh": "Yangilash", "no_survey": "Hali so‘rovnoma o‘tkazilmagan",
           "in_bot": "Botdagi talabalar", "site": "Sayt", "site_ok": "ishlayapti", "site_down": "ishlamayapti",
           "site_starting": "ishga tushmoqda", "site_unknown": "noma’lum", "site_none": "manzil yo‘q",
           "not_admin": "Bu bo‘lim faqat Talaba Ovozi adminlari uchun. Admin saytdagi «Mening hisobim › Telegram» "
                        "orqali hisobingizni ulang.",
           "open_in_telegram": "Bu sahifa Telegram bot ichida ochiladi.", "error": "Ma’lumotni olib bo‘lmadi."},
    "en": {"title": "Statistics", "open": "Open", "closed": "Closed", "closes": "until {date}", "left": "{n} days left",
           "left_today": "closes today", "participation": "Participation", "of_students": "{p} / {n} students",
           "ratings": "Ratings", "today": "today +{n}", "average": "Average score", "completed": "Rated everyone",
           "comments": "Comments", "criteria": "Criteria", "teaching": "Teaching", "fairness": "Fairness",
           "professionalism": "Professionalism", "by_course": "Participation by year", "course": "Year {n}",
           "low": "Lowest participation", "daily": "Ratings per day", "latest": "Latest comments",
           "student": "Student", "links": "Addresses", "survey_link": "Survey", "admin_link": "Dashboard",
           "admin_closed": "Closed to the internet — only on the server computer", "copy": "Copy", "copied": "Copied",
           "open_link": "Open", "refresh": "Refresh", "no_survey": "No survey has been run yet",
           "in_bot": "Students in the bot", "site": "Site", "site_ok": "working", "site_down": "down",
           "site_starting": "starting", "site_unknown": "unknown", "site_none": "no address",
           "not_admin": "This is for Talaba Ovozi admins only. Link your account in the dashboard: «My account › Telegram».",
           "open_in_telegram": "This page opens inside the Telegram bot.", "error": "Couldn’t load the data."},
    "ru": {"title": "Статистика", "open": "Открыт", "closed": "Закрыт", "closes": "до {date}", "left": "осталось дней: {n}",
           "left_today": "закрывается сегодня", "participation": "Участие", "of_students": "{p} / {n} студентов",
           "ratings": "Оценки", "today": "сегодня +{n}", "average": "Средний балл", "completed": "Оценили всех",
           "comments": "Комментарии", "criteria": "Критерии", "teaching": "Преподавание", "fairness": "Справедливость",
           "professionalism": "Профессионализм", "by_course": "Участие по курсам", "course": "{n} курс",
           "low": "Самое низкое участие", "daily": "Оценки по дням", "latest": "Последние комментарии",
           "student": "Студент", "links": "Адреса", "survey_link": "Опрос", "admin_link": "Админ-сайт",
           "admin_closed": "Закрыт для интернета — только на компьютере-сервере", "copy": "Копировать",
           "copied": "Скопировано", "open_link": "Открыть", "refresh": "Обновить", "no_survey": "Опросов ещё не было",
           "in_bot": "Студентов в боте", "site": "Сайт", "site_ok": "работает", "site_down": "не работает",
           "site_starting": "запускается", "site_unknown": "неизвестно", "site_none": "нет адреса",
           "not_admin": "Раздел только для админов Talaba Ovozi. Привяжите аккаунт на админ-сайте: «Мой аккаунт › Telegram».",
           "open_in_telegram": "Эта страница открывается внутри Telegram-бота.", "error": "Не удалось загрузить данные."},
}


def texts(lang: str | None) -> dict:
    return TEXTS.get(lang or "uz") or TEXTS["uz"]


async def telegram_admin(session: AsyncSession = Depends(get_session, scope="function"),
                         x_telegram_init_data: str | None = Header(default=None)) -> tuple[Admin, str]:
    """(the linked dashboard account of whoever opened the Mini App, their Telegram language)."""
    user = verify_init_data(x_telegram_init_data, get_settings().bot_token) if x_telegram_init_data else None
    if user is None:
        raise HTTPException(401, "open_in_telegram")
    admin = await session.scalar(select(Admin).where(Admin.telegram_id == int(user["id"]), Admin.is_active))
    if admin is None:
        raise HTTPException(403, "not_admin")
    return admin, user.get("language_code") or ""


@router.get("/miniapp/admin", response_class=HTMLResponse)
async def page(request: Request):
    return templates.TemplateResponse(request, "miniapp_admin.html", {"texts": TEXTS})


@router.get("/api/miniapp/admin")
async def data(who: tuple = Depends(telegram_admin), session: AsyncSession = Depends(get_session, scope="function")):
    admin, tg_lang = who
    lang = tg_lang if tg_lang in TEXTS else "uz"
    s = await admin_stats.snapshot(session, detail=True)
    comments = []
    if s["campaign"]:
        for c in await an.latest_comments(session, s["campaign"]["id"], limit=6):
            comments.append({"teacher": c["teacher"], "group": c["group"], "date": c["date"], "overall": c["overall"],
                             "comment": c["comment"], "student": c["student"] if admin.sees_identity else None})
    online = not get_settings().admin_local_only or await settings_store.get(session, "admin_online")
    url = s["site"]["url"]
    return {"lang": lang, "texts": texts(lang),
            "admin": {"name": admin.telegram_name or admin.username, "role": translator(lang)(f"role_{admin.role}")},
            "stats": s, "comments": comments,
            "links": {"survey": f"{url}/survey" if url else "", "admin": f"{url}/admin" if url and online else "",
                      "local": f"http://127.0.0.1:{get_settings().web_port}/admin"}}
