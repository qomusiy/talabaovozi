import re
from datetime import date, datetime, timedelta, timezone

import pytest
from aiogram import Bot, Dispatcher
from aiogram.client.session.base import BaseSession
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.methods import TelegramMethod
from aiogram.types import CallbackQuery, Chat, InlineKeyboardMarkup, Message, PhotoSize, Update, User
from sqlalchemy import select

from app.bot import chatlog
from app.bot.handlers import admin, menu, start
from app.bot.i18n import LANGUAGE_NAMES, TEXTS, t
from app.bot.middleware import ContextMiddleware
from app.bot.reactions import ReactionMiddleware
from app.models import (BotUser, Department, Feedback, Group, Semester, Subject, SurveyCampaign, Teacher,
                        TeachingAssignment)
from app.services import survey as svc
from app.services import users


def test_every_text_has_all_languages_and_same_placeholders():
    for key, entry in TEXTS.items():
        assert set(entry) == set(LANGUAGE_NAMES), key
        placeholders = {lang: set(re.findall(r"{(\w+)}", s)) for lang, s in entry.items()}
        assert len({frozenset(p) for p in placeholders.values()}) == 1, (key, placeholders)


@pytest.fixture
async def world(session):
    group = Group(name="25-16 IQT", code="IQT", course=2, student_count=25)
    other_group = Group(name="25-17 BXA", code="BXA", course=2, student_count=20)
    sem = Semester(name="2026-2027 Fall", starts_on=date(2026, 9, 1), ends_on=date(2027, 1, 20), is_current=True)
    dept = Department(name="Iqtisodiyot nazariyasi")
    t1 = Teacher(full_name="Qodirov Rustam", department=dept, room_number="2-14")
    t2 = Teacher(full_name="Saidova Madina")
    t3 = Teacher(full_name="Other Group Teacher")
    subj = Subject(name="Makroiqtisodiyot")
    session.add_all([
        sem, t3,
        TeachingAssignment(semester=sem, teacher=t1, group=group, subject=subj, lesson_type="lecture"),
        TeachingAssignment(semester=sem, teacher=t1, group=group, subject=Subject(name="Mikro"), lesson_type="practice"),
        TeachingAssignment(semester=sem, teacher=t2, group=group, subject=subj, lesson_type="practice"),
        TeachingAssignment(semester=sem, teacher=t3, group=other_group, subject=subj, lesson_type="lecture"),
    ])
    await session.commit()
    return {"group": group, "other": other_group, "t1": t1, "t2": t2, "t3": t3, "sem": sem}


async def open_campaign(session, world, title="Mid-term"):
    now = datetime.now(timezone.utc)
    camp = SurveyCampaign(semester_id=world["sem"].id, title=title, opens_at=now - timedelta(days=1),
                          closes_at=now + timedelta(days=7))
    session.add(camp)
    await session.commit()
    return camp


async def test_teachers_of_a_group_or_every_teacher_without_one(session, world):
    user = BotUser(id=5, group_id=world["group"].id)
    session.add(user)
    await session.commit()
    cards = await svc.teachers_of(session, user)
    assert [c.teacher.full_name for c in cards] == ["Qodirov Rustam", "Saidova Madina"]
    assert len(cards[0].lessons) == 2
    assert await svc.may_rate(session, user, world["t1"].id) and not await svc.may_rate(session, user, world["t3"].id)
    user.group_id = None
    assert [c.teacher.full_name for c in await svc.teachers_of(session, user)] == [
        "Other Group Teacher", "Qodirov Rustam", "Saidova Madina"]
    assert await svc.may_rate(session, user, world["t3"].id)


