"""Texts of the bot's admin menu (Uzbek, English, Russian - the dashboard's languages; others get Uzbek)."""

TEXTS: dict[str, dict[str, str]] = {
    "home": {
        "uz": "🛡 <b>Assalomu alaykum, {name}!</b>\n<i>Talaba Ovozi · {role}</i>\n\n{survey}\n\n"
              "🤖 Botda: <b>{in_bot}</b> / {students} talaba\n🌐 Sayt: {site}",
        "en": "🛡 <b>Hello, {name}!</b>\n<i>Talaba Ovozi · {role}</i>\n\n{survey}\n\n"
              "🤖 In the bot: <b>{in_bot}</b> / {students} students\n🌐 Site: {site}",
        "ru": "🛡 <b>Здравствуйте, {name}!</b>\n<i>Talaba Ovozi · {role}</i>\n\n{survey}\n\n"
              "🤖 В боте: <b>{in_bot}</b> / {students} студентов\n🌐 Сайт: {site}",
    },
    "survey_open": {
        "uz": "📝 <b>{title}</b>\n🟢 Ochiq · {left}\n\n👥 Ishtirok: <b>{participants}</b> talaba ({pct}%)\n"
              "✅ Hammasini baholagan: <b>{completed}</b>\n⭐ Baholar: <b>{evaluations}</b> · bugun <b>+{today}</b>\n"
              "📊 O‘rtacha ball: <b>{overall}</b> / 10\n💬 Izohlar: <b>{comments}</b>",
        "en": "📝 <b>{title}</b>\n🟢 Open · {left}\n\n👥 Took part: <b>{participants}</b> students ({pct}%)\n"
              "✅ Rated everyone: <b>{completed}</b>\n⭐ Ratings: <b>{evaluations}</b> · today <b>+{today}</b>\n"
              "📊 Average: <b>{overall}</b> / 10\n💬 Comments: <b>{comments}</b>",
        "ru": "📝 <b>{title}</b>\n🟢 Открыт · {left}\n\n👥 Участвуют: <b>{participants}</b> студентов ({pct}%)\n"
              "✅ Оценили всех: <b>{completed}</b>\n⭐ Оценок: <b>{evaluations}</b> · сегодня <b>+{today}</b>\n"
              "📊 Средний балл: <b>{overall}</b> / 10\n💬 Комментариев: <b>{comments}</b>",
    },
    "survey_closed": {
        "uz": "🕊 Hozir ochiq so‘rovnoma yo‘q.\nOxirgisi: <b>{title}</b> — ishtirok {pct}%, {evaluations} ta baho, "
              "o‘rtacha {overall}",
        "en": "🕊 No survey is open now.\nThe last one: <b>{title}</b> — {pct}% took part, {evaluations} ratings, "
              "average {overall}",
        "ru": "🕊 Сейчас нет открытого опроса.\nПоследний: <b>{title}</b> — участие {pct}%, {evaluations} оценок, "
              "в среднем {overall}",
    },
    "survey_none": {"uz": "🕊 Hali so‘rovnoma o‘tkazilmagan.", "en": "🕊 No survey has been run yet.",
                    "ru": "🕊 Опросов ещё не было."},
    "left_days": {"uz": "{n} kun qoldi", "en": "{n} days left", "ru": "осталось дней: {n}"},
    "left_today": {"uz": "bugun yopiladi", "en": "closes today", "ru": "закрывается сегодня"},
    "site_ok": {"uz": "🟢 ishlayapti", "en": "🟢 working", "ru": "🟢 работает"},
    "site_down": {"uz": "🔴 ishlamayapti — yangi manzil olinmoqda", "en": "🔴 down — getting a new address",
                  "ru": "🔴 не работает — получаем новый адрес"},
    "site_starting": {"uz": "🟡 ishga tushmoqda", "en": "🟡 starting", "ru": "🟡 запускается"},
    "site_unknown": {"uz": "⚪ noma’lum (tekshiruv to‘xtagan)", "en": "⚪ unknown (not checked lately)",
                     "ru": "⚪ неизвестно (давно не проверялся)"},
    "site_none": {"uz": "⚪ internet manzili yo‘q", "en": "⚪ no public address", "ru": "⚪ нет адреса в интернете"},
    # Buttons
    "btn_app": {"uz": "📊 Statistika (Mini App)", "en": "📊 Statistics (Mini App)", "ru": "📊 Статистика (Mini App)"},
    "btn_links": {"uz": "🔗 Sayt manzili", "en": "🔗 Site address", "ru": "🔗 Адрес сайта"},
    "btn_stats": {"uz": "📈 Batafsil", "en": "📈 Details", "ru": "📈 Подробно"},
    "btn_notify_on": {"uz": "🔔 Xabarnoma: yoqiq", "en": "🔔 Alerts: on", "ru": "🔔 Уведомления: вкл"},
    "btn_notify_off": {"uz": "🔕 Xabarnoma: o‘chiq", "en": "🔕 Alerts: off", "ru": "🔕 Уведомления: выкл"},
    "btn_daily_on": {"uz": "📬 Kunlik hisobot: yoqiq", "en": "📬 Daily report: on", "ru": "📬 Ежедневный отчёт: вкл"},
    "btn_daily_off": {"uz": "📭 Kunlik hisobot: o‘chiq", "en": "📭 Daily report: off", "ru": "📭 Ежедневный отчёт: выкл"},
    "btn_refresh": {"uz": "🔄 Yangilash", "en": "🔄 Refresh", "ru": "🔄 Обновить"},
    "btn_tunnel": {"uz": "🛠 Yangi manzil olish", "en": "🛠 Get a new address", "ru": "🛠 Новый адрес"},
    "btn_tunnel_yes": {"uz": "✅ Ha, yangi manzil", "en": "✅ Yes, new address", "ru": "✅ Да, новый адрес"},
    "btn_student": {"uz": "🎓 Talaba menyusi", "en": "🎓 Student menu", "ru": "🎓 Меню студента"},
    "btn_unlink": {"uz": "🔌 Botdan uzish", "en": "🔌 Unlink from the bot", "ru": "🔌 Отвязать от бота"},
    "btn_unlink_yes": {"uz": "✅ Ha, uzish", "en": "✅ Yes, unlink", "ru": "✅ Да, отвязать"},
    "btn_open_admin": {"uz": "📊 Admin saytni ochish", "en": "📊 Open the dashboard", "ru": "📊 Открыть админ-сайт"},
    "btn_open_survey": {"uz": "📝 So‘rovnoma", "en": "📝 Survey", "ru": "📝 Опрос"},
    "btn_back": {"uz": "⬅️ Orqaga", "en": "⬅️ Back", "ru": "⬅️ Назад"},
    # Sections
    "links": {
        "uz": "🔗 <b>Manzillar</b>\n\n📝 <b>So‘rovnoma</b> (talabalarning Mini App’i):\n<code>{url}/survey</code>\n\n"
              "📊 <b>Admin sayt:</b>\n{admin}\n\n🌐 Holati: {site}{checked}",
        "en": "🔗 <b>Addresses</b>\n\n📝 <b>Survey</b> (the students’ Mini App):\n<code>{url}/survey</code>\n\n"
              "📊 <b>Dashboard:</b>\n{admin}\n\n🌐 Status: {site}{checked}",
        "ru": "🔗 <b>Адреса</b>\n\n📝 <b>Опрос</b> (Mini App студентов):\n<code>{url}/survey</code>\n\n"
              "📊 <b>Админ-сайт:</b>\n{admin}\n\n🌐 Состояние: {site}{checked}",
    },
    "admin_online": {"uz": "<code>{url}/admin</code>", "en": "<code>{url}/admin</code>", "ru": "<code>{url}/admin</code>"},
    "admin_local": {
        "uz": "🔒 Internetda yopiq — faqat server kompyuterida: <code>http://127.0.0.1:{port}/admin</code>\n"
              "Ochish: admin sayt › Telegram bot › «Admin saytini internetda ochish».",
        "en": "🔒 Closed to the internet — only on the server computer: <code>http://127.0.0.1:{port}/admin</code>\n"
              "To open it: dashboard › Telegram bot › «Open the dashboard on the internet».",
        "ru": "🔒 Закрыт для интернета — только на компьютере-сервере: <code>http://127.0.0.1:{port}/admin</code>\n"
              "Открыть: админ-сайт › Telegram-бот › «Открыть админ-сайт в интернете».",
    },
    "no_url": {
        "uz": "⚠️ Hozir internet manzili yo‘q — tunnel ishga tushmoqda. 1–2 daqiqadan so‘ng «🔄 Yangilash» ni bosing.",
        "en": "⚠️ There’s no public address right now — the tunnel is starting. Tap «🔄 Refresh» in 1–2 minutes.",
        "ru": "⚠️ Сейчас нет адреса в интернете — туннель запускается. Нажмите «🔄 Обновить» через 1–2 минуты.",
    },
    "checked": {"uz": " · {n} daqiqa oldin tekshirildi", "en": " · checked {n} min ago", "ru": " · проверено {n} мин назад"},
    "stats": {
        "uz": "📈 <b>{title}</b>\n\n<b>Kurslar bo‘yicha ishtirok</b>\n{courses}\n\n<b>Eng past ishtirok</b>\n{low}\n\n"
              "<b>Mezonlar</b> (o‘rtacha)\n🎓 O‘qitish: <b>{teaching}</b>\n⚖️ Adolat: <b>{fairness}</b>\n"
              "🤝 Kasbiylik: <b>{professionalism}</b>\n\n<b>Oxirgi kunlar</b>\n{daily}",
        "en": "📈 <b>{title}</b>\n\n<b>Participation by year</b>\n{courses}\n\n<b>Lowest participation</b>\n{low}\n\n"
              "<b>Criteria</b> (average)\n🎓 Teaching: <b>{teaching}</b>\n⚖️ Fairness: <b>{fairness}</b>\n"
              "🤝 Professionalism: <b>{professionalism}</b>\n\n<b>Recent days</b>\n{daily}",
        "ru": "📈 <b>{title}</b>\n\n<b>Участие по курсам</b>\n{courses}\n\n<b>Самое низкое участие</b>\n{low}\n\n"
              "<b>Критерии</b> (в среднем)\n🎓 Преподавание: <b>{teaching}</b>\n⚖️ Справедливость: <b>{fairness}</b>\n"
              "🤝 Профессионализм: <b>{professionalism}</b>\n\n<b>Последние дни</b>\n{daily}",
    },
    "course_line": {"uz": "{course}-kurs  {bar} <b>{pct}%</b> ({p}/{n})", "en": "Year {course}  {bar} <b>{pct}%</b> ({p}/{n})",
                    "ru": "{course} курс  {bar} <b>{pct}%</b> ({p}/{n})"},
    "low_line": {"uz": "• {name} — <b>{pct}%</b> ({p}/{n})", "en": "• {name} — <b>{pct}%</b> ({p}/{n})",
                 "ru": "• {name} — <b>{pct}%</b> ({p}/{n})"},
    "day_line": {"uz": "{date}: <b>{n}</b> ta baho", "en": "{date}: <b>{n}</b> ratings", "ru": "{date}: <b>{n}</b> оценок"},
    "nothing": {"uz": "—", "en": "—", "ru": "—"},
    "tunnel_confirm": {
        "uz": "🛠 <b>Yangi manzil olinsinmi?</b>\n\nHozirgi manzil o‘chadi, 1–2 daqiqada yangisi tayyor bo‘ladi va bot "
              "tugmalari o‘zi yangilanadi. Faqat sayt ochilmay qolganda kerak.",
        "en": "🛠 <b>Get a new address?</b>\n\nThe current one stops working, a new one is ready in 1–2 minutes and the "
              "bot moves its buttons there itself. Only needed when the site doesn’t open.",
        "ru": "🛠 <b>Получить новый адрес?</b>\n\nТекущий перестанет работать, новый будет готов через 1–2 минуты, бот "
              "сам переведёт кнопки. Нужно, только если сайт не открывается.",
    },
    "tunnel_done": {
        "uz": "✅ Yangi manzil so‘raldi. Tayyor bo‘lgach (1–2 daqiqa) shu yerga yuboraman.",
        "en": "✅ A new address was requested. I’ll send it here when it’s ready (1–2 minutes).",
        "ru": "✅ Новый адрес запрошен. Пришлю его сюда, когда будет готов (1–2 минуты).",
    },
    "unlink_confirm": {
        "uz": "🔌 <b>Botdan uzilsinmi?</b>\n\nBot sizni admin sifatida tanimay qo‘yadi. Qayta ulash: admin sayt › "
              "Mening hisobim › Telegram.",
        "en": "🔌 <b>Unlink from the bot?</b>\n\nThe bot will stop knowing you as an admin. To link again: dashboard › "
              "My account › Telegram.",
        "ru": "🔌 <b>Отвязать от бота?</b>\n\nБот перестанет узнавать вас как админа. Привязать снова: админ-сайт › "
              "Мой аккаунт › Telegram.",
    },
    "unlinked": {"uz": "🔌 Uzildi. Qayta ulash: admin sayt › Mening hisobim › Telegram.",
                 "en": "🔌 Unlinked. To link again: dashboard › My account › Telegram.",
                 "ru": "🔌 Отвязано. Привязать снова: админ-сайт › Мой аккаунт › Telegram."},
    "linked": {
        "uz": "✅ <b>Bog‘landi!</b> Bot sizni <b>{username}</b> admin hisobi sifatida taniydi (Telegram ID orqali — "
              "username o‘zgarsa ham). Sayt manzili o‘zgarsa, shu yerga yuboraman.",
        "en": "✅ <b>Linked!</b> The bot knows you as the <b>{username}</b> dashboard account (by your Telegram ID — "
              "even if your username changes). I’ll send the site address here when it changes.",
        "ru": "✅ <b>Привязано!</b> Бот узнаёт вас как аккаунт <b>{username}</b> (по Telegram ID — даже если username "
              "сменится). Если адрес сайта изменится, пришлю его сюда.",
    },
    "link_bad": {
        "uz": "⚠️ Bu havola eskirgan yoki noto‘g‘ri. Admin saytda «Mening hisobim › Telegram» dan yangisini oling.",
        "en": "⚠️ This link has expired or is wrong. Get a new one in the dashboard: «My account › Telegram».",
        "ru": "⚠️ Ссылка устарела или неверна. Получите новую на админ-сайте: «Мой аккаунт › Telegram».",
    },
    "notify_on": {"uz": "🔔 Manzil o‘zgarsa xabar beraman", "en": "🔔 I’ll tell you when the address changes",
                  "ru": "🔔 Сообщу, когда адрес изменится"},
    "notify_off": {"uz": "🔕 Manzil xabarlari o‘chirildi", "en": "🔕 Address alerts are off", "ru": "🔕 Уведомления об адресе выключены"},
    "daily_on": {"uz": "📬 So‘rovnoma ochiq kunlari 20:00 da qisqa hisobot yuboraman",
                 "en": "📬 While a survey is open, I’ll send a short report at 20:00",
                 "ru": "📬 Пока опрос открыт, буду присылать короткий отчёт в 20:00"},
    "daily_off": {"uz": "📭 Kunlik hisobot o‘chirildi", "en": "📭 Daily report is off", "ru": "📭 Ежедневный отчёт выключен"},
    "daily_report": {
        "uz": "📬 <b>Kunlik hisobot · {date}</b>\n\n📝 {title} · {left}\n⭐ Bugun: <b>+{today}</b> baho\n"
              "👥 Ishtirok: <b>{pct}%</b> ({participants} talaba)\n✅ Hammasini baholagan: <b>{completed}</b>\n"
              "📊 O‘rtacha ball: <b>{overall}</b>",
        "en": "📬 <b>Daily report · {date}</b>\n\n📝 {title} · {left}\n⭐ Today: <b>+{today}</b> ratings\n"
              "👥 Took part: <b>{pct}%</b> ({participants} students)\n✅ Rated everyone: <b>{completed}</b>\n"
              "📊 Average: <b>{overall}</b>",
        "ru": "📬 <b>Отчёт за день · {date}</b>\n\n📝 {title} · {left}\n⭐ Сегодня: <b>+{today}</b> оценок\n"
              "👥 Участие: <b>{pct}%</b> ({participants} студентов)\n✅ Оценили всех: <b>{completed}</b>\n"
              "📊 Средний балл: <b>{overall}</b>",
    },
    "super_only": {"uz": "Bu faqat superadminlar uchun.", "en": "Superadmins only.", "ru": "Только для суперадминов."},
    "cmd_admin": {"uz": "Admin menyusi", "en": "Admin menu", "ru": "Меню админа"},
    "cmd_link": {"uz": "Sayt manzili", "en": "Site address", "ru": "Адрес сайта"},
}


def ta(lang: str | None, key: str, **kwargs) -> str:
    entry = TEXTS[key]
    text = entry.get(lang or "uz") or entry["uz"]
    return text.format(**kwargs) if kwargs else text
