# Teacher Feedback System — Economics Faculty

Students rate their teachers anonymously through a Telegram bot — they pick their group, so they see the teachers
who actually teach them — and admins analyse the results in a web dashboard.

**Bot:** @talabaovozibot · **Stack:** Python 3.12 · PostgreSQL 16 · SQLAlchemy + Alembic · aiogram (bot) · FastAPI (survey + dashboard)

## Status

| Step | What | State |
|------|------|-------|
| 1 | Database, Excel import | ✅ teachers and groups from EduPage; group sizes (2,091 students) from HEMIS |
| 2 | Telegram bot: language, anonymous intro, picking a group, menu | ✅ |
| 3 | Survey (Telegram Mini App) | ✅ |
| 4 | Dashboard control: data, surveys, bot settings, messages, admins | ✅ |
| 5 | Analytics (UZ/EN/RU) | ✅ — feedback is still **demo** data until the first real survey |
| 6 | EduPage timetable → who teaches whom (auto-updated) | ✅ |
| 7 | Hosting | ✅ one computer as the server — Windows (`scripts\setup.bat`) or Linux (`scripts/setup.sh`) — starts by itself; fixed address with Tailscale or a domain |

## Running it

The whole server is one program, the same on Linux and Windows: `python -m app.server` runs the web server (survey +
dashboard), the Telegram bot and the public address, starts each again if it stops, and makes a database backup every
night. A setup script installs everything and makes the server start with the computer, before anyone logs in:

|                         | Linux (Ubuntu 24.04)                       | Windows 10 / 11                         |
|-------------------------|--------------------------------------------|-----------------------------------------|
| Set up (safe to rerun)  | `scripts/setup.sh [transfer file]`         | `scripts\setup.bat`                     |
| Manage                  | `scripts/server.sh <command>`              | `scripts\server.bat <command>`          |
| Database                | PostgreSQL 16 in Docker (`scripts/db.sh`)  | PostgreSQL 16, a Windows service        |
| Starts with the computer| the systemd service `talaba`               | the task *Talaba Ovozi* (Task Scheduler)|

Both scripts take the same commands:

```bash
scripts/server.sh status              # running? + the public address
scripts/server.sh logs bot            # follow a log: server | web | bot | tunnel (Ctrl+C stops following)
scripts/server.sh restart             # after changing .env
scripts/server.sh update              # after pushing new code: git pull, new packages, restart
scripts/server.sh backup | backups | restore <file> | transfer | stop | start
```

Logs are in `data/runtime/logs/`.

### A new server computer

**First, on the old computer** — the data is not on GitHub (personal data and keys):

```bash
scripts/server.sh uninstall    # stop it there for good (two bots with one token fight) - Windows: scripts\server.bat stop
scripts/server.sh transfer     # -> data/backups/talaba-transfer-<date>.tar.gz: .env + database + uploaded files
```

Copy that file by USB stick — never through GitHub or a public place: it holds the bot token, the `SECRET_KEY` and
every student.

**Windows 10 / 11:**

```powershell
git clone https://github.com/qomusiy/talabaovozi.git C:\talabaovozi
# put talaba-transfer-<date>.tar.gz into C:\talabaovozi, then:
C:\talabaovozi\scripts\setup.bat
```

`setup.bat` (double-clicking it works too) asks for administrator rights and installs what is missing: Python 3.12,
PostgreSQL 16 (a Windows service on port 5433, reachable only from this computer), cloudflared or Tailscale. It
restores the data from the transfer file, asks which public address to use (*Fixed address*), keeps Windows awake
(no sleep or hibernation, a laptop lid does nothing) and adds the task *Talaba Ovozi* that runs the server whenever
Windows starts. Pick a folder outside OneDrive (`C:\talabaovozi`).

Set up on that computer before (it has data of its own)? Get the new code and run the setup again with the new
transfer file:

```powershell
cd C:\talabaovozi
git pull
# put the new talaba-transfer-<date>.tar.gz into C:\talabaovozi, then:
scripts\setup.bat
```

It asks whether to replace that computer's data with the file's (`y`; a copy of the data that was there is saved to
`data\backups` first) and keeps that computer's `.env` (its address settings). Without a transfer file — only new
code — `scripts\server.bat update` is enough: it backs the database up, updates it and restarts.