def test_flood_guard_counts_a_burst_not_a_steady_pace():
    users._recent.clear()
    assert not any(users.flooding(1, now=i * 1.0) for i in range(30))   # one a second: fine
    assert any(users.flooding(2, now=100 + i * 0.1) for i in range(25))  # 25 in 2.5 s: stopped


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
        self.dp.update.outer_middleware(chatlog.IncomingLog())
        self.dp.update.outer_middleware(ContextMiddleware())
        self.dp.message.middleware(ReactionMiddleware())
        self.bot.session.middleware(chatlog.OutgoingLog())
        self.dp.include_routers(admin.router, start.router, menu.router)
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

    @property
    def card(self) -> int:
        """The card a tap is on: the newest one the bot sent (as a person taps the card at the bottom)."""
        sent = [c for c in self.fake.calls if _text(c) and type(c).__name__ in ("SendPhoto", "SendMessage")]
        return 100 + self.fake.calls.index(sent[-1]) + 1 if sent else 1

    async def press(self, data: str, photo: bool = False, on: int | None = None) -> list[str]:
        """Tap a button under a card (photo=True: a card with the menu picture, as the bot sends them); on: the
        message id of the card (default: the newest)."""
        self.n += 1
        start = len(self.fake.texts())
        msg = Message(message_id=on or self.card, date=datetime.now(), chat=Chat(id=777, type="private"),
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
    from app.bot import cards
    from app.services import users
    users._recent.clear()
    cards._swaps.clear()
    # Handlers open their own sessions via app.db; they point at the same test database.
    for r in (admin.router, start.router, menu.router):
        r._parent_router = None  # routers can only be attached once; reset between tests
    return Chatter()


async def test_first_visit_language_intro_and_picking_a_group(chat, session, world):
    out = await chat.send("/start")
    assert out == [t("uz", "pick_language")]                       # the first time: the language first
    user = await session.get(BotUser, 777)
    assert user.first_name == "Aziz" and user.onboarded_at is None and user.updates == 1

    out = await chat.press("lang:ru")
    assert out[-1] == t("ru", "intro") and "Анонимность" in out[-1]  # what the bot is: anonymous, the group filters
    assert [[b.callback_data for b in row] for row in chat.last_markup().inline_keyboard] == [["pick:intro"]]
    out = await chat.press("pick:intro")
    assert out[-1] == t("ru", "pick_course")
    course = chat.last_markup().inline_keyboard[0][0]
    assert course.text == "2 курс" and course.callback_data == "pc:intro:2"
    out = await chat.press("pc:intro:2")
    names = [row[0].text for row in chat.last_markup().inline_keyboard[:-1]]
    assert names == ["Бухгалтерский учёт", "Экономика"]            # the course's specialties, by name
    assert [b.callback_data for b in chat.last_markup().inline_keyboard[-1]] == ["pick:intro"]  # Back, no "no group"
    out = await chat.press("ps:intro:2:IQT")
    assert "Экономика" in out[-1]
    pick = chat.last_markup().inline_keyboard[0][0]
    assert pick.text == "25-16 IQT"
    out = await chat.press(pick.callback_data)
    await session.refresh(user)
    assert user.group_id == world["group"].id and user.onboarded_at is not None and user.language == "ru"
    assert out[-1].startswith("👋 ") and "\n\n🎓 25-16 IQT\n\n" + t("ru", "survey_closed") in out[-1]
    home = [[b.callback_data for b in row] for row in chat.last_markup().inline_keyboard]
    assert ["pick:home", "choose_lang"] in home and "profile" not in str(home)   # "Change group" instead of a profile

    # "My teachers": only this group's.
    out = await chat.press("teachers:1")
    assert "Qodirov Rustam" in out[0] and "Saidova Madina" in out[0] and "Other Group" not in out[0]
    assert "лекция" in out[0] and "2-14" in out[0]

    # A survey opens: the home card shows how many teachers are rated, and the days left.
    camp = await open_campaign(session, world)
    session.add(Feedback(campaign_id=camp.id, user_id=777, teacher_id=world["t1"].id, group_id=world["group"].id,
                         teaching=9, fairness=8, professionalism=10))
    await session.commit()
    out = await chat.press("home")
    assert t("ru", "survey_open") in out[0] and t("ru", "rated_n", done=1, total=2) in out[0]
    assert "⏳" in out[0] and "Mid-term" not in out[0] and "%" not in out[0]

    # With a public address the card's first button opens the Mini App.
    import app.runtime
    app.runtime.WEBAPP_URL_FILE.write_text("https://demo.trycloudflare.com\n")
    await chat.send("/start")
    assert chat.last_markup().inline_keyboard[0][0].web_app.url == "https://demo.trycloudflare.com/survey"
    assert any(type(c).__name__ == "SetChatMenuButton" and c.menu_button.web_app for c in chat.fake.calls)

    # Only the newest card stays (the one before is deleted); a new address moves the survey button on it.
    await session.refresh(user)
    first = user.survey_message_id
    await chat.send("/start")
    assert calls_of(chat, "DeleteMessage")[-1].message_id == first
    from app.bot.menu_button import refresh_survey_buttons
    assert await refresh_survey_buttons(chat.bot, "https://new.trycloudflare.com") == 1
    assert chat.fake.calls[-1].reply_markup.inline_keyboard[0][0].web_app.url == "https://new.trycloudflare.com/survey"

    # Turkmen; a "Profile" button of an old card leads to picking the group.
    out = await chat.press("lang:tk")
    assert any("haýyrly" in o for o in out)
    out = await chat.press("profile")
    assert out[-1] == t("tk", "pick_course")
    assert [b.callback_data for b in chat.last_markup().inline_keyboard[-1]] == ["home"]


async def test_group_numbers_name_the_group_for_students(chat, session, world):
    world["group"].number = "216"
    session.add(Group(name="25-18 IQT", code="IQT", course=2, number="205"))
    session.add(BotUser(id=777, language="uz", onboarded_at=datetime.now(timezone.utc)))
    await session.commit()
    session.add(TeachingAssignment(semester=world["sem"], teacher=world["t2"], subject=Subject(name="X"),
                                   group=await session.scalar(select(Group).where(Group.name == "25-18 IQT"))))
    await session.commit()
    await chat.press("ps:home:2:IQT")
    assert [b.text for b in chat.last_markup().inline_keyboard[0]] == ["205", "216"]   # by number, as students know
    out = await chat.press(f"pg:{world['group'].id}")
    assert "\n\n🎓 216-guruh\n\n" in out[-1] and "25-16" not in out[-1]


async def test_an_old_user_without_a_group_is_asked_to_pick_one(chat, session, world):
    session.add(BotUser(id=777, language="uz", onboarded_at=datetime.now(timezone.utc)))   # "without a group", before
    await session.commit()
    await open_campaign(session, world)
    out = await chat.send("/start")
    assert t("uz", "no_group") in out[-1] and t("uz", "cta_pick_group") in out[-1]
    assert [b.callback_data for b in chat.last_markup().inline_keyboard[0]] == ["pick:home"]   # no survey button
    out = await chat.press("timetable")
    assert t("uz", "tt_need_group") in out[-1]
    out = await chat.press("teachers:1")
    assert t("uz", "no_group") in out[-1]
    out = await chat.press("nogroup")                 # the old "go on without a group": picking one instead
    assert out[-1] == t("uz", "pick_course")
    out = await chat.press("login")                   # an old button of the login days: just the home card
    assert t("uz", "no_group") in out[-1]


async def test_a_tap_swaps_the_card_and_a_double_tap_sends_one(chat, session, world):
    await chat.send("/start")
    card = chat.card
    await chat.press("lang:uz", photo=True)
    assert calls_of(chat, "DeleteMessage")[-1].message_id == card     # the tapped card goes ...
    assert calls_of(chat, "SendPhoto")[-1].caption == t("uz", "intro")  # ... and the next one comes, with the picture
    assert calls_of(chat, "EditMessageCaption") == []
    sent = len(calls_of(chat, "SendPhoto"))
    card = chat.card
    await chat.press("pick:intro", photo=True, on=card)
    await chat.press("pick:intro", photo=True, on=card)   # tapped twice before the new card came
    assert len(calls_of(chat, "SendPhoto")) == sent + 1
    assert [c.message_id for c in calls_of(chat, "DeleteMessage")][-1] == card


async def test_blocked_and_suspended_users_are_stopped_and_flooding_suspends(chat, session, world):
    from app.bot import middleware
    await chat.send("/start")
    user = await session.get(BotUser, 777)
    user.blocked = True
    await session.commit()
    middleware._told.clear()
    out = await chat.send("salom")
    assert len(out) == 1 and "⛔" in out[0]
    assert await chat.send("salom") == []          # said once, not on every message
    user.blocked = False
    await session.commit()
    middleware._told.clear()
    for _ in range(25):                            # a burst: the flood guard stops them for a while
        out = await chat.send("spam")
    await session.refresh(user)
    assert user.floods == 1 and user.suspended_until > datetime.now(timezone.utc) + timedelta(minutes=9)
    assert t("uz", "flood_stopped") in chat.fake.texts()
    # Every message is in the conversation log - the stopped ones too.
    from app.models import BotMessage
    n = await session.scalar(select(__import__("sqlalchemy").func.count(BotMessage.id)).where(
        BotMessage.chat_id == 777, BotMessage.dir == "in"))
    assert n == 28


async def test_menu_card_reactions_and_the_conversation_log(chat, session, world):
    from app.models import BotChat, BotMessage
    await chat.send("/start")
    card = calls_of(chat, "SendPhoto")[-1]           # the language card carries the menu picture
    assert card.caption == t("uz", "pick_language")
    await chat.press("lang:uz", photo=True)
    assert calls_of(chat, "SendPhoto")[-1].caption == t("uz", "intro")
    await chat.press(f"pg:{world['group'].id}", photo=True)
    card = calls_of(chat, "SendPhoto")[-1]
    assert card.reply_markup.inline_keyboard[-1][-1].url == "https://t.me/iqtisodiyot_uz1"   # the faculty channel
    reactions = [c.reaction[0].emoji for c in calls_of(chat, "SetMessageReaction")]
    assert len(reactions) == 1                       # on /start
    await chat.send("AS3480990")                      # a passport out of habit: never stored
    rows = (await session.execute(select(BotMessage).order_by(BotMessage.id))).scalars().all()
    assert "3480990" not in " ".join(r.text or "" for r in rows)
    assert any(r.dir == "in" and r.text == "/start" and r.reaction for r in rows)
    assert {r.text for r in rows if r.dir == "tap"} >= {"lang:uz", f"pg:{world['group'].id}"}
    assert (await session.get(BotChat, 777)).name == "Aziz"


async def test_timetable_picture_and_reactions_switch(chat, session, world):
    from app import settings_store
    from app.services import teaching
    from app.timetable import edupage
    from tests.test_timetable import edupage_raw
    data = edupage.parse(edupage_raw(), "Iqtisodiyot") | {"source": "edupage"}
    await teaching.store_timetable(session, data, title="T", source="x", admin="test")
    gid = (await session.scalar(select(Group).where(Group.name == "26-01 IQT"))).id
    session.add(BotUser(id=777, group_id=gid, onboarded_at=datetime.now(timezone.utc)))
    await session.commit()
    await chat.press("timetable")
    photo = next(c for c in calls_of(chat, "SendPhoto") if "jadval" in c.caption)
    assert photo.caption.startswith("📅 <b>26-01 IQT — haftalik dars jadvali</b>\n\nEduPage veb-saytidagi ")
    assert "Bugun" not in photo.caption and photo.photo.data[:4] == b"\x89PNG"   # the week, nothing about today
    assert calls_of(chat, "SendPhoto")[-1].caption.startswith("👋")   # the menu moves under the picture

    assert calls_of(chat, "SetMessageReaction") == []
    await chat.send("Katta rahmat!")
    assert calls_of(chat, "SetMessageReaction")[-1].reaction[0].emoji == "❤"
    await settings_store.save(session, bot_reactions=False)
    await session.commit()
    settings_store.reset_cache()
    await chat.send("rahmat")
    assert len(calls_of(chat, "SetMessageReaction")) == 1

    group = await session.get(Group, gid)              # the number students know the group by, once typed in
    group.number = "105"
    await session.commit()
    await chat.send("/timetable")
    assert "105-guruh — haftalik dars jadvali" in calls_of(chat, "SendPhoto")[-1].caption


def calls_of(chat, name: str) -> list:
    return [c for c in chat.fake.calls if type(c).__name__ == name]


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
    assert t("uz", "survey_closed") not in " ".join(await chat.send("/start adm_wrong"))   # a wrong link: just says so
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
    assert any("Kuzatuvchi" in o for o in out)   # the admin card, not the language card
    chat.user = User(id=777, is_bot=False, first_name="Aziz", username="new_name")   # username changed: still known
    out = await chat.send("/admin")
    assert any("Assalomu alaykum" in o for o in out)
    import app.bot.handlers.admin as admin_handlers
    monkeypatch.setattr(admin_handlers, "request_tunnel_restart", lambda: (tmp_path / "flag").write_text("1"))
    await chat.press("adm:tunnel:yes", photo=True)
    assert not (tmp_path / "flag").exists()


async def test_server_messages_are_off_by_default_and_one_message_is_kept_up_to_date(chat, session, world, monkeypatch):
    import app.bot.server_alerts as alerts
    from app import settings_store
    await make_admin(session, username="a1", telegram_id=101, prefs={"tg_server": True})
    await make_admin(session, username="a2", telegram_id=102)                      # never switched on
    settings_store.reset_cache()
    site = {"ok": False}

    async def answers(url):
        return site["ok"]
    monkeypatch.setattr(alerts, "site_answers", answers)
    monkeypatch.setattr(alerts, "server_status", lambda: {"started": 1000, "children": {"web": {"running": True}}})
    monkeypatch.setattr(alerts, "webapp_url", lambda: "")
    state = await alerts.tick(chat.bot, now=2000)                                  # the server started
    sent = calls_of(chat, "SendMessage")
    assert [c.chat_id for c in sent] == [101] and "Server ishga tushdi" in sent[0].text
    assert "manzil olinmoqda" in sent[0].text and not state["done"]

    monkeypatch.setattr(alerts, "webapp_url", lambda: "https://a.trycloudflare.com")
    await alerts.tick(chat.bot, now=2010)                                          # the address is known
    edit = calls_of(chat, "EditMessageText")[-1]
    assert edit.message_id == state["messages"]["101"] and "a.trycloudflare.com" in edit.text
    site["ok"] = True
    state = await alerts.tick(chat.bot, now=2070)                                  # it answers: done
    assert "Hammasi ishlayapti" in calls_of(chat, "EditMessageText")[-1].text and state["done"]
    n = len(chat.fake.calls)
    await alerts.tick(chat.bot, now=2080)
    assert len(chat.fake.calls) == n                                               # nothing more to say
    assert len(calls_of(chat, "SendMessage")) == 1                                 # one message, edited

    monkeypatch.setattr(alerts, "webapp_url", lambda: "https://b.trycloudflare.com")
    await alerts.tick(chat.bot, now=3000)                                          # a new address: a new message
    assert "manzili yangilandi" in calls_of(chat, "SendMessage")[-1].text


async def test_daily_report_reaches_admins_who_want_it(chat, session, world):
    from zoneinfo import ZoneInfo

    from app.bot.admin_reports import send_daily
    await make_admin(session, username="a1", telegram_id=101, prefs={"tg_daily": True})
    await make_admin(session, username="a2", telegram_id=102)
    await open_campaign(session, world, title="Kuz")
    evening = datetime.now(ZoneInfo("Asia/Tashkent")).replace(hour=20, minute=30)
    assert await send_daily(chat.bot, evening.replace(hour=19)) == 0      # not yet
    assert await send_daily(chat.bot, evening) == 1
    assert await send_daily(chat.bot, evening) == 0                       # once a day
    report = calls_of(chat, "SendMessage")[-1]
    assert report.chat_id == 101 and "Kuz" in report.text
