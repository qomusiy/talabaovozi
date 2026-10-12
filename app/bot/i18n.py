"""Bot texts in Uzbek (default), English, Russian and Turkmen.

To fix a translation, edit the text here - nothing else needs to change.
Texts use Telegram HTML: <b>bold</b>, <i>italic</i>, <code>code</code>.
"""
DEFAULT_LANG = "uz"

LANGUAGE_NAMES = {
    "uz": "🇺🇿 O‘zbekcha",
    "en": "🇬🇧 English",
    "ru": "🇷🇺 Русский",
    "tk": "🇹🇲 Türkmençe",
}

TEXTS: dict[str, dict[str, str]] = {
    # ---------- Language ----------
    "choose_language": {
        "uz": "🌐 Tilni tanlang:",
        "en": "🌐 Choose your language:",
        "ru": "🌐 Выберите язык:",
        "tk": "🌐 Dili saýlaň:",
    },
    "language_set": {
        "uz": "✅ Til o‘zgartirildi: O‘zbekcha",
        "en": "✅ Language changed: English",
        "ru": "✅ Язык изменён: Русский",
        "tk": "✅ Dil üýtgedildi: Türkmençe",
    },

    # ---------- First visit: language, what the bot is, picking a group ----------
    "pick_language": {lang: "🌐 <b>Tilni tanlang</b> · Choose your language · Выберите язык · Dili saýlaň"
                      for lang in ("uz", "en", "ru", "tk")},
    "intro": {
        "uz": "👋 <b>Assalomu alaykum!</b>\n\n"
              "🎓 <b>Talaba Ovozi</b> — TIQXMMI Milliy tadqiqot universiteti talabalarining ta’lim sifatini anonim "
              "baholash tizimi.\n\n"
              "📝 <b>Qanday ishlaydi?</b> So‘rovnoma ochilganda, o‘qituvchilaringizni 3 ta mezon bo‘yicha 1 dan 10 "
              "gacha baholaysiz. Xohlasangiz, izoh ham qoldirishingiz mumkin.\n\n"
              "👤 Sizdan xolis va samimiy bo‘lishingizni so‘raymiz. Sizning fikr-mulohazalaringiz ta’limdagi "
              "kamchiliklarni aniqlash, ularni bartaraf etish va ta’lim sifatini yanada yaxshilashga yordam berishi "
              "mumkin.\n\n"
              "🔒 <b>Anonimlik.</b> So‘rovnomada ishtirok etayotgan talabalardan shaxsiy ma’lumotlar so‘ralmaydi, "
              "o‘qituvchilar va rahbariyat esa baholarni anonim ko‘radi.\n\n"
              "👥 <b>Guruh bo‘yicha filtrlang</b> — shunda so‘rovnomada faqat sizga kerakli o‘qituvchilar ko‘rsatiladi.",
        "en": "👋 <b>Hello!</b>\n\n"
              "🎓 <b>Talaba Ovozi</b> is the system where students of TIIAME National Research University evaluate "
              "the quality of their education anonymously.\n\n"
              "📝 <b>How does it work?</b> When a survey opens, you rate your teachers from 1 to 10 on 3 criteria. "
              "If you like, you can also leave a comment.\n\n"
              "👤 Please be fair and honest. Your feedback can help find what is missing in teaching, fix it and make "
              "education even better.\n\n"
              "🔒 <b>Anonymity.</b> Students taking part are not asked for any personal details, and teachers and "
              "management see the ratings anonymously.\n\n"
              "👥 <b>Filter by group</b> — then the survey shows only the teachers you need.",
        "ru": "👋 <b>Здравствуйте!</b>\n\n"
              "🎓 <b>Talaba Ovozi</b> — система анонимной оценки качества образования студентами Национального "
              "исследовательского университета «ТИИИМСХ».\n\n"
              "📝 <b>Как это работает?</b> Когда открывается опрос, вы оцениваете своих преподавателей по 3 критериям "
              "от 1 до 10. При желании можно оставить и комментарий.\n\n"
              "👤 Просим вас быть объективными и искренними. Ваши отзывы помогут выявить недостатки в обучении, "
              "устранить их и сделать образование ещё лучше.\n\n"
              "🔒 <b>Анонимность.</b> У участников опроса не запрашиваются личные данные, а преподаватели и "
              "руководство видят оценки анонимно.\n\n"
              "👥 <b>Выберите группу</b> — тогда в опросе будут только нужные вам преподаватели.",
        "tk": "👋 <b>Salam!</b>\n\n"
              "🎓 <b>Talaba Ovozi</b> — TIQXMMI Milli barlag uniwersitetiniň talyplarynyň bilim hiline anonim baha "
              "bermek ulgamy.\n\n"
              "📝 <b>Nähili işleýär?</b> Soragnama açylanda, mugallymlaryňyza 3 ölçeg boýunça 1-den 10-a çenli baha "
              "berýärsiňiz. Isleseňiz, teswir hem ýazyp bilersiňiz.\n\n"
              "👤 Sizden adalatly we ak ýürekden bolmagyňyzy haýyş edýäris. Siziň pikirleriňiz bilimdäki "
              "kemçilikleri ýüze çykarmaga, olary düzetmäge we bilim hilini has-da gowulandyrmaga kömek edip biler.\n\n"
              "🔒 <b>Anonimlik.</b> Soragnama gatnaşýan talyplardan şahsy maglumatlar soralmaýar, mugallymlar we "
              "ýolbaşçylar bahalary anonim görýär.\n\n"
              "👥 <b>Topar boýunça süzüň</b> — şonda soragnamada diňe size gerek mugallymlar görkeziler.",
    },
    "btn_pick_group": {"uz": "👥 Guruhni tanlash", "en": "👥 Choose group", "ru": "👥 Выбрать группу",
                       "tk": "👥 Topary saýlamak"},
    "pick_course": {
        "uz": "👥 <b>Guruhingizni tanlang</b>\n\n<b>1/3</b> · Nechanchi kursda o‘qiysiz?",
        "en": "👥 <b>Choose your group</b>\n\n<b>1/3</b> · Which year are you in?",
        "ru": "👥 <b>Выберите группу</b>\n\n<b>1/3</b> · На каком вы курсе?",
        "tk": "👥 <b>Toparyňyzy saýlaň</b>\n\n<b>1/3</b> · Näçenji kursda okaýarsyňyz?",
    },
    "pick_specialty": {
        "uz": "👥 <b>{course}</b>\n\n<b>2/3</b> · Yo‘nalishingizni tanlang:",
        "en": "👥 <b>{course}</b>\n\n<b>2/3</b> · Choose your programme:",
        "ru": "👥 <b>{course}</b>\n\n<b>2/3</b> · Выберите направление:",
        "tk": "👥 <b>{course}</b>\n\n<b>2/3</b> · Ugruňyzy saýlaň:",
    },
    "pick_group": {
        "uz": "👥 <b>{course} · {specialty}</b>\n\n<b>3/3</b> · Guruhingizni tanlang:",
        "en": "👥 <b>{course} · {specialty}</b>\n\n<b>3/3</b> · Choose your group:",
        "ru": "👥 <b>{course} · {specialty}</b>\n\n<b>3/3</b> · Выберите группу:",
        "tk": "👥 <b>{course} · {specialty}</b>\n\n<b>3/3</b> · Toparyňyzy saýlaň:",
    },
    "no_groups": {
        "uz": "😕 Hozircha tanlash uchun guruhlar yo‘q. Birozdan so‘ng qayta urinib ko‘ring.",
        "en": "😕 There are no groups to choose from yet. Please try again a little later.",
        "ru": "😕 Пока нет групп для выбора. Попробуйте чуть позже.",
        "tk": "😕 Häzirlikçe saýlamak üçin topar ýok. Biraz soňrak synanyşyň.",
    },
    "course_n": {"uz": "{n}-kurs", "en": "Year {n}", "ru": "{n} курс", "tk": "{n}-nji kurs"},
    # A group by the number students know it by (Group.number), e.g. "302-guruh".
    "group_n": {"uz": "{n}-guruh", "en": "Group {n}", "ru": "Группа {n}", "tk": "Topar {n}"},
    "group_set": {"uz": "✅ Guruh: {group}", "en": "✅ Group: {group}", "ru": "✅ Группа: {group}",
                  "tk": "✅ Topar: {group}"},
    "no_group": {"uz": "Guruh tanlanmagan", "en": "No group chosen", "ru": "Группа не выбрана",
                 "tk": "Topar saýlanmady"},
    "btn_change_group": {"uz": "🔄 Guruhni o‘zgartirish", "en": "🔄 Change group", "ru": "🔄 Сменить группу",
                         "tk": "🔄 Topary üýtgetmek"},

    # ---------- Moderation (the dashboard's Foydalanuvchilar page, and the flood guard) ----------
    "restricted_blocked": {
        "uz": "⛔ Siz botdan foydalana olmaysiz. Xato deb hisoblasangiz: {support}",
        "en": "⛔ You can’t use this bot. If you think this is a mistake: {support}",
        "ru": "⛔ Вы не можете пользоваться ботом. Если это ошибка: {support}",
        "tk": "⛔ Siz botdan peýdalanyp bilmeýärsiňiz. Ýalňyşlyk diýip pikir etseňiz: {support}",
    },
    "restricted_suspended": {
        "uz": "⏸ Bot sizga {until} gacha javob bermaydi. Savollar bo‘lsa: {support}",
        "en": "⏸ The bot won’t answer you until {until}. Questions: {support}",
        "ru": "⏸ Бот не будет отвечать вам до {until}. Вопросы: {support}",
        "tk": "⏸ Bot size {until} çenli jogap bermez. Soraglar: {support}",
    },
    "flood_stopped": {
        "uz": "⏸ Juda ko‘p xabar yuboryapsiz. Bot 10 daqiqa javob bermaydi — keyin davom etishingiz mumkin.",
        "en": "⏸ You’re sending too many messages. The bot will pause for 10 minutes — then you can go on.",
        "ru": "⏸ Слишком много сообщений. Бот не будет отвечать 10 минут — потом можно продолжить.",
        "tk": "⏸ Gaty köp habar iberýärsiňiz. Bot 10 minut jogap bermez — soňra dowam edip bilersiňiz.",
    },

    # ---------- Main menu ----------
    "btn_teachers": {"uz": "👨‍🏫 O‘qituvchilarim", "en": "👨‍🏫 My teachers", "ru": "👨‍🏫 Мои преподаватели",
                     "tk": "👨‍🏫 Mugallymlarym"},
    "btn_language": {"uz": "🌐 Til", "en": "🌐 Language", "ru": "🌐 Язык", "tk": "🌐 Dil"},
    "btn_help": {"uz": "❓ Yordam", "en": "❓ Help", "ru": "❓ Помощь", "tk": "❓ Kömek"},
    "btn_timetable": {"uz": "📅 Dars jadvali", "en": "📅 Timetable", "ru": "📅 Расписание", "tk": "📅 Sapak tertibi"},
    "btn_channel": {"uz": "📢 Fakultet kanali", "en": "📢 Faculty channel", "ru": "📢 Канал факультета",
                    "tk": "📢 Fakultetiň kanaly"},

    # ---------- Timetable (a picture of the group's week) ----------
    "tt_loading": {"uz": "⏳ Jadval tayyorlanmoqda…", "en": "⏳ Preparing your timetable…",
                   "ru": "⏳ Готовим расписание…", "tk": "⏳ Tertip taýýarlanýar…"},
    "tt_none": {
        "uz": "📅 Guruhingizning dars jadvali hali yuklanmagan. Keyinroq urinib ko‘ring.",
        "en": "📅 Your group’s timetable isn’t available yet. Please try again later.",
        "ru": "📅 Расписание вашей группы ещё не загружено. Попробуйте позже.",
        "tk": "📅 Toparyňyzyň sapak tertibi entek ýüklenmedi. Soňrak synanyşyň.",
    },
    "tt_need_group": {
        "uz": "📅 Dars jadvalini ko‘rish uchun avval guruhingizni tanlang.",
        "en": "📅 Pick your group first to see its timetable.",
        "ru": "📅 Чтобы увидеть расписание, сначала выберите группу.",
        "tk": "📅 Sapak tertibini görmek üçin ilki toparyňyzy saýlaň.",
    },
    "tt_caption": {
        "uz": "📅 <b>{group} — haftalik dars jadvali</b>\n\nEduPage veb-saytidagi {date} holatiga ko‘ra.",
        "en": "📅 <b>{group} — weekly timetable</b>\n\nFrom the EduPage website, as of {date}.",
        "ru": "📅 <b>{group} — расписание на неделю</b>\n\nПо данным сайта EduPage на {date}.",
        "tk": "📅 <b>{group} — hepdelik sapak tertibi</b>\n\nEduPage saýtyndaky {date} ýagdaýyna görä.",
    },
    "tt_title": {"uz": "Dars jadvali", "en": "Timetable", "ru": "Расписание", "tk": "Sapak tertibi"},
    "tt_count": {"uz": "{n} ta dars", "en": "{n} classes", "ru": "занятий: {n}", "tk": "{n} sapak"},
    "tt_lunch": {"uz": "Tushlik", "en": "Lunch", "ru": "Обед", "tk": "Günortanlyk"},
    "tt_week_A": {"uz": "A hafta", "en": "Week A", "ru": "Неделя A", "tk": "A hepde"},
    "tt_week_B": {"uz": "B hafta", "en": "Week B", "ru": "Неделя B", "tk": "B hepde"},
    "tt_room": {"uz": "Xona", "en": "Room", "ru": "Ауд.", "tk": "Otag"},
    "tt_course": {"uz": "{n}-kurs", "en": "Year {n}", "ru": "{n} курс", "tk": "{n}-nji kurs"},
    "tt_footer": {"uz": "Talaba Ovozi · EduPage, {date} holatiga", "en": "Talaba Ovozi · from EduPage, as of {date}",
                  "ru": "Talaba Ovozi · EduPage, на {date}", "tk": "Talaba Ovozi · EduPage, {date} ýagdaýyna görä"},

    # ---------- Home card (one message with buttons; sections open in the same message) ----------
    "home": {lang: "{greeting}\n\n🎓 {group}\n\n{status}" for lang in ("uz", "en", "ru", "tk")},
    "greet_morning": {"uz": "👋 Xayrli tong!", "en": "👋 Good morning!", "ru": "👋 Доброе утро!",
                      "tk": "👋 Ertiriňiz haýyrly bolsun!"},
    "greet_day": {"uz": "👋 Xayrli kun!", "en": "👋 Good afternoon!", "ru": "👋 Добрый день!",
                  "tk": "👋 Günüňiz haýyrly bolsun!"},
    "greet_evening": {"uz": "👋 Xayrli kech!", "en": "👋 Good evening!", "ru": "👋 Добрый вечер!",
                      "tk": "👋 Agşamyňyz haýyrly bolsun!"},
    "survey_open": {"uz": "📝 <b>So‘rovnoma</b> — Ochiq", "en": "📝 <b>Survey</b> — Open",
                    "ru": "📝 <b>Опрос</b> — Открыт", "tk": "📝 <b>Soragnama</b> — Açyk"},
    "survey_closed": {"uz": "📝 <b>So‘rovnoma</b> — Hozircha yopiq", "en": "📝 <b>Survey</b> — Closed for now",
                      "ru": "📝 <b>Опрос</b> — Пока закрыт", "tk": "📝 <b>Soragnama</b> — Häzirlikçe ýapyk"},
    "closes_in": {"uz": "⏳ Yopilishiga {n} kun qoldi.", "en": "⏳ Closes in {n} days.",
                  "ru": "⏳ До закрытия осталось дней: {n}.", "tk": "⏳ Ýapylmagyna {n} gün galdy."},
    "closes_today": {"uz": "⏳ Bugun yopiladi.", "en": "⏳ Closes today.", "ru": "⏳ Закрывается сегодня.",
                     "tk": "⏳ Şu gün ýapylýar."},
    "rated_n": {"uz": "✅ {done} / {total} ta o‘qituvchi baholandi.", "en": "✅ {done} / {total} teachers rated.",
                "ru": "✅ Оценено преподавателей: {done} / {total}.", "tk": "✅ {done} / {total} mugallyma baha berildi."},
    "cta_start": {"uz": "👇 Boshlash uchun tugmani bosing.", "en": "👇 Tap the button to start.",
                  "ru": "👇 Нажмите кнопку, чтобы начать.", "tk": "👇 Başlamak üçin düwmä basyň."},
    "cta_continue": {"uz": "👇 Davom ettirish uchun tugmani bosing.", "en": "👇 Tap the button to continue.",
                     "ru": "👇 Нажмите кнопку, чтобы продолжить.", "tk": "👇 Dowam etmek üçin düwmä basyň."},
    "cta_pick_group": {"uz": "👇 Boshlash uchun avval guruhingizni tanlang.", "en": "👇 Choose your group first to start.",
                       "ru": "👇 Чтобы начать, сначала выберите группу.", "tk": "👇 Başlamak üçin ilki toparyňyzy saýlaň."},
    "home_thanks": {
        "uz": "🎉 Rahmat! Fikringiz ta’lim sifatini oshirishga yordam beradi.",
        "en": "🎉 Thank you! Your feedback helps improve education.",
        "ru": "🎉 Спасибо! Ваше мнение помогает улучшить обучение.",
        "tk": "🎉 Sag boluň! Pikiriňiz bilim hilini gowulandyrmaga kömek edýär.",
    },
    "home_can_edit": {
        "uz": "✏️ Yopilguncha baholaringizni o‘zgartirishingiz mumkin.",
        "en": "✏️ You can change your ratings until it closes.",
        "ru": "✏️ До закрытия оценки можно изменить.",
        "tk": "✏️ Ýapylýança bahalaryňyzy üýtgedip bilersiňiz.",
    },
    "btn_back": {"uz": "⬅️ Orqaga", "en": "⬅️ Back", "ru": "⬅️ Назад", "tk": "⬅️ Yza"},
    "btn_review": {"uz": "✏️ Baholarimni ko‘rish", "en": "✏️ See my ratings", "ru": "✏️ Мои оценки",
                   "tk": "✏️ Bahalarymy görmek"},
    "teachers_page": {"uz": "📄 {page} / {pages}", "en": "📄 {page} / {pages}", "ru": "📄 {page} / {pages}",
                      "tk": "📄 {page} / {pages}"},
    "reminder_3": {
        "uz": "⏰ <b>{name}</b>, so‘rovnoma tugashiga <b>3 kun</b> qoldi!\n\n"
              "Siz hali barcha o‘qituvchilaringizni baholamadingiz. Bu 2–3 daqiqa oladi — fikringiz ta’lim "
              "sifatini oshirishga yordam beradi 💬\n\n👇 Tugmani bosing va davom eting",
        "en": "⏰ <b>{name}</b>, the survey ends in <b>3 days</b>!\n\n"
              "You haven’t rated all your teachers yet. It takes 2–3 minutes — and your opinion helps improve "
              "teaching 💬\n\n👇 Tap the button to continue",
        "ru": "⏰ <b>{name}</b>, до конца опроса <b>3 дня</b>!\n\n"
              "Вы ещё не оценили всех преподавателей. Это займёт 2–3 минуты — ваше мнение помогает улучшить "
              "обучение 💬\n\n👇 Нажмите кнопку и продолжите",
        "tk": "⏰ <b>{name}</b>, soragnamanyň gutarmagyna <b>3 gün</b> galdy!\n\n"
              "Siz entek ähli mugallymlaryňyza baha bermediňiz. Bu 2–3 minut alar — pikiriňiz bilim hilini "
              "gowulandyrmaga kömek edýär 💬\n\n👇 Düwmä basyň we dowam ediň",
    },
    "reminder_1": {
        "uz": "⏳ <b>{name}</b>, so‘rovnoma <b>ertaga yopiladi</b>!\n\n"
              "Hali baholanmagan o‘qituvchilaringiz bor. Ovozingiz muhim — bir necha daqiqa ajrating 🙏\n\n"
              "👇 Hoziroq tugatish uchun tugmani bosing",
        "en": "⏳ <b>{name}</b>, the survey <b>closes tomorrow</b>!\n\n"
              "Some of your teachers aren’t rated yet. Your voice matters — it only takes a few minutes 🙏\n\n"
              "👇 Tap the button to finish now",
        "ru": "⏳ <b>{name}</b>, опрос <b>закрывается завтра</b>!\n\n"
              "Ещё не все преподаватели оценены. Ваш голос важен — это займёт пару минут 🙏\n\n"
              "👇 Нажмите кнопку, чтобы закончить",
        "tk": "⏳ <b>{name}</b>, soragnama <b>ertir ýapylýar</b>!\n\n"
              "Heniz baha berilmedik mugallymlaryňyz bar. Sesiňiz möhüm — birnäçe minut sarp ediň 🙏\n\n"
              "👇 Häzir tamamlamak üçin düwmä basyň",
    },

    # ---------- Survey ----------
    "btn_open_survey": {"uz": "📝 Baholashni boshlash", "en": "📝 Start evaluating", "ru": "📝 Начать оценку",
                        "tk": "📝 Baha bermäge başlamak"},
    "survey_coming_soon": {
        "uz": "🛠 So‘rovnoma sahifasi tayyorlanmoqda.",
        "en": "🛠 The survey page is being prepared.",
        "ru": "🛠 Страница опроса готовится.",
        "tk": "🛠 Soragnama sahypasy taýýarlanýar.",
    },

    # ---------- Teachers ----------
    "teachers_header": {
        "uz": "👨‍🏫 <b>Sizning o‘qituvchilaringiz</b>\n<i>{semester}</i>",
        "en": "👨‍🏫 <b>Your teachers</b>\n<i>{semester}</i>",
        "ru": "👨‍🏫 <b>Ваши преподаватели</b>\n<i>{semester}</i>",
        "tk": "👨‍🏫 <b>Siziň mugallymlaryňyz</b>\n<i>{semester}</i>",
    },
    "no_teachers": {
        "uz": "📭 Guruhingiz uchun o‘qituvchilar hali biriktirilmagan.",
        "en": "📭 No teachers have been assigned to your group yet.",
        "ru": "📭 Преподаватели для вашей группы ещё не назначены.",
        "tk": "📭 Toparyňyz üçin entek mugallym bellenmedi.",
    },
    "room": {"uz": "Xona", "en": "Room", "ru": "Кабинет", "tk": "Otag"},
    "lesson_lecture": {"uz": "ma’ruza", "en": "lecture", "ru": "лекция", "tk": "leksiýa"},
    "lesson_practice": {"uz": "amaliy", "en": "practice", "ru": "практика", "tk": "amaly"},
    "lesson_lab": {"uz": "laboratoriya", "en": "lab", "ru": "лабораторная", "tk": "laboratoriýa"},
    "lesson_seminar": {"uz": "seminar", "en": "seminar", "ru": "семинар", "tk": "seminar"},
    "lesson_other": {"uz": "mashg‘ulot", "en": "class", "ru": "занятие", "tk": "sapak"},

    # ---------- Help ----------
    "help": {
        "uz": "❓ <b>Yordam</b>\n\n"
              "📝 <b>Baholash</b> — so‘rovnoma ochiq bo‘lganda o‘qituvchilaringizni 3 mezon bo‘yicha "
              "1 dan 10 gacha baholang:\n"
              "   • 🎓 O‘qitish sifati\n   • ⚖️ Adolatlilik va baholash\n   • 🤝 Kasbiy mahorat va talabalar bilan munosabat\n\n"
              "🔒 Baholar anonim — o‘qituvchilar va fakultet kim baho berganini ko‘rmaydi.\n\n"
              "👨‍🏫 <b>O‘qituvchilarim</b> — guruhingizga dars beradigan o‘qituvchilar\n"
              "📅 <b>Dars jadvali</b> — guruhingizning haftalik jadvali, rasm ko‘rinishida\n"
              "🔄 <b>Guruhni o‘zgartirish</b> — boshqa guruhni tanlash\n"
              "🌐 <b>Til</b> — interfeys tilini o‘zgartirish\n\n"
              "💬 Savollar bo‘yicha: {support}\n🛠 Texnik muammolar: {tech}",
        "en": "❓ <b>Help</b>\n\n"
              "📝 <b>Evaluate</b> — while a survey is open, rate each of your teachers from 1 to 10 on 3 criteria:\n"
              "   • 🎓 Teaching\n   • ⚖️ Fairness\n   • 🤝 Professionalism\n\n"
              "🔒 Ratings are anonymous — teachers and the faculty don’t see who rated.\n\n"
              "👨‍🏫 <b>My teachers</b> — the teachers of your group\n"
              "📅 <b>Timetable</b> — your group’s week as a picture\n"
              "🔄 <b>Change group</b> — choose another group\n"
              "🌐 <b>Language</b> — change the interface language\n\n"
              "💬 Questions: {support}\n🛠 Technical issues: {tech}",
        "ru": "❓ <b>Помощь</b>\n\n"
              "📝 <b>Оценить</b> — пока опрос открыт, оцените каждого преподавателя от 1 до 10 по 3 критериям:\n"
              "   • 🎓 Качество преподавания\n   • ⚖️ Справедливость и оценивание\n   • 🤝 Профессионализм и отношение к студентам\n\n"
              "🔒 Оценки анонимны — преподаватели и факультет не видят, кто их поставил.\n\n"
              "👨‍🏫 <b>Мои преподаватели</b> — кто ведёт занятия у вашей группы\n"
              "📅 <b>Расписание</b> — неделя вашей группы картинкой\n"
              "🔄 <b>Сменить группу</b> — выбрать другую группу\n"
              "🌐 <b>Язык</b> — сменить язык интерфейса\n\n"
              "💬 По вопросам: {support}\n🛠 Технические проблемы: {tech}",
        "tk": "❓ <b>Kömek</b>\n\n"
              "📝 <b>Baha bermek</b> — soragnama açyk wagty mugallymlaryňyza 3 ölçeg boýunça "
              "1-den 10-a çenli baha beriň:\n"
              "   • 🎓 Okatmagyň hili\n   • ⚖️ Adalatlylyk we bahalandyryş\n   • 🤝 Hünär ussatlygy we talyplar bilen gatnaşyk\n\n"
              "🔒 Bahalar anonim — mugallymlar we fakultet kimiň baha berendigini görmeýär.\n\n"
              "👨‍🏫 <b>Mugallymlarym</b> — toparyňyza sapak berýän mugallymlar\n"
              "📅 <b>Sapak tertibi</b> — toparyňyzyň hepdesi surat görnüşinde\n"
              "🔄 <b>Topary üýtgetmek</b> — başga topar saýlamak\n"
              "🌐 <b>Dil</b> — interfeýsiň dilini üýtgetmek\n\n"
              "💬 Soraglar boýunça: {support}\n🛠 Tehniki meseleler: {tech}",
    },

    "cmd_start": {"uz": "Boshlash / asosiy menyu", "en": "Start / main menu", "ru": "Начать / главное меню",
                  "tk": "Başlamak / esasy menýu"},
    "cmd_language": {"uz": "Tilni o‘zgartirish", "en": "Change language", "ru": "Сменить язык", "tk": "Dili üýtgetmek"},
    "cmd_help": {"uz": "Yordam", "en": "Help", "ru": "Помощь", "tk": "Kömek"},

    # ---------- Commands ----------
    "my_id": {
        "uz": "🆔 Telegram ID raqamingiz: <code>{id}</code>",
        "en": "🆔 Your Telegram ID: <code>{id}</code>",
        "ru": "🆔 Ваш Telegram ID: <code>{id}</code>",
        "tk": "🆔 Telegram ID belgiňiz: <code>{id}</code>",
    },
    "no_teachers_in_survey": {
        "uz": "😕 Guruhingiz uchun o‘qituvchilar ro‘yxati hali tayyor emas. Iltimos, {support} ga yozing.",
        "en": "😕 The teacher list for your group isn't ready yet. Please write to {support}.",
        "ru": "😕 Список преподавателей вашей группы ещё не готов. Напишите, пожалуйста, {support}.",
        "tk": "😕 Toparyňyz üçin mugallymlaryň sanawy entek taýýar däl. Haýyş, {support} ýazyň.",
    },
}


