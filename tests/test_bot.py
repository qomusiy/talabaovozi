import re
from datetime import date, datetime, timedelta, timezone

import pytest
from aiogram import Bot, Dispatcher
from aiogram.client.session.base import BaseSession
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.methods import TelegramMethod
from aiogram.types import CallbackQuery, Chat, InlineKeyboardMarkup, Message, PhotoSize, Update, User

from app.bot import chatlog
from app.bot.handlers import admin, auth, menu
from app.bot.reactions import ReactionMiddleware
from app.bot.i18n import LANGUAGE_NAMES, TEXTS, t
from app.bot.middleware import ContextMiddleware
from app.models import Department, Feedback, Group, Semester, Student, Subject, SurveyCampaign, Teacher, TeachingAssignment
from app.security import hash_passport
from app.services import students as svc


def test_every_text_has_all_languages_and_same_placeholders():
    for key, entry in TEXTS.items():
        assert set(entry) == set(LANGUAGE_NAMES), key
        placeholders = {lang: set(re.findall(r"{(\w+)}", s)) for lang, s in entry.items()}
        assert len({frozenset(p) for p in placeholders.values()}) == 1, (key, placeholders)


@pytest.fixture
async def world(session):
    group = Group(name="25-16 IQT", course=2)
    other_group = Group(name="25-17 IQT", course=2)
    sem = Semester(name="2026-2027 Fall", starts_on=date(2026, 9, 1), ends_on=date(2027, 1, 20), is_current=True)
    dept = Department(name="Iqtisodiyot nazariyasi")
    t1 = Teacher(full_name="Qodirov Rustam", department=dept, room_number="2-14")
    t2 = Teacher(full_name="Saidova Madina")
    t3 = Teacher(full_name="Other Group Teacher")
    subj = Subject(name="Makroiqtisodiyot")
    student = Student(hemis_id="368211100001", full_name="Karimov Aziz", passport_hash=hash_passport("AS3480990"),
                      group=group)
    session.add_all([
        student, sem, t3,
        TeachingAssignment(semester=sem, teacher=t1, group=group, subject=subj, lesson_type="lecture"),
        TeachingAssignment(semester=sem, teacher=t1, group=group, subject=Subject(name="Mikro"), lesson_type="practice"),
        TeachingAssignment(semester=sem, teacher=t2, group=group, subject=subj, lesson_type="practice"),
        TeachingAssignment(semester=sem, teacher=t3, group=other_group, subject=subj, lesson_type="lecture"),
    ])
    await session.commit()
    return {"student": student, "t1": t1, "t2": t2, "sem": sem}


async def test_authenticate(session, world):
    assert await svc.authenticate(session, "368211100001", "as 3480990")
    assert await svc.authenticate(session, "368211100001", "AS3480991") is None
    assert await svc.authenticate(session, "000", "AS3480990") is None


async def test_one_telegram_account_per_student(session, world):
    st = world["student"]
    await svc.link_telegram(session, st, 111, "ru")
    await svc.link_telegram(session, st, 111, "ru")  # same account again is fine
    with pytest.raises(svc.AlreadyLinkedError):
        await svc.link_telegram(session, st, 222, "uz")


async def test_teachers_of_only_own_group_grouped_by_teacher(session, world):
    cards = await svc.teachers_of(session, world["student"])
    assert [c.teacher.full_name for c in cards] == ["Qodirov Rustam", "Saidova Madina"]
    assert len(cards[0].lessons) == 2


# ---------- End-to-end: feed fake Telegram updates through the real dispatcher ----------

class FakeSession(BaseSession):
    """Records every API call instead of sending it to Telegram."""

    def __init__(self):
        super().__init__()
        self.calls: list[TelegramMethod] = []

    async def make_request(self, bot, method, timeout=None):
        self.calls.append(method)
        if method.__returning__ is Message or "Message" in str(method.__returning__):
            chat_id = getattr(method, "chat_id", None)
            photo = [PhotoSize(file_id="PHOTO", file_unique_id="u", width=1, height=1)] if hasattr(method, "photo") else None
            return Message(message_id=len(self.calls) + 100, date=datetime.now(),
                           chat=Chat(id=chat_id if isinstance(chat_id, int) else 1, type="private"),
                           text=getattr(method, "text", None) if photo is None else None,
                           caption=getattr(method, "caption", None), photo=photo,
                           reply_markup=markup if isinstance(markup := getattr(method, "reply_markup", None),
                                                             InlineKeyboardMarkup) else None)
        return True

    async def close(self):
        pass

    async def stream_content(self, *a, **kw):
        yield b""

    def texts(self) -> list[str]:
        """Text (or photo caption) of every message the bot sent/edited (other API calls are skipped)."""
        return [_text(c) for c in self.calls if _text(c)]


