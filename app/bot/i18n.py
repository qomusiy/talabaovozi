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

    # ---------- Welcome & login ----------
    "welcome": {
        "uz": "👋 <b>Assalomu alaykum!</b>\n\n"
              "<b>Talaba Ovozi</b> — Iqtisodiyot fakulteti talabalari o‘qituvchilarini baholaydigan platforma.\n\n"
              "📝 Sizga dars beradigan o‘qituvchilarni baholang\n"
              "💬 Fikr va takliflaringizni yozing\n"
              "📈 Ta’lim sifatini birgalikda oshiraylik\n\n"
              "Boshlash uchun tizimga kiring 👇",
        "en": "👋 <b>Hello!</b>\n\n"
              "<b>Talaba Ovozi</b> (Student Voice) is where Economics Faculty students evaluate their teachers.\n\n"
              "📝 Rate the teachers who teach you\n"
              "💬 Share your comments and suggestions\n"
              "📈 Help improve the quality of teaching\n\n"
              "Log in to get started 👇",
        "ru": "👋 <b>Здравствуйте!</b>\n\n"
              "<b>Talaba Ovozi</b> (Голос студента) — платформа, где студенты экономического факультета "
              "оценивают своих преподавателей.\n\n"
              "📝 Оцените преподавателей, которые у вас ведут занятия\n"
              "💬 Поделитесь мнением и предложениями\n"
              "📈 Помогите улучшить качество обучения\n\n"
              "Чтобы начать, войдите в систему 👇",
        "tk": "👋 <b>Salam!</b>\n\n"
              "<b>Talaba Ovozi</b> (Talyp sesi) — Ykdysadyýet fakultetiniň talyplarynyň mugallymlaryna baha "
              "berýän platformasy.\n\n"
              "📝 Size sapak berýän mugallymlara baha beriň\n"
              "💬 Pikirleriňizi we teklipleriňizi ýazyň\n"
              "📈 Bilim hilini bilelikde gowulandyralyň\n\n"
              "Başlamak üçin ulgama giriň 👇",
    },
    "btn_login": {"uz": "🔐 Kirish", "en": "🔐 Log in", "ru": "🔐 Войти", "tk": "🔐 Girmek"},
    "btn_cancel": {"uz": "❌ Bekor qilish", "en": "❌ Cancel", "ru": "❌ Отмена", "tk": "❌ Ýatyrmak"},
    "btn_retry": {"uz": "🔄 Qayta urinish", "en": "🔄 Try again", "ru": "🔄 Попробовать снова",
                  "tk": "🔄 Täzeden synanyşmak"},
    "ask_hemis": {
        "uz": "<b>1/2</b> 🆔 HEMIS login raqamingizni yuboring.\n\n<i>Masalan:</i> <code>368211100123</code>",
        "en": "<b>1/2</b> 🆔 Send your HEMIS login number.\n\n<i>Example:</i> <code>368211100123</code>",
        "ru": "<b>1/2</b> 🆔 Отправьте ваш логин HEMIS.\n\n<i>Например:</i> <code>368211100123</code>",
        "tk": "<b>1/2</b> 🆔 HEMIS login belgiňizi iberiň.\n\n<i>Mysal üçin:</i> <code>368211100123</code>",
    },
    "bad_hemis": {
        "uz": "⚠️ HEMIS raqami faqat raqamlardan iborat bo‘lishi kerak. Qaytadan yuboring:",
        "en": "⚠️ The HEMIS number should contain digits only. Please send it again:",
        "ru": "⚠️ Номер HEMIS должен состоять только из цифр. Отправьте ещё раз:",
        "tk": "⚠️ HEMIS belgisi diňe sanlardan ybarat bolmaly. Täzeden iberiň:",
    },
    "ask_passport": {
        "uz": "<b>2/2</b> 🪪 Pasport seriyasi va raqamini yuboring.\n\n<i>Masalan:</i> <code>AS3480990</code>\n\n"
              "🔒 Xavfsizlik uchun xabaringiz darhol o‘chiriladi.",
        "en": "<b>2/2</b> 🪪 Send your passport series and number.\n\n<i>Example:</i> <code>AS3480990</code>\n\n"
              "🔒 For your security, the message will be deleted right away.",
        "ru": "<b>2/2</b> 🪪 Отправьте серию и номер паспорта.\n\n<i>Например:</i> <code>AS3480990</code>\n\n"
              "🔒 В целях безопасности сообщение будет сразу удалено.",
        "tk": "<b>2/2</b> 🪪 Pasportyňyzyň seriýasyny we belgisini iberiň.\n\n<i>Mysal üçin:</i> "
              "<code>AS3480990</code>\n\n🔒 Howpsuzlyk üçin habaryňyz derrew öçüriler.",
    },
    "bad_passport": {
        "uz": "⚠️ Format noto‘g‘ri. 2 ta harf va 7 ta raqam bo‘lishi kerak, masalan <code>AS3480990</code>:",
        "en": "⚠️ Wrong format. It should be 2 letters and 7 digits, e.g. <code>AS3480990</code>:",
        "ru": "⚠️ Неверный формат. Нужно 2 буквы и 7 цифр, например <code>AS3480990</code>:",
        "tk": "⚠️ Nädogry format. 2 harp we 7 san bolmaly, mysal üçin <code>AS3480990</code>:",
    },
    "login_failed": {
        "uz": "❌ <b>Ma’lumotlar topilmadi.</b>\n\nHEMIS raqami yoki pasport ma’lumotlari noto‘g‘ri, "
              "yoki siz Iqtisodiyot fakulteti talabalari ro‘yxatida yo‘qsiz.\n\n"
              "Tekshirib, qaytadan urinib ko‘ring. Muammo davom etsa: {support}",
        "en": "❌ <b>No match found.</b>\n\nThe HEMIS number or passport details are incorrect, "
              "or you are not on the Economics Faculty student list.\n\n"
              "Please check and try again. If the problem persists: {support}",
        "ru": "❌ <b>Данные не найдены.</b>\n\nНеверный номер HEMIS или паспортные данные, "
              "либо вас нет в списке студентов экономического факультета.\n\n"
              "Проверьте и попробуйте снова. Если проблема не решится: {support}",
        "tk": "❌ <b>Maglumat tapylmady.</b>\n\nHEMIS belgisi ýa-da pasport maglumatlary nädogry, "
              "ýa-da siz Ykdysadyýet fakultetiniň talyplarynyň sanawynda ýok.\n\n"
              "Barlap, täzeden synanyşyň. Mesele dowam etse: {support}",
    },
    "linked_elsewhere": {
        "uz": "⛔ Bu talaba boshqa Telegram akkaunt orqali allaqachon ro‘yxatdan o‘tgan.\n\n"
              "Agar bu siz bo‘lsangiz, administratorga murojaat qiling: {support}",
        "en": "⛔ This student is already registered from another Telegram account.\n\n"
              "If this is you, please contact the administrator: {support}",
        "ru": "⛔ Этот студент уже зарегистрирован с другого аккаунта Telegram.\n\n"
              "Если это вы, обратитесь к администратору: {support}",
        "tk": "⛔ Bu talyp başga Telegram hasaby arkaly eýýäm hasaba alnan.\n\n"
              "Eger bu siz bolsaňyz, administratora ýüz tutuň: {support}",
    },
    "login_success": {
        "uz": "✅ <b>Xush kelibsiz, {name}!</b>\n\n👥 Guruh: <b>{group}</b>\n\n"
              "So‘rovnoma boshlanganda sizga xabar beramiz 🔔",
        "en": "✅ <b>Welcome, {name}!</b>\n\n👥 Group: <b>{group}</b>\n\n"
              "We’ll notify you when a survey starts 🔔",
        "ru": "✅ <b>Добро пожаловать, {name}!</b>\n\n👥 Группа: <b>{group}</b>\n\n"
              "Мы сообщим вам, когда начнётся опрос 🔔",
        "tk": "✅ <b>Hoş geldiňiz, {name}!</b>\n\n👥 Topar: <b>{group}</b>\n\n"
              "Soragnama başlanda size habar bereris 🔔",
    },
    "cancelled": {
        "uz": "Bekor qilindi. Kirish uchun /start ni bosing.",
        "en": "Cancelled. Press /start to log in.",
        "ru": "Отменено. Нажмите /start, чтобы войти.",
        "tk": "Ýatyryldy. Girmek üçin /start basyň.",
    },
    "need_login": {
        "uz": "🔐 Avval tizimga kiring: /start",
        "en": "🔐 Please log in first: /start",
        "ru": "🔐 Сначала войдите в систему: /start",
        "tk": "🔐 Ilki ulgama giriň: /start",
    },

    # ---------- Main menu ----------
    "btn_survey": {"uz": "📝 Baholash", "en": "📝 Evaluate", "ru": "📝 Оценить", "tk": "📝 Baha bermek"},
    "btn_teachers": {"uz": "👨‍🏫 O‘qituvchilarim", "en": "👨‍🏫 My teachers", "ru": "👨‍🏫 Мои преподаватели",
                     "tk": "👨‍🏫 Mugallymlarym"},
    "btn_profile": {"uz": "👤 Profil", "en": "👤 Profile", "ru": "👤 Профиль", "tk": "👤 Profil"},
    "btn_language": {"uz": "🌐 Til", "en": "🌐 Language", "ru": "🌐 Язык", "tk": "🌐 Dil"},
    "btn_help": {"uz": "❓ Yordam", "en": "❓ Help", "ru": "❓ Помощь", "tk": "❓ Kömek"},
    "btn_timetable": {"uz": "📅 Dars jadvali", "en": "📅 Timetable", "ru": "📅 Расписание", "tk": "📅 Sapak tertibi"},
    "btn_channel": {"uz": "📢 Fakultet kanali", "en": "📢 Faculty channel", "ru": "📢 Канал факультета",
                    "tk": "📢 Fakultetiň kanaly"},

    # ---------- Log out (Profile) ----------
    "btn_logout": {"uz": "🚪 Hisobdan chiqish", "en": "🚪 Log out", "ru": "🚪 Выйти из аккаунта",
                   "tk": "🚪 Hasapdan çykmak"},
    "btn_logout_yes": {"uz": "✅ Ha, chiqish", "en": "✅ Yes, log out", "ru": "✅ Да, выйти", "tk": "✅ Hawa, çykmak"},
    "logout_confirm": {
        "uz": "🚪 <b>Hisobdan chiqasizmi?</b>\n\nQayta kirish uchun HEMIS raqamingiz va pasport ma’lumotlaringiz "
              "kerak bo‘ladi. Bergan baholaringiz saqlanib qoladi.",
        "en": "🚪 <b>Log out?</b>\n\nTo log in again you will need your HEMIS number and passport details. "
              "The ratings you gave are kept.",
        "ru": "🚪 <b>Выйти из аккаунта?</b>\n\nЧтобы войти снова, понадобятся номер HEMIS и паспортные данные. "
              "Ваши оценки сохранятся.",
        "tk": "🚪 <b>Hasapdan çykýarsyňyzmy?</b>\n\nTäzeden girmek üçin HEMIS belgiňiz we pasport maglumatlaryňyz "
              "gerek bolar. Beren bahalaryňyz saklanar.",
    },
    "logged_out": {
        "uz": "👋 <b>Hisobdan chiqdingiz.</b>\n\nQayta kirish uchun «Kirish» tugmasini bosing 👇",
        "en": "👋 <b>You have logged out.</b>\n\nTap «Log in» to log in again 👇",
        "ru": "👋 <b>Вы вышли из аккаунта.</b>\n\nЧтобы войти снова, нажмите «Войти» 👇",
        "tk": "👋 <b>Hasapdan çykdyňyz.</b>\n\nTäzeden girmek üçin «Girmek» düwmesine basyň 👇",
    },

    # ---------- Timetable (a picture of the group's week) ----------
    "tt_loading": {"uz": "⏳ Jadval tayyorlanmoqda…", "en": "⏳ Preparing your timetable…",
                   "ru": "⏳ Готовим расписание…", "tk": "⏳ Tertip taýýarlanýar…"},
    "tt_none": {
        "uz": "📅 Guruhingizning dars jadvali hali yuklanmagan. Keyinroq urinib ko‘ring.",
        "en": "📅 Your group’s timetable isn’t available yet. Please try again later.",
        "ru": "📅 Расписание вашей группы ещё не загружено. Попробуйте позже.",
        "tk": "📅 Toparyňyzyň sapak tertibi entek ýüklenmedi. Soňrak synanyşyň.",
    },
    "tt_caption": {
        "uz": "📅 <b>{group}</b> — haftalik dars jadvali\n\n{day}\n\n<i>EduPage, {date} holatiga</i>",
        "en": "📅 <b>{group}</b> — weekly timetable\n\n{day}\n\n<i>From EduPage, as of {date}</i>",
        "ru": "📅 <b>{group}</b> — расписание на неделю\n\n{day}\n\n<i>EduPage, на {date}</i>",
        "tk": "📅 <b>{group}</b> — hepdelik sapak tertibi\n\n{day}\n\n<i>EduPage, {date} ýagdaýyna görä</i>",
    },
    "tt_today": {"uz": "Bugun", "en": "Today", "ru": "Сегодня", "tk": "Şu gün"},
    "tt_tomorrow": {"uz": "Ertaga", "en": "Tomorrow", "ru": "Завтра", "tk": "Ertir"},
    "tt_free_week": {"uz": "🎉 Bu hafta darslar yo‘q.", "en": "🎉 No classes this week.",
                     "ru": "🎉 На этой неделе занятий нет.", "tk": "🎉 Bu hepde sapak ýok."},
    "tt_title": {"uz": "Dars jadvali", "en": "Timetable", "ru": "Расписание", "tk": "Sapak tertibi"},
    "tt_free": {"uz": "Dars yo‘q", "en": "No classes", "ru": "Нет занятий", "tk": "Sapak ýok"},
    "tt_count": {"uz": "{n} ta dars", "en": "{n} classes", "ru": "занятий: {n}", "tk": "{n} sapak"},
    "tt_lunch": {"uz": "Tushlik", "en": "Lunch", "ru": "Обед", "tk": "Günortanlyk"},
    "tt_week_A": {"uz": "A hafta", "en": "Week A", "ru": "Неделя A", "tk": "A hepde"},
    "tt_week_B": {"uz": "B hafta", "en": "Week B", "ru": "Неделя B", "tk": "B hepde"},
    "tt_room": {"uz": "Xona", "en": "Room", "ru": "Ауд.", "tk": "Otag"},
    "tt_course": {"uz": "{n}-kurs", "en": "Year {n}", "ru": "{n} курс", "tk": "{n}-nji kurs"},
    "tt_footer": {"uz": "Talaba Ovozi · EduPage, {date} holatiga", "en": "Talaba Ovozi · from EduPage, as of {date}",
                  "ru": "Talaba Ovozi · EduPage, на {date}", "tk": "Talaba Ovozi · EduPage, {date} ýagdaýyna görä"},
    "unknown": {
        "uz": "🤔 Tushunmadim. Quyidagi tugmalardan foydalaning 👇",
        "en": "🤔 Sorry, I didn’t get that. Please use the buttons below 👇",
        "ru": "🤔 Не понял. Пожалуйста, воспользуйтесь кнопками ниже 👇",
        "tk": "🤔 Düşünmedim. Aşakdaky düwmelerden peýdalanyň 👇",
    },

    # ---------- Home card (one message with buttons; sections open in the same message) ----------
    "home": {
        "uz": "👋 <b>Assalomu alaykum, {name}!</b>\n🎓 {group}\n\n{status}",
        "en": "👋 <b>Hello, {name}!</b>\n🎓 {group}\n\n{status}",
        "ru": "👋 <b>Здравствуйте, {name}!</b>\n🎓 {group}\n\n{status}",
        "tk": "👋 <b>Salam, {name}!</b>\n🎓 {group}\n\n{status}",
    },
    "home_open": {
        "uz": "📝 <b>{title}</b>\n🟢 Ochiq · {left}\n\n{bar}\n✅ <b>{done} / {total}</b> o‘qituvchi baholandi\n\n👇 {cta}",
        "en": "📝 <b>{title}</b>\n🟢 Open · {left}\n\n{bar}\n✅ <b>{done} / {total}</b> teachers rated\n\n👇 {cta}",
        "ru": "📝 <b>{title}</b>\n🟢 Открыт · {left}\n\n{bar}\n✅ Оценено: <b>{done} / {total}</b>\n\n👇 {cta}",
        "tk": "📝 <b>{title}</b>\n🟢 Açyk · {left}\n\n{bar}\n✅ <b>{done} / {total}</b> mugallyma baha berildi\n\n👇 {cta}",
    },
    "home_done": {
        "uz": "📝 <b>{title}</b>\n🟢 Ochiq · {left}\n\n🎉 <b>Barcha {total} o‘qituvchini baholadingiz!</b>\n"
              "Rahmat — fikringiz ta’lim sifatini oshirishga yordam beradi 💙",
        "en": "📝 <b>{title}</b>\n🟢 Open · {left}\n\n🎉 <b>You’ve rated all {total} teachers!</b>\n"
              "Thank you — your opinion helps improve teaching 💙",
        "ru": "📝 <b>{title}</b>\n🟢 Открыт · {left}\n\n🎉 <b>Вы оценили всех преподавателей ({total})!</b>\n"
              "Спасибо — ваше мнение помогает улучшить обучение 💙",
        "tk": "📝 <b>{title}</b>\n🟢 Açyk · {left}\n\n🎉 <b>Ähli {total} mugallyma baha berdiňiz!</b>\n"
              "Sag boluň — pikiriňiz bilim hilini gowulandyrmaga kömek edýär 💙",
    },
    "home_can_edit": {
        "uz": "\n\n✏️ Yopilguncha baholaringizni o‘zgartirishingiz mumkin.",
        "en": "\n\n✏️ You can change your ratings until it closes.",
        "ru": "\n\n✏️ До закрытия оценки можно изменить.",
        "tk": "\n\n✏️ Ýapylýança bahalaryňyzy üýtgedip bilersiňiz.",
    },
    "home_closed": {
        "uz": "🕊 Hozir ochiq so‘rovnoma yo‘q.\nSo‘rovnoma ochilishi bilan shu yerda xabar beramiz 🔔",
        "en": "🕊 There’s no open survey right now.\nWe’ll let you know here as soon as one opens 🔔",
        "ru": "🕊 Сейчас нет открытого опроса.\nКак только он откроется, мы сообщим здесь 🔔",
        "tk": "🕊 Häzir açyk soragnama ýok.\nSoragnama açylan badyna şu ýerde habar bereris 🔔",
    },
    "left_days": {"uz": "{n} kun qoldi", "en": "{n} days left", "ru": "осталось дней: {n}", "tk": "{n} gün galdy"},
    "left_today": {"uz": "bugun yopiladi", "en": "closes today", "ru": "закрывается сегодня", "tk": "şu gün ýapylýar"},
    "cta_start": {"uz": "Boshlash uchun tugmani bosing", "en": "Tap the button to start",
                  "ru": "Нажмите кнопку, чтобы начать", "tk": "Başlamak üçin düwmä basyň"},
    "cta_continue": {"uz": "Davom ettirish uchun tugmani bosing", "en": "Tap the button to continue",
                     "ru": "Нажмите кнопку, чтобы продолжить", "tk": "Dowam etmek üçin düwmä basyň"},
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
    "no_campaign": {
        "uz": "📭 Hozircha faol so‘rovnoma yo‘q.\n\nSo‘rovnoma boshlanganda sizga xabar yuboramiz 🔔",
        "en": "📭 There’s no active survey right now.\n\nWe’ll send you a message when one starts 🔔",
        "ru": "📭 Сейчас нет активного опроса.\n\nМы пришлём сообщение, когда он начнётся 🔔",
        "tk": "📭 Häzirki wagtda işjeň soragnama ýok.\n\nSoragnama başlanda size habar ibereris 🔔",
    },
    "campaign_status": {
        "uz": "📝 <b>{title}</b>\n\n⏳ Muddat: <b>{closes}</b> gacha\n📊 Baholangan: <b>{done} / {total}</b> o‘qituvchi\n{bar}",
        "en": "📝 <b>{title}</b>\n\n⏳ Open until: <b>{closes}</b>\n📊 Rated: <b>{done} / {total}</b> teachers\n{bar}",
        "ru": "📝 <b>{title}</b>\n\n⏳ Открыт до: <b>{closes}</b>\n📊 Оценено: <b>{done} / {total}</b> преподавателей\n{bar}",
        "tk": "📝 <b>{title}</b>\n\n⏳ Möhleti: <b>{closes}</b> çenli\n📊 Baha berildi: <b>{done} / {total}</b> mugallym\n{bar}",
    },
    "campaign_all_done": {
        "uz": "🎉 Rahmat! Siz barcha o‘qituvchilaringizni baholadingiz.",
        "en": "🎉 Thank you! You’ve rated all your teachers.",
        "ru": "🎉 Спасибо! Вы оценили всех своих преподавателей.",
        "tk": "🎉 Sag boluň! Siz ähli mugallymlaryňyza baha berdiňiz.",
    },
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

    # ---------- Profile ----------
    "profile": {
        "uz": "👤 <b>{name}</b>\n\n🆔 HEMIS: <code>{hemis}</code>\n👥 Guruh: <b>{group}</b>\n"
              "🎓 Kurs: <b>{course}</b>\n🌐 Til: {language}",
        "en": "👤 <b>{name}</b>\n\n🆔 HEMIS: <code>{hemis}</code>\n👥 Group: <b>{group}</b>\n"
              "🎓 Year: <b>{course}</b>\n🌐 Language: {language}",
        "ru": "👤 <b>{name}</b>\n\n🆔 HEMIS: <code>{hemis}</code>\n👥 Группа: <b>{group}</b>\n"
              "🎓 Курс: <b>{course}</b>\n🌐 Язык: {language}",
        "tk": "👤 <b>{name}</b>\n\n🆔 HEMIS: <code>{hemis}</code>\n👥 Topar: <b>{group}</b>\n"
              "🎓 Kurs: <b>{course}</b>\n🌐 Dil: {language}",
    },

    # ---------- Help ----------
    "help": {
        "uz": "❓ <b>Yordam</b>\n\n"
              "📝 <b>Baholash</b> — so‘rovnoma ochiq bo‘lganda o‘qituvchilaringizni 3 mezon bo‘yicha "
              "1 dan 10 gacha baholang:\n"
              "   • 🎓 O‘qitish sifati\n   • ⚖️ Adolatlilik va baholash\n   • 🤝 Kasbiy mahorat va talabalar bilan munosabat\n\n"
              "👨‍🏫 <b>O‘qituvchilarim</b> — sizga dars beradigan o‘qituvchilar ro‘yxati\n"
              "📅 <b>Dars jadvali</b> — guruhingizning haftalik jadvali, rasm ko‘rinishida\n"
              "👤 <b>Profil</b> — shaxsiy ma’lumotlaringiz (u yerda hisobdan chiqish ham bor)\n"
              "🌐 <b>Til</b> — interfeys tilini o‘zgartirish\n\n"
              "💬 Savollar bo‘yicha: {support}\n🛠 Texnik muammolar: {tech}",
        "en": "❓ <b>Help</b>\n\n"
              "📝 <b>Evaluate</b> — while a survey is open, rate each of your teachers from 1 to 10 on 3 criteria:\n"
              "   • 🎓 Teaching\n   • ⚖️ Fairness\n   • 🤝 Professionalism\n\n"
              "👨‍🏫 <b>My teachers</b> — the teachers who teach you\n"
              "📅 <b>Timetable</b> — your group’s week as a picture\n"
              "👤 <b>Profile</b> — your details (you can also log out there)\n"
              "🌐 <b>Language</b> — change the interface language\n\n"
              "💬 Questions: {support}\n🛠 Technical issues: {tech}",
        "ru": "❓ <b>Помощь</b>\n\n"
              "📝 <b>Оценить</b> — пока опрос открыт, оцените каждого преподавателя от 1 до 10 по 3 критериям:\n"
              "   • 🎓 Качество преподавания\n   • ⚖️ Справедливость и оценивание\n   • 🤝 Профессионализм и отношение к студентам\n\n"
              "👨‍🏫 <b>Мои преподаватели</b> — кто у вас ведёт занятия\n"
              "📅 <b>Расписание</b> — неделя вашей группы картинкой\n"
              "👤 <b>Профиль</b> — ваши данные (там же можно выйти из аккаунта)\n"
              "🌐 <b>Язык</b> — сменить язык интерфейса\n\n"
              "💬 По вопросам: {support}\n🛠 Технические проблемы: {tech}",
        "tk": "❓ <b>Kömek</b>\n\n"
              "📝 <b>Baha bermek</b> — soragnama açyk wagty mugallymlaryňyza 3 ölçeg boýunça "
              "1-den 10-a çenli baha beriň:\n"
              "   • 🎓 Okatmagyň hili\n   • ⚖️ Adalatlylyk we bahalandyryş\n   • 🤝 Hünär ussatlygy we talyplar bilen gatnaşyk\n\n"
              "👨‍🏫 <b>Mugallymlarym</b> — size sapak berýän mugallymlar\n"
              "📅 <b>Sapak tertibi</b> — toparyňyzyň hepdesi surat görnüşinde\n"
              "👤 <b>Profil</b> — şahsy maglumatlaryňyz (şol ýerde hasapdan çykyp hem bolýar)\n"
              "🌐 <b>Dil</b> — interfeýsiň dilini üýtgetmek\n\n"
              "💬 Soraglar boýunça: {support}\n🛠 Tehniki meseleler: {tech}",
    },

    # ---------- Bot profile (shown in Telegram before /start) ----------
    "bot_description": {
        "uz": "🎓 Talaba Ovozi — Iqtisodiyot fakulteti talabalari uchun o‘qituvchilarni baholash platformasi.\n\n"
              "Boshlash uchun «Start» tugmasini bosing 👇",
        "en": "🎓 Talaba Ovozi — the teacher evaluation platform for Economics Faculty students.\n\n"
              "Press «Start» to begin 👇",
        "ru": "🎓 Talaba Ovozi — платформа оценки преподавателей для студентов экономического факультета.\n\n"
              "Нажмите «Start», чтобы начать 👇",
        "tk": "🎓 Talaba Ovozi — Ykdysadyýet fakultetiniň talyplary üçin mugallymlara baha bermek platformasy.\n\n"
              "Başlamak üçin «Start» basyň 👇",
    },
    "bot_short_description": {
        "uz": "Iqtisodiyot fakulteti — o‘qituvchilarni baholash 📝",
        "en": "Economics Faculty — teacher evaluation 📝",
        "ru": "Экономический факультет — оценка преподавателей 📝",
        "tk": "Ykdysadyýet fakulteti — mugallymlara baha bermek 📝",
    },
    "cmd_start": {"uz": "Boshlash / asosiy menyu", "en": "Start / main menu", "ru": "Начать / главное меню",
                  "tk": "Başlamak / esasy menýu"},
    "cmd_language": {"uz": "Tilni o‘zgartirish", "en": "Change language", "ru": "Сменить язык", "tk": "Dili üýtgetmek"},
    "cmd_help": {"uz": "Yordam", "en": "Help", "ru": "Помощь", "tk": "Kömek"},

    # ---------- Controlled from the dashboard ----------
    "login_closed": {
        "uz": "⏸ Hozircha botga kirish yopiq. Keyinroq urinib ko‘ring.\n\nSavollar bo‘lsa: {support}",
        "en": "⏸ Logging in is closed for now. Please try again later.\n\nQuestions: {support}",
        "ru": "⏸ Вход в бот сейчас закрыт. Попробуйте позже.\n\nВопросы: {support}",
        "tk": "⏸ Häzirlikçe bota girmek ýapyk. Soňrak synanyşyň.\n\nSoraglar: {support}",
    },
    "my_id": {
        "uz": "🆔 Telegram ID raqamingiz: <code>{id}</code>",
        "en": "🆔 Your Telegram ID: <code>{id}</code>",
        "ru": "🆔 Ваш Telegram ID: <code>{id}</code>",
        "tk": "🆔 Telegram ID belgiňiz: <code>{id}</code>",
    },
    "admin_new_address": {
        "uz": "🔗 <b>Talaba Ovozi</b> manzili yangilandi — bot tugmalari yangi manzilga o‘tkazildi.\n\n"
              "📝 So‘rovnoma: {url}/survey\n📊 Admin sayt (internetda ochiq bo‘lsa): {url}/admin",
        "en": "🔗 The <b>Talaba Ovozi</b> address changed — the bot’s buttons now use it.\n\n"
              "📝 Survey: {url}/survey\n📊 Dashboard (if opened to the internet): {url}/admin",
        "ru": "🔗 Адрес <b>Talaba Ovozi</b> изменился — кнопки бота переведены на него.\n\n"
              "📝 Опрос: {url}/survey\n📊 Админ-сайт (если открыт в интернете): {url}/admin",
        "tk": "🔗 <b>Talaba Ovozi</b> salgysy üýtgedi — botuň düwmeleri täze salga geçirildi.\n\n"
              "📝 Sorag: {url}/survey\n📊 Admin sahypa (internetde açyk bolsa): {url}/admin",
    },
    "no_teachers_in_survey": {
        "uz": "😕 Guruhingiz uchun o‘qituvchilar ro‘yxati hali tayyor emas. Iltimos, {support} ga yozing.",
        "en": "😕 The teacher list for your group isn't ready yet. Please write to {support}.",
        "ru": "😕 Список преподавателей вашей группы ещё не готов. Напишите, пожалуйста, {support}.",
        "tk": "😕 Toparyňyz üçin mugallymlaryň sanawy entek taýýar däl. Haýyş, {support} ýazyň.",
    },
}


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