# The bot's Telegram profile, the same for every Telegram language (app.bot.__main__.setup_bot_profile):
# the name in chats, the short description on its profile page, and "What can this bot do?" before /start.
BOT_NAME = "🎓 Talaba Ovozi (Anonim Soʻrovnoma)"
BOT_SHORT_DESCRIPTION = "Ta’lim sifatini baholash, izoh qoldirish va tekshirish tizimi"
BOT_DESCRIPTION = ("🎓 Talaba Ovozi — TIQXMMI Milliy tadqiqot universiteti talabalarining ta’lim sifatini anonim "
                   "baholash tizimi")


# Weekdays, Monday first (the timetable's day numbers).
DAY_NAMES = {
    "uz": ("Dushanba", "Seshanba", "Chorshanba", "Payshanba", "Juma", "Shanba", "Yakshanba"),
    "en": ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"),
    "ru": ("Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"),
    "tk": ("Duşenbe", "Sişenbe", "Çarşenbe", "Penşenbe", "Anna", "Şenbe", "Ýekşenbe"),
}


def t(lang: str | None, key: str, **kwargs) -> str:
    entry = TEXTS[key]
    text = entry.get(lang or DEFAULT_LANG) or entry[DEFAULT_LANG]
    return text.format(**kwargs) if kwargs else text


def all_variants(key: str) -> set[str]:
    """Every translation of a button label, so a menu tap is recognised in any language."""
    return set(TEXTS[key].values())