def _text(call) -> str | None:
    return getattr(call, "text", None) or getattr(call, "caption", None)


class Chatter:
    def __init__(self):
        self.fake = FakeSession()
        self.bot = Bot("42:TEST", session=self.fake)
        self.dp = Dispatcher(storage=MemoryStorage())
        self.dp.update.outer_middleware(ContextMiddleware())
        self.dp.update.outer_middleware(chatlog.IncomingLog())
        self.dp.message.middleware(ReactionMiddleware())
        self.bot.session.middleware(chatlog.OutgoingLog())
        self.dp.include_routers(admin.router, auth.router, menu.router)
        self.user = User(id=777, is_bot=False, first_name="Aziz")
        self.n = 0

    async def send(self, text: str) -> list[str]:
        self.n += 1
        start = len(self.fake.texts())
        msg = Message(message_id=self.n, date=datetime.now(), chat=Chat(id=777, type="private"),
                      from_user=self.user, text=text,
                      entities=[{"type": "bot_command", "offset": 0, "length": len(text.split()[0])}]
                      if text.startswith("/") else None)
        await self.dp.feed_update(self.bot, Update(update_id=self.n, message=msg))
        return self.fake.texts()[start:]

    def last_markup(self):
        return next((c.reply_markup for c in reversed(self.fake.calls) if _text(c)), None)

    async def press(self, data: str, photo: bool = False) -> list[str]:
        """Tap a button under a card (photo=True: a card with the menu picture, as the bot sends them)."""
        self.n += 1
        start = len(self.fake.texts())
        msg = Message(message_id=1, date=datetime.now(), chat=Chat(id=777, type="private"),
                      **({"caption": "x", "photo": [PhotoSize(file_id="P", file_unique_id="u", width=1, height=1)]}
                         if photo else {"text": "x"}))
        cb = CallbackQuery(id=str(self.n), from_user=self.user, chat_instance="c", data=data, message=msg)
        await self.dp.feed_update(self.bot, Update(update_id=self.n, callback_query=cb))
        return self.fake.texts()[start:]


@pytest.fixture
async def chat(world, monkeypatch, tmp_path):
    import app.runtime
    monkeypatch.setattr(app.runtime, "WEBAPP_URL_FILE", tmp_path / "webapp_url")  # no tunnel unless a test adds one
    import app.bot.menu_button
    monkeypatch.setattr(app.bot.menu_button, "_current", None)
    # Handlers open their own sessions via app.db; they point at the same test database.
    for r in (admin.router, auth.router, menu.router):
        r._parent_router = None  # routers can only be attached once; reset between tests
    return Chatter()


