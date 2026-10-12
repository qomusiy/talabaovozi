"""Texts of the bot's admin menu (Uzbek, English, Russian - the dashboard's languages; others get Uzbek)."""

TEXTS: dict[str, dict[str, str]] = {
    "home": {
        "uz": "🛡 <b>Assalomu alaykum, {name}!</b>\n<i>Talaba Ovozi · {role}</i>\n\n{survey}\n\n"
              "🤖 Botda: <b>{in_bot}</b> foydalanuvchi · fakultetda {students} talaba\n🌐 Sayt: {site}",
        "en": "🛡 <b>Hello, {name}!</b>\n<i>Talaba Ovozi · {role}</i>\n\n{survey}\n\n"
              "🤖 In the bot: <b>{in_bot}</b> users · {students} students in the faculty\n🌐 Site: {site}",
        "ru": "🛡 <b>Здравствуйте, {name}!</b>\n<i>Talaba Ovozi · {role}</i>\n\n{survey}\n\n"
              "🤖 В боте: <b>{in_bot}</b> пользователей · на факультете {students} студентов\n🌐 Сайт: {site}",
    },
    "survey_open": {
        "uz": "📝 <b>{title}</b>\n🟢 Ochiq · {left}\n\n👥 Ishtirok: <b>{participants}</b> kishi ({pct}%)\n"
              "✅ Hammasini baholagan: <b>{completed}</b>\n⭐ Baholar: <b>{evaluations}</b> · bugun <b>+{today}</b>\n"
              "📊 O‘rtacha ball: <b>{overall}</b> / 10\n💬 Izohlar: <b>{comments}</b>",
        "en": "📝 <b>{title}</b>\n🟢 Open · {left}\n\n👥 Took part: <b>{participants}</b> people ({pct}%)\n"
              "✅ Rated everyone: <b>{completed}</b>\n⭐ Ratings: <b>{evaluations}</b> · today <b>+{today}</b>\n"
              "📊 Average: <b>{overall}</b> / 10\n💬 Comments: <b>{comments}</b>",
        "ru": "📝 <b>{title}</b>\n🟢 Открыт · {left}\n\n👥 Участвуют: <b>{participants}</b> человек ({pct}%)\n"
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
    "btn_notify_on": {"uz": "🔔 Server xabarlari: yoqiq", "en": "🔔 Server messages: on",
                      "ru": "🔔 Сообщения сервера: вкл"},
    "btn_notify_off": {"uz": "🔕 Server xabarlari: o‘chiq", "en": "🔕 Server messages: off",
                       "ru": "🔕 Сообщения сервера: выкл"},
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
        "uz": "✅ Yangi manzil so‘raldi. 1–2 daqiqada tayyor bo‘ladi — «🔗 Sayt manzili» da ko‘rinadi "
              "(server xabarlari yoqiq bo‘lsa, shu yerga ham keladi).",
        "en": "✅ A new address was requested. It’s ready in 1–2 minutes — see «🔗 Site address» "
              "(with server messages on, it also comes here).",
        "ru": "✅ Новый адрес запрошен. Будет готов через 1–2 минуты — см. «🔗 Адрес сайта» "
              "(если сообщения сервера включены, он придёт и сюда).",
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
              "username o‘zgarsa ham). Server ishga tushganda xabar olishni xohlasangiz, «🔕 Server xabarlari» ni "
              "yoqing.",
        "en": "✅ <b>Linked!</b> The bot knows you as the <b>{username}</b> dashboard account (by your Telegram ID — "
              "even if your username changes). To hear when the server starts, turn on «🔕 Server messages».",
        "ru": "✅ <b>Привязано!</b> Бот узнаёт вас как аккаунт <b>{username}</b> (по Telegram ID — даже если username "
              "сменится). Чтобы получать сообщения о запуске сервера, включите «🔕 Сообщения сервера».",
    },
    "link_bad": {
        "uz": "⚠️ Bu havola eskirgan yoki noto‘g‘ri. Admin saytda «Mening hisobim › Telegram» dan yangisini oling.",
        "en": "⚠️ This link has expired or is wrong. Get a new one in the dashboard: «My account › Telegram».",
        "ru": "⚠️ Ссылка устарела или неверна. Получите новую на админ-сайте: «Мой аккаунт › Telegram».",
    },
    "notify_on": {"uz": "🔔 Server ishga tushganda va manzil o‘zgarganda holatini yuboraman",
                  "en": "🔔 I’ll send the status when the server starts or the address changes",
                  "ru": "🔔 Пришлю состояние, когда сервер запустится или адрес изменится"},
    "notify_off": {"uz": "🔕 Server xabarlari o‘chirildi", "en": "🔕 Server messages are off",
                   "ru": "🔕 Сообщения сервера выключены"},
    # Server status messages (app.bot.server_alerts): one message, kept up to date until everything works.
    "alert_started": {"uz": "🖥 <b>Server ishga tushdi</b> · {at}", "en": "🖥 <b>The server started</b> · {at}",
                      "ru": "🖥 <b>Сервер запущен</b> · {at}"},
    "alert_address": {"uz": "🔁 <b>Sayt manzili yangilandi</b> · {at}", "en": "🔁 <b>The site address changed</b> · {at}",
                      "ru": "🔁 <b>Адрес сайта изменился</b> · {at}"},
    "alert_bot": {"uz": "🤖 Bot: 🟢 ishlayapti", "en": "🤖 Bot: 🟢 working", "ru": "🤖 Бот: 🟢 работает"},
    "alert_web_ok": {"uz": "🖥 Veb-server: 🟢 ishlayapti", "en": "🖥 Web server: 🟢 working",
                     "ru": "🖥 Веб-сервер: 🟢 работает"},
    "alert_web_down": {"uz": "🖥 Veb-server: 🔴 to‘xtagan — qayta ishga tushirilmoqda",
                       "en": "🖥 Web server: 🔴 stopped — restarting", "ru": "🖥 Веб-сервер: 🔴 остановлен — перезапуск"},
    "alert_site": {"uz": "🌐 Sayt: {state}", "en": "🌐 Site: {state}", "ru": "🌐 Сайт: {state}"},
    "alert_site_ok": {"uz": "🟢 internetda ochiladi", "en": "🟢 opens on the internet", "ru": "🟢 открывается в интернете"},
    "alert_site_starting": {"uz": "🟡 manzil olinmoqda…", "en": "🟡 getting an address…", "ru": "🟡 получаем адрес…"},
    "alert_site_down": {"uz": "🔴 hali javob bermayapti", "en": "🔴 not answering yet", "ru": "🔴 пока не отвечает"},
    "alert_survey_open": {"uz": "📝 So‘rovnoma: 🟢 ochiq — «{title}», {closes} gacha",
                          "en": "📝 Survey: 🟢 open — «{title}», until {closes}",
                          "ru": "📝 Опрос: 🟢 открыт — «{title}», до {closes}"},
    "alert_survey_none": {"uz": "📝 So‘rovnoma: ⚪ hozir ochiq so‘rovnoma yo‘q", "en": "📝 Survey: ⚪ none is open now",
                          "ru": "📝 Опрос: ⚪ сейчас нет открытого"},
    "alert_admin_online": {"uz": "📊 Admin sayt: internetda ham ochiq", "en": "📊 Dashboard: open on the internet too",
                           "ru": "📊 Админ-сайт: открыт и в интернете"},
    "alert_admin_local": {"uz": "📊 Admin sayt: faqat server kompyuterida — http://127.0.0.1:{port}/admin",
                          "en": "📊 Dashboard: only on the server computer — http://127.0.0.1:{port}/admin",
                          "ru": "📊 Админ-сайт: только на компьютере-сервере — http://127.0.0.1:{port}/admin"},
    "alert_all_ok": {"uz": "✅ <b>Hammasi ishlayapti</b> · {time}", "en": "✅ <b>Everything works</b> · {time}",
                     "ru": "✅ <b>Всё работает</b> · {time}"},
    "alert_watching": {"uz": "⏳ Kuzatyapman — o‘zgarsa, shu xabar yangilanadi · {time}",
                       "en": "⏳ Watching — this message updates as things change · {time}",
                       "ru": "⏳ Слежу — это сообщение обновится · {time}"},
    "alert_gave_up": {"uz": "⚠️ {n} daqiqadan beri sayt ochilmayapti — server kompyuterini tekshiring.",
                      "en": "⚠️ The site hasn’t opened for {n} minutes — please check the server computer.",
                      "ru": "⚠️ Сайт не открывается уже {n} минут — проверьте компьютер-сервер."},
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