**Linux (Ubuntu 24.04)**, as the user that will run it (with sudo rights):

```bash
git clone https://github.com/qomusiy/talabaovozi.git talaba-ovozi
cd talaba-ovozi
scripts/setup.sh ~/talaba-transfer-<date>.tar.gz   # or no file: a fresh start without data
```

`setup.sh` installs Docker (the database), the Python packages and cloudflared or Tailscale, restores the data, asks
which public address to use (*Fixed address*), switches off sleep, and installs the systemd service `talaba` that runs
the server whenever the computer starts. If it asks for a restart (Docker's group), restart and run the same command
again.

Once the repository is private, the server needs a GitHub login for `update` (Windows: Git asks in a browser window
the first time; Linux: `gh auth login`).

### Fixed address

`TUNNEL` in `.env` decides the survey's public address — the setup asks the first time (Enter = `tailscale`); to
change it later, edit `.env` and run the setup again.

- `quick` (default) — a free Cloudflare quick tunnel. The address **changes after every restart**; the bot moves its
  buttons by itself (admins who turned on 🔔 *Server xabarlari* in the bot hear of it).
- `tailscale` — **free and permanent**: `https://talaba-ovozi.<tailnet>.ts.net` (Tailscale Funnel). The setup
  installs Tailscale and asks you to log in once (a free account with Google, GitHub or Microsoft) and to allow
  Funnel (it prints a link). `<tailnet>` is a random name like `tail1a2b3c`; it can be renamed once in the Tailscale
  admin console (DNS › Tailnet name) — do that *before* the first setup, since the address changes with it.
- `cloudflare` — **permanent on your own domain** (e.g. `https://ovoz.example.uz`; a domain costs about $10 a year).
  Add the domain to a free Cloudflare account, then Zero Trust › Networks › Tunnels › *Create a tunnel*
  (Cloudflared), copy its token (the long string after `--token`), and add a *Public hostname*
  `ovoz.example.uz` → `HTTP` `localhost:8000`. In `.env`: `TUNNEL=cloudflare`, `CLOUDFLARE_TUNNEL_TOKEN=<token>`,
  `WEBAPP_URL=https://ovoz.example.uz`.

The server watches the address: if Cloudflare deletes a quick tunnel or the address stops answering for ~4 minutes,
it starts the tunnel again — a quick tunnel gets a new address (the bot moves its Telegram buttons there by itself and
tells the admins who switched on its server messages), a fixed one reconnects to the same address. The dashboard's
Bot page shows whether the address works and (quick tunnel only) has a
*Yangi manzil olish* (new address) button.

The dashboard is only reachable on the server computer (http://127.0.0.1:8000/admin) unless it is opened to the
internet — the *Admin saytini internetda ochish* switch on the Bot page (or `ADMIN_LOCAL_ONLY=false` in `.env`); then
it is at `<public address>/admin` too, e.g. on a phone. Online it is protected by the login
(5 wrong passwords → 15 min block), SameSite cookies + an origin check on every form, and no-cache/no-frame headers.

### Development

`scripts/server.sh run` runs the same server in the terminal (Ctrl+C stops it); on Windows
`.venv\Scripts\python -m app.server`. Only one server — and one bot — runs on a computer at a time (a second copy
refuses to start), so stop the service first: `scripts/server.sh stop`. A bot token also works in one place only:
while the real server runs the bot elsewhere, `scripts/server.sh run --no-bot` runs everything but the bot.

Tests: `pytest` (uses the separate `feedback_test` database).

## Managing it from the dashboard

Everything that changes between semesters is done in the dashboard — no code changes:

- **Ma’lumotlar (Data)** — four steps with a status each:
  1. *Semester*: create the new one (it becomes current) or edit dates.
  2. *Timetable*: downloaded from EduPage and **re-checked automatically every 6 h** (adjustable); if it changed,
     teachers, groups and who-teaches-whom are updated and the bot uses them at once. If EduPage can't be used,
     upload the timetable as Excel (automatic checks then stop).
  3. *Who teaches whom*: built from the timetable (subjects like “Kelajak soati” can be excluded from rating), or
     uploaded as Excel. Teacher details (full names, departments, rooms) can be uploaded on top. Groups whose
     students would see no teachers are listed.
  4. *Group sizes*: how many students each group has, for “X of Y took part” — upload the HEMIS export (one row per
     student, counted per group; **no names are kept**) or a “Guruh | Talabalar soni” table; “clear groups not in
     the file” for a new semester. Groups with teachers but no size are listed. An optional *Raqami* column sets
     the group numbers students know (see *Tahrirlash*); a row with only a number leaves the size alone.
  Every upload has a template (instructions sheet, drop-downs from the database, a filled-in example sheet that is never
  imported). Teachers and who-teaches-whom are one file with two sheets. The upload history is kept.
- **Tahrirlash (Edit data)** — fix teachers (kafedra, full name, position, room, active), kafedras (name,
  faculty) and groups (with their number of students) by hand, or add/delete them. A teacher with ratings can't be
  deleted, only switched off; a group with ratings can't be deleted. A timetable group's name, year and language
  belong to EduPage and are changed there (its number of students and its *Raqami* here).
- **Group numbers (*Raqami*)** — students don't know the university's group names (`24-09 BXA (ing)`), they know a
  number (302). Once an admin types it in, the bot shows “302-guruh” when picking a group, on the home card, in the
  survey and on the timetable; until then the system name. On the dashboard each person can show numbers next to the
  names (“302 · 24-09 BXA (ing)”, Excel too) with *Ko‘rinish › Guruh raqamlarini ko‘rsatish*. The teacher page has a *Tahrirlash* link
  straight to that teacher.
- **The survey's comment** — optional, or required (at least 10 characters) with *Izoh yozish majburiy* on the
  Telegram bot page.
- **So‘rovnomalar (Surveys)** — create, edit, open/close and delete survey rounds (they can't overlap). Demo data
  is shown here with one “Delete demo data” button (removes only demo rounds and their feedback).
- **Telegram bot** — online status, public address, settings the bot picks up within 10 s (comments on/off,
  editing ratings on/off, a notice at the top of the survey, support contacts, emoji reactions, the faculty channel
  button), automatic reminders (3 days and 1 day before a survey ends, to users who haven't finished), and messages
  to the bot's users with delivery counts:
  - to everyone, or — by the group they picked — chosen years, groups, a kafedra (groups taught by its teachers this
    semester) or a specialty; and, while a survey is open, only those who haven't finished it (or only those who
    have). Blocked and suspended users get nothing;
  - with a photo, video or file (uploaded to Telegram once, then reused) and an optional “open survey” button;
  - a live preview of how it looks in Telegram, and *O‘zimga sinash* — send it to your own Telegram first.
  - **The menu picture**: the bot's cards carry a picture on top (the default, `app/assets/menu.jpg`, is drawn
    in the style of the bot's profile photo).
    Upload your own on this page (best 1280 × 640 px, 2:1) — it is saved as `data/media/menu.jpg`, and copying a
    file there works too. No restart needed.
- **Izohlar (Comments)** — every written comment with search and filters (choosing a group offers only its
  teachers, choosing a teacher only their groups); the **Excel** button downloads what is shown (the only Excel export). Specialty codes (IQT, BXA, …) are shown by full name (`app/faculty.py`).
- **Adminlar** — superadmins manage accounts; *viewers* only see the analytics. Nobody but programmer accounts sees
  who rated (pages, searches and Excel show the group only). Everyone can change their own password (click your
  name).
- **Programmer account** (`python -m app.cli admin-create <name> --role programmer`; the same command sets a new
  password) — not shown to other admins and they can't change it. It sees which Telegram account gave each rating
  (a link next to it), and also has:
  - *Foydalanuvchilar* — every account of the bot: name, @username, Telegram ID, profile photo, everything Telegram
    tells a bot (bio, language, Premium, …), its group, ratings, activity and conversation. To stop abuse:
    **block** it, **suspend** it for an hour / a day / a week, send a **warning** as the bot, change its group, keep a
    note, delete its ratings (one round or all) or the whole account. The **flood guard** suspends anyone who sends
    more than 20 messages in 10 seconds for 10 minutes by itself (shown as ⚡ on the page); the survey refuses more
    than 30 ratings a minute from one account.
  - *Jurnal*: every login (device, IP, how long), page opened, change made (old → new values, including settings)
    and error, by session and as a timeline;
  - *Suhbatlar*: the bot's conversations as Telegram shows them to the bot's owner (people on the left; their
    messages, the bot's replies with buttons, button taps, reactions, edits and deletions on the right; refreshes by
    itself) with a box to write to that person as the bot — logged by `app/bot/chatlog.py` (blocked users too),
    kept for a year;
  - *Baholar*: change or delete a rating; and the data structure (tables, links, row counts) on the Data page.
- **Ko‘rinish (Display)** — the "Aa" button next to your name: text size (90–150 %), light/dark theme,
  high contrast, less motion, wider spacing, underlined links, and (programmer accounts) *Kim baholaganini
  yashirish* — your own panel hides who rated (Excel too), e.g. while showing your screen. Saved with the account.
- **The bot for admins** — link a dashboard account to Telegram on *Mening hisobim* (a one-time link, or your
  @username: the first message saves the Telegram ID, so a later username change doesn't matter; a superadmin can
  enter it for others on *Adminlar*). The bot then shows that person an admin card instead of the student menu:
  the survey's numbers, *🔗 Sayt manzili* (and `/link`), *📈 Batafsil*, a *📊 Statistika* Mini App (charts on the phone,
  no password — Telegram vouches for the person; `app/web/miniapp.py`), the student menu, and two switches that are
  **off until turned on**: *🔔 Server xabarlari* — when the server starts or the public address changes, one message
  says when it started, whether the bot, the web server and the site on its public address work, whether a survey
  is open and where the dashboard is, and the bot **edits that same message** as things come up until everything
  works (`app/bot/server_alerts.py`); and *📬 Kunlik hisobot* at 20:00 while a survey is open. Superadmins also get
  *🛠 Yangi manzil olish*. Admins' actions in the bot are in the programmer's *Jurnal* too.

**The bot** — its Telegram name and descriptions are `BOT_NAME`, `BOT_DESCRIPTION` and `BOT_SHORT_DESCRIPTION` in
`app/bot/i18n.py`, the same for every Telegram language, and are set when the bot starts (only if they differ). The
first time: the language, then what the bot is (anonymous; no personal details are asked), then the group — course ›
specialty › group — so the survey shows only that group's teachers. After that `/start` sends one card (the menu
picture, a greeting, the group, whether the survey is open, how many teachers are rated, and buttons). A tap swaps the
card: the next card is sent while the tapped one is deleted, at the same time, so the chat always ends with one fresh
card (`app/bot/cards.py`) — *O‘qituvchilarim*, *Guruhni o‘zgartirish*, *Til*, *Yordam*, the faculty channel, each
with ⬅️ Back. *📅 Dars jadvali* (or `/timetable`) sends the group's whole week from EduPage as a picture to keep
(`app/bot/pictures.py`; nothing marks “today”, it is the same every day) and the menu card moves under it.

Every table sorts by several columns: the first column clicked orders it, the next ones order within it.

**Kafedras.** EduPage doesn't say which kafedra a teacher belongs to, so a teacher without one gets the kafedra
that teaches most of their subjects (`app/services/departments.py`, TIIAME's kafedra and faculty names) — on
every timetable sync for new teachers, or with *Fanlarga qarab to‘ldirish* / `python -m app.cli departments-guess`.
Teachers of other faculties' kafedras (Oliy matematika, Gumanitar fanlar, …) are grouped under their faculty.
A kafedra set by hand or from the teachers Excel is never changed by the guess.

**Backups.** Every night at 03:30 (caught up if the computer was off) — and before the server applies a database
update — the server copies the database and uploaded files to `data/backups`; the newest 14 are kept. `scripts/server.sh backup` (Windows: `scripts\server.bat backup`)
makes one now, `backups` lists them, `restore <file>` puts one back (it saves the current data first). Copy a backup
to another disk now and then: a copy on the same disk doesn't survive the disk.

Command line equivalents: `python -m app.cli --help` (`timetable-sync`, `departments-guess`, `import-group-sizes`,
`group "<name>"`, `demo [--clear]`, `reset-data --yes`, …).

## Data model

```
departments ─< teachers ─< teaching_assignments >─ groups (student_count) ─< bot_users
                               │        │                                  │
                           subjects  semesters ─< survey_campaigns          │
                                                    │                       │
                          feedback (campaign, user ─────────────────────────┘, teacher, group,
                                    teaching, fairness, professionalism 1-10, comment)
```

Plus `app_settings` (dashboard settings the bot reads), `broadcasts` (messages to the bot's users),
`timetable_snapshots` (EduPage downloads), `import_logs` (upload history), `bot_chats` / `bot_messages` (the
conversation log).

- **departments** are kafedras, each with its faculty (see *Kafedras* above).
- **There is no student list.** `bot_users` are Telegram accounts (id = the Telegram user id; demo data uses
  negative ids); each picks a group in the bot. `groups.student_count` is how many students a group has,
  `groups.number` the number students know it by (302).
- **teaching_assignments** decides whom a user can rate: every teacher assigned to their group in the current
  semester (without a group: every teacher of the semester).
- **Feedback** belongs to the account (`user_id`) and keeps the group it was given as; one evaluation per account,
  teacher and campaign (a unique constraint). Only programmer accounts can see the account.

## Excel import

Group names are matched on “admission year – number – specialty” (`26-01-IQT uz` = `26-01 IQT`), so HEMIS and
EduPage spellings meet. Headers are matched flexibly (Uzbek / Russian / English, apostrophes and punctuation ignored, title rows
above the header are skipped). If a real file uses a header the importer doesn't recognise, you get an error
listing the columns it found; add the header to the alias lists in `app/importers/excel.py`.

- **Group sizes:** counts the rows per group (a HEMIS id seen twice counts once) or reads “Talabalar soni”;
  creates missing groups; keeps no names. “Raqami” sets the group's number (one number per group).
- **Teachers:** matched by id, full name, or any way the timetable writes the name (`Qodirov RS`).
- **Assignments:** replace the current semester's assignments and switch the source to “Excel”.
- **Timetable:** one row per class (day, period, groups, subject, type, teacher, room, week A/B).

## Timetable (EduPage)

Dashboard → **Dars jadvali**, or `python -m app.cli timetable-sync`, downloads the timetable from
https://tiiame.edupage.org/timetable/ (the same JSON its web viewer uses) and stores it as a snapshot
(`timetable_snapshots`; the newest is shown, the last 5 are kept).

- **Faculty groups:** every group listed under the `Iqtisodiyot` section in EduPage (`EDUPAGE_FACULTY` in `.env`);
  if that section ever disappears, the specialty codes in `FACULTY_GROUP_CODES` are used instead.
- **Faculty teachers:** everyone who teaches at least one faculty group. Their whole week is kept, including lessons
  in other faculties (those groups are shown greyed out, without a link).
- Lesson type comes from the subject suffix: `(Ma)` lecture, `(A)` practice, `(S)` seminar, `(L)` lab; none = other.
  `A` / `B` week lessons count as half a class per week. Lessons EduPage hasn't placed yet are counted, not shown.
- Pages: faculty overview (load heatmap, lesson-type mix, groups by course, teachers table), and a weekly grid per
  group or teacher (a day list on phones) with gaps between classes, the busiest day and a subject table.
- A teacher in our database whose name (or `edupage_id`) matches is linked both ways with their feedback page.

## Survey rules

- A user sees only the teachers assigned to their group in the current semester. (Accounts from before that went on
  without a group are asked to pick one; the survey page still lists every teacher of the semester for them, with a
  search.)
- 3 criteria, each 1-10: teaching quality (*O‘qitish sifati*), fairness and assessment (*Adolatlilik va baholash*),
  professionalism and attitude to students (*Kasbiy mahorat va talabalar bilan munosabat*); optional comment.
  Columns: `teaching`, `fairness`, `professionalism`; the texts are in `app/web/i18n.py` and the admin i18n.
- One evaluation per account, teacher and survey round; re-submitting updates it until the round closes
  (unless “changing a submitted rating” is turned off on the Bot page).
- The Mini App knows who opened it from Telegram's signed `initData` — no login; blocked and suspended accounts are
  refused.