async def test_full_login_flow_and_menu(chat, session, world):
    out = await chat.send("/start")
    assert t("uz", "welcome") in out

    await chat.press("lang:ru")
    await chat.press("login")
    assert (await chat.send("abc")) == [t("ru", "bad_hemis")]
    assert (await chat.send("368211100001")) == [t("ru", "ask_passport")]

    out = await chat.send("AS0000000")  # wrong passport
    assert any("❌" in o for o in out)
    assert any(isinstance(c, type(c)) and type(c).__name__ == "DeleteMessage" for c in chat.fake.calls)

    await chat.press("login")
    await chat.send("368211100001")
    out = await chat.send("as3480990")
    assert any("Karimov Aziz" in o and "25-16 IQT" in o for o in out)

    await session.refresh(world["student"])
    assert world["student"].telegram_id == 777 and world["student"].language == "ru"

    # Logging in shows the home card (no survey yet) - with inline buttons, and no reply keyboard.
    assert any(t("ru", "home_closed") in o for o in out)
    assert all(type(c.reply_markup).__name__ != "ReplyKeyboardMarkup" for c in chat.fake.calls if hasattr(c, "reply_markup"))

    # "My teachers" opens in the same message: only this group's teachers.
    out = await chat.press("teachers:1")
    assert "Qodirov Rustam" in out[0] and "Saidova Madina" in out[0] and "Other Group" not in out[0]
    assert "лекция" in out[0] and "2-14" in out[0]
    assert chat.last_markup().inline_keyboard[-1][0].callback_data == "home"   # ⬅️ Back

    # A button of the old always-open keyboard still works: it brings the home card and removes that keyboard.
    out = await chat.send(t("ru", "btn_survey"))
    assert any(t("ru", "home_closed") in o for o in out)
    assert any(type(c.reply_markup).__name__ == "ReplyKeyboardRemove" for c in chat.fake.calls if hasattr(c, "reply_markup"))

    # Open a campaign, rate one of two teachers -> 1/2 progress.
    now = datetime.now(timezone.utc)
    camp = SurveyCampaign(semester_id=world["sem"].id, title="Mid-term", opens_at=now - timedelta(days=1),
                          closes_at=now + timedelta(days=7))
    session.add(camp)
    await session.flush()
    session.add(Feedback(campaign_id=camp.id, student_id=world["student"].id, teacher_id=world["t1"].id,
                         teaching=9, fairness=8, professionalism=10))
    await session.commit()
    out = await chat.press("home")
    assert "1 / 2" in out[0] and "50%" in out[0] and "Mid-term" in out[0] and "127.0.0.1" not in out[0]

    # With a tunnel URL (written by scripts/tunnel.sh) the card's first button opens the Mini App inside Telegram.
    import app.runtime
    app.runtime.WEBAPP_URL_FILE.write_text("https://demo.trycloudflare.com\n")
    await chat.send("/start")
    button = chat.last_markup().inline_keyboard[0][0]
    assert button.web_app.url == "https://demo.trycloudflare.com/survey"
    assert any(type(c).__name__ == "SetChatMenuButton" and c.menu_button.web_app
               and c.menu_button.web_app.url.endswith("/survey") for c in chat.fake.calls)

    # Asking again: only the newest card keeps buttons, so an old one can't be tapped by mistake.
    await session.refresh(world["student"])
    first = world["student"].survey_message_id
    await chat.send("/start")
    edits = [c for c in chat.fake.calls if type(c).__name__ == "EditMessageReplyMarkup"]
    assert edits[-1].message_id == first and edits[-1].reply_markup is None
    await session.refresh(world["student"])
    assert world["student"].survey_message_id not in (None, first)

    # The tunnel got a new address -> the survey button on the card is moved to it.
    from app.bot.menu_button import refresh_survey_buttons
    assert await refresh_survey_buttons(chat.bot, "https://new.trycloudflare.com") == 1
    edit = chat.fake.calls[-1]
    assert (edit.chat_id, edit.message_id) == (777, world["student"].survey_message_id)
    assert edit.reply_markup.inline_keyboard[0][0].web_app.url == "https://new.trycloudflare.com/survey"

    # Changing language to Turkmen: back to the card in Turkmen; the profile opens in the same message.
    out = await chat.press("lang:tk")
    assert any("Salam" in o for o in out)
    out = await chat.press("profile")
    assert "368211100001" in out[0] and "Türkmençe" in out[0]


async def test_login_can_be_closed_from_the_dashboard(chat, session, world):
    from app import settings_store
    await settings_store.save(session, login_open=False, support_contact="@dekanat")
    await session.commit()
    settings_store.reset_cache()
    await chat.send("/start")
    await chat.press("login")
    assert any("⏸" in text and "@dekanat" in text for text in chat.fake.texts())
    out = await chat.send("/myid")
    assert "777" in out[0]


def calls_of(chat, name: str) -> list:
    return [c for c in chat.fake.calls if type(c).__name__ == name]


async def test_menu_card_reactions_logout_and_the_conversation_log(chat, session, world):
    from sqlalchemy import select

    from app.models import BotChat, BotMessage
    await chat.send("/start")
    card = calls_of(chat, "SendPhoto")[-1]           # the welcome card carries the menu picture
    assert card.caption == t("uz", "welcome")
    assert card.reply_markup.inline_keyboard[-1][0].url == "https://t.me/iqtisodiyot_uz1"   # the faculty channel

    await chat.press("login")
    await chat.send("368211100001")
    await chat.send("AS3480990")
    await session.refresh(world["student"])
    assert world["student"].telegram_id == 777
    # Reactions: on /start and on the HEMIS number - not on the passport (that message is deleted at once).
    reactions = [c.reaction[0].emoji for c in calls_of(chat, "SetMessageReaction")]
    assert len(reactions) == 2 and reactions[1] == "👀"

    # Profile › 🚪 Log out, all inside the same photo card.
    await chat.press("profile", photo=True)
    edit = calls_of(chat, "EditMessageCaption")[-1]
    assert "368211100001" in edit.caption and edit.reply_markup.inline_keyboard[0][0].callback_data == "logout"
    await chat.press("logout", photo=True)
    assert calls_of(chat, "EditMessageCaption")[-1].caption == t("uz", "logout_confirm")
    await chat.press("logout:yes", photo=True)
    await session.refresh(world["student"])
    assert world["student"].telegram_id is None and world["student"].survey_message_id is None
    assert calls_of(chat, "EditMessageCaption")[-1].caption == t("uz", "logged_out")
    assert "❌" not in (await chat.send("/start"))[-1]  # back to the welcome card, can log in again

    # Everything is in the conversation log - but never the passport number.
    rows = (await session.execute(select(BotMessage).order_by(BotMessage.id))).scalars().all()
    assert "3480990" not in " ".join(r.text or "" for r in rows)
    assert any(r.dir == "in" and r.text == "/start" and r.reaction for r in rows)
    assert any(r.dir == "in" and "pasport" in r.text and r.deleted for r in rows)
    assert any(r.dir == "out" and r.kind == "photo" and "Talaba Ovozi" in r.text for r in rows)  # the menu card
    assert {r.text for r in rows if r.dir == "tap"} >= {"login", "profile", "logout", "logout:yes"}
    assert (await session.get(BotChat, 777)).name == "Aziz"


async def test_timetable_picture_and_reactions_switch(chat, session, world):
    from sqlalchemy import select

    from app import settings_store
    from app.services import teaching
    from app.timetable import edupage
    from tests.test_timetable import edupage_raw
    st = world["student"]
    st.telegram_id = 777
    await session.commit()
    out = await chat.press("timetable")                 # no timetable yet
    assert t("uz", "tt_none") in out[-1]

    data = edupage.parse(edupage_raw(), "Iqtisodiyot") | {"source": "edupage"}
    await teaching.store_timetable(session, data, title="T", source="x", admin="test")
    st.group_id = (await session.scalar(select(Group).where(Group.name == "26-01 IQT"))).id
    await session.commit()
    await chat.press("timetable")
    photo = calls_of(chat, "SendPhoto")[-1]
    assert "26-01 IQT" in photo.caption and photo.photo.data[:4] == b"\x89PNG"

    assert calls_of(chat, "SetMessageReaction") == []
    await chat.send("Katta rahmat!")
    assert calls_of(chat, "SetMessageReaction")[-1].reaction[0].emoji == "❤"
    await settings_store.save(session, bot_reactions=False)
    await session.commit()
    settings_store.reset_cache()
    await chat.send("rahmat")
    assert len(calls_of(chat, "SetMessageReaction")) == 1


# ---------------------------------------------------------------- the bot for dashboard accounts

async def make_admin(session, **kw):
    from app.models import Admin
    from app.security import hash_password
    admin = Admin(username=kw.pop("username", "dekan"), password_hash=hash_password("secret123"),
                  role=kw.pop("role", "superadmin"), **kw)
    session.add(admin)
    await session.commit()
    return admin


async def test_admin_links_with_a_one_time_link_and_uses_the_admin_menu(chat, session, world, monkeypatch, tmp_path):
    from datetime import datetime, timedelta, timezone

    from sqlalchemy import select

    import app.bot.handlers.admin as admin_handlers
    from app.models import AuditLog
    admin = await make_admin(session, tg_link_token="tok123", tg_link_until=datetime.now(timezone.utc) + timedelta(minutes=5))
    assert t("uz", "home_closed") not in " ".join(await chat.send("/start adm_wrong"))   # a wrong link: just says so
    out = await chat.send("/start adm_tok123")
    await session.refresh(admin)
    assert admin.telegram_id == 777 and admin.tg_link_token is None
    assert any("Bog‘landi" in o for o in out) and any("Assalomu alaykum" in o and "Bosh administrator" in o for o in out)
    assert any(type(c).__name__ == "SetMyCommands" and c.scope and c.scope.chat_id == 777 for c in chat.fake.calls)
    # The token works once.
    admin.telegram_id = None
    await session.commit()
    await chat.send("/start adm_tok123")
    await session.refresh(admin)
    assert admin.telegram_id is None

    admin.telegram_id = 777
    await session.commit()
    import app.runtime
    app.runtime.WEBAPP_URL_FILE.write_text("https://demo.trycloudflare.com\n")
    out = await chat.press("adm:links", photo=True)
    assert "https://demo.trycloudflare.com/survey" in out[-1] and "127.0.0.1" in out[-1]   # dashboard not online
    out = await chat.press("adm:stats", photo=True)
    assert out
    await chat.press("adm:daily", photo=True)
    await session.refresh(admin)
    assert admin.prefs.get("tg_daily") is True

    monkeypatch.setattr(admin_handlers, "request_tunnel_restart", lambda: (tmp_path / "flag").write_text("1"))
    await chat.press("adm:tunnel:yes", photo=True)
    assert (tmp_path / "flag").exists()
    assert await session.scalar(select(AuditLog.path).where(AuditLog.method == "BOT")) == "/bot/tunnel"

    await chat.press("adm:unlink:yes", photo=True)
    await session.refresh(admin)
    assert admin.telegram_id is None
    await chat.press("adm:home")
    alerts = [c for c in chat.fake.calls if type(c).__name__ == "AnswerCallbackQuery" and c.show_alert]
    assert alerts   # not an admin any more: the old card's buttons don't work


async def test_admin_links_by_username_and_viewers_cant_restart_the_tunnel(chat, session, world, tmp_path, monkeypatch):
    from aiogram.types import User
    viewer = await make_admin(session, username="kuzatuvchi", role="viewer", telegram_username="aziz_k")
    await chat.send("salom")                     # another username: nothing happens
    await session.refresh(viewer)
    assert viewer.telegram_id is None
    chat.user = User(id=777, is_bot=False, first_name="Aziz", username="Aziz_K")
    out = await chat.send("salom")
    await session.refresh(viewer)
    assert viewer.telegram_id == 777 and viewer.telegram_name == "Aziz"
    assert any("Kuzatuvchi" in o for o in out)   # the admin card, not "please log in"
    chat.user = User(id=777, is_bot=False, first_name="Aziz", username="new_name")   # username changed: still known
    out = await chat.send("/admin")
    assert any("Assalomu alaykum" in o for o in out)
    import app.bot.handlers.admin as admin_handlers
    monkeypatch.setattr(admin_handlers, "request_tunnel_restart", lambda: (tmp_path / "flag").write_text("1"))
    await chat.press("adm:tunnel:yes", photo=True)
    assert not (tmp_path / "flag").exists()


async def test_new_address_and_daily_report_reach_linked_admins(chat, session, world):
    from datetime import datetime, timedelta, timezone
    from zoneinfo import ZoneInfo

    from app import settings_store
    from app.bot.admin_reports import send_daily
    from app.bot.menu_button import notify_admins
    await make_admin(session, username="a1", telegram_id=101, prefs={"tg_daily": True})
    await make_admin(session, username="a2", telegram_id=102, prefs={"tg_notify": False})
    await settings_store.save(session, admin_telegram_ids=[555])
    await session.commit()
    settings_store.reset_cache()
    await notify_admins(chat.bot, "https://x.trycloudflare.com")
    told = sorted(c.chat_id for c in chat.fake.calls if type(c).__name__ == "SendMessage")
    assert told == [101, 555]

    now = datetime.now(timezone.utc)
    session.add(SurveyCampaign(semester_id=world["sem"].id, title="Kuz", opens_at=now - timedelta(days=1),
                               closes_at=now + timedelta(days=3)))
    await session.commit()
    evening = datetime.now(ZoneInfo("Asia/Tashkent")).replace(hour=20, minute=30)
    assert await send_daily(chat.bot, evening.replace(hour=19)) == 0      # not yet
    assert await send_daily(chat.bot, evening) == 1
    assert await send_daily(chat.bot, evening) == 0                       # once a day
    report = [c for c in chat.fake.calls if type(c).__name__ == "SendMessage"][-1]
    assert report.chat_id == 101 and "Kuz" in report.text
