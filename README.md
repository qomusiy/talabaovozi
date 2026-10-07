# Teacher Feedback System — Economics Faculty

Students log in through a Telegram bot, rate the teachers who actually teach them, and admins analyse the
results in a web dashboard.

**Bot:** @talabaovozibot · **Stack:** Python 3.12 · PostgreSQL 16 · SQLAlchemy + Alembic · aiogram (bot) · FastAPI (survey + dashboard)

## Status

| Step | What | State |
|------|------|-------|
| 1 | Database, Excel import | ✅ real data: 2,091 students (HEMIS export), teachers and groups from EduPage |
| 2 | Telegram bot: login, language, menu | ✅ |
| 3 | Survey (Telegram Mini App) | ✅ |
| 4 | Dashboard control: data, surveys, bot settings, messages, admins | ✅ |
| 5 | Analytics (UZ/EN/RU) | ✅ — feedback is still **demo** data until the first real survey |
| 6 | EduPage timetable → who teaches whom (auto-updated) | ✅ |
| 7 | Hosting | ✅ one computer as the server — Windows (WSL) or Linux, `scripts/setup.sh` — starts by itself; fixed address with Tailscale or a domain |

## Running it

### A new server computer

The server is Linux software (bash scripts, systemd, Docker). On **Windows** it runs in WSL — Ubuntu inside Windows,
made by Microsoft — and `scripts/windows/setup-windows.ps1` sets that up; on **Linux** `scripts/setup.sh` does it
directly. Either way you end with the same server, which starts by itself when the computer is switched on, without
anyone signing in.

**First, on the old computer** (the data is not on GitHub — personal data and keys):

```bash
scripts/server.sh uninstall    # stop it there (two bots with one token fight; nothing changes after the copy)
scripts/backup.sh transfer     # -> data/backups/talaba-transfer-<date>.tar.gz: .env + database + uploaded files
```

Copy that file by USB stick (or `scp`) — never through GitHub or a public place: it holds the bot token, the
`SECRET_KEY` and every student. Delete it from the stick afterwards. For Windows copy
`scripts/windows/setup-windows.ps1` to the stick too.

**Windows 10 (22H2) or 11.** Put both files in *Downloads*, open PowerShell **as Administrator** (Start › type
PowerShell › right-click › *Run as administrator*) and run:

```powershell
cd $HOME\Downloads
powershell -ExecutionPolicy Bypass -File .\setup-windows.ps1 -Transfer .\talaba-transfer-<date>.tar.gz
```

It installs WSL with Ubuntu 24.04 (the first time you create a Linux user name and password, and Windows may ask for
a restart — then run the same command again), downloads this repository into Ubuntu (`~/talaba-ovozi`; another
repository: `-Repo <url>`), runs `scripts/setup.sh` there, keeps Windows awake (no sleep or hibernation, the lid
does nothing) and adds the task *Talaba Ovozi server* that starts Ubuntu — and with it everything — when Windows
starts. For that it asks for your Windows password once (Windows keeps it; for a Microsoft account it is that
account's password, not the PIN). Check it once: restart Windows, don't sign in, wait 2 minutes, use the bot.

Living with it on Windows:
- Server commands are typed in Ubuntu: Start › *Ubuntu*, then `cd ~/talaba-ovozi` and `scripts/server.sh status`
  (and the other commands below). The dashboard is at http://127.0.0.1:8000/admin in the Windows browser.
- The files are in Explorer at `\\wsl.localhost\Ubuntu-24.04\home\<linux user>\talaba-ovozi` (e.g. `data\backups`
  to copy backups to a USB disk).
- Don't install Docker Desktop (it runs only while someone is signed in); `setup.sh` uses Docker inside Ubuntu.
- `wsl --shutdown` stops the server; the task starts it again within 30 seconds.
- Windows updates may restart the computer at night: that's fine, it comes back by itself.
- Keep the computer on a cable (Ethernet) or a Wi-Fi that connects by itself, and plugged in.

**Linux (Ubuntu 24.04)**, as the user that will run it (with sudo rights):

```bash
git clone https://github.com/qomusiy/talaba-ovozi.git talaba-ovozi
cd talaba-ovozi
scripts/setup.sh ~/talaba-transfer-<date>.tar.gz   # or no file: a fresh start without data
```

`setup.sh` installs Docker, the Python packages and the tunnel program, restores the data, switches off sleep, and
installs the services (*Server mode* below). It asks which public address to use (*Fixed address*). If it asks for a
restart (Docker's group), restart and run the same command again; it is safe to run any number of times.

**Updating the server** after pushing new code — in the server's (Ubuntu) terminal:
`cd ~/talaba-ovozi && git pull && scripts/setup.sh` (installs new packages, updates the database and restarts
everything; `scripts/server.sh restart` is enough for code-only changes). Once the repository is private, the server
needs a GitHub login for `git pull`: run `gh auth login` there once (`sudo apt install gh`).

### Fixed address

`TUNNEL` in `.env` decides the survey's public address — `setup.sh` asks the first time (Enter = `tailscale`); to change it later, edit `.env` and run `scripts/setup.sh` again.

- `quick` (default) — a free Cloudflare quick tunnel. The address **changes after every restart**; the bot moves its
  buttons by itself and tells the admins.
- `tailscale` — **free and permanent**: `https://talaba-ovozi.<tailnet>.ts.net` (Tailscale Funnel). `setup.sh`
  installs Tailscale and asks you to log in once (a free account with Google, GitHub or Microsoft) and to allow
  Funnel (it prints a link). `<tailnet>` is a random name like `tail1a2b3c`; it can be renamed once in the Tailscale
  admin console (DNS › Tailnet name) — do that *before* the first setup, since the address changes with it.
- `cloudflare` — **permanent on your own domain** (e.g. `https://ovoz.example.uz`; a domain costs about $10 a year).
  Add the domain to a free Cloudflare account, then Zero Trust › Networks › Tunnels › *Create a tunnel*
  (Cloudflared), copy its token (the long string after `--token`), and add a *Public hostname*
  `ovoz.example.uz` → `HTTP` `localhost:8000`. In `.env`: `TUNNEL=cloudflare`, `CLOUDFLARE_TUNNEL_TOKEN=<token>`,
  `WEBAPP_URL=https://ovoz.example.uz`.

With a fixed address the dashboard and the bot don't offer *Yangi manzil olish*; if the address stops answering, the
tunnel reconnects to the same one by itself.

### Server mode

The survey, the dashboard and the bot run as systemd user services: they restart if they crash and start at boot.

```bash
scripts/server.sh install      # once (setup.sh does it); again after changing .env
scripts/server.sh status       # running? + the public address
scripts/server.sh restart      # after changing code (the public address stays the same)
scripts/server.sh logs bot     # web | bot | tunnel
scripts/server.sh uninstall    # back to development mode
```

With `TUNNEL=quick` the public address is a Cloudflare quick tunnel (`https://….trycloudflare.com`). It changes
only when the tunnel restarts (reboot, `restart tunnel`); the bot then moves its Telegram buttons to the new address
by itself and sends it to the admins listed on the dashboard's Bot page (Telegram IDs; send `/myid` to the bot to get
yours). For an address that never changes see *Fixed address* above.

The tunnel watches itself (`scripts/tunnel.sh`): if Cloudflare deletes the quick tunnel or the address stops
answering for ~4 minutes, it starts again by itself; the dashboard's Bot page shows whether the address works and
(quick tunnel only) has a *Yangi manzil olish* (new address) button.

The dashboard is only reachable on this computer (http://127.0.0.1:8000/admin) unless it is opened to the internet —
the *Admin saytini internetda ochish* switch on the Bot page (or `ADMIN_LOCAL_ONLY=false` in `.env`); then it is at
`<public address>/admin` too, e.g. on a phone. Online it is protected by the login
(5 wrong passwords → 15 min block), SameSite cookies + an origin check on every form, and no-cache/no-frame headers.

**Development mode** — `scripts/dev.sh` runs the same programs in the terminal (Ctrl+C stops them; the tunnel keeps
its address between restarts, `scripts/dev.sh stop` closes it). It refuses to start while server mode is installed.
Only one bot may run at a time; a second copy refuses to start.

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
  4. *Students*: upload the HEMIS export (only the HEMIS ID column is required; “deactivate students not in the
     file” for a new semester). Students without a passport code get a **temporary code** (shown on the Students
     page and downloadable) until a “HEMIS ID + Pasport” file is uploaded.
  Every upload has a template (instructions sheet, drop-downs from the database, a filled-in example sheet that is never
  imported). Teachers and who-teaches-whom are one file with two sheets; students and their passport codes are one
  file. The upload history is kept.
- **Tahrirlash (Edit data)** — fix teachers (kafedra, full name, position, room, active), kafedras (name,
  faculty), groups and students (name, HEMIS ID, group, passport code, active) by hand, or add/delete them. Who
  already has evaluations can't be deleted, only switched off (students then don't rate / can't log in, results
  are kept). A timetable group's name, year and language belong to EduPage and are changed there. The teacher
  page has a *Tahrirlash* link straight to that teacher.
- **The survey's comment** — optional, or required (at least 10 characters) with *Izoh yozish majburiy* on the
  Telegram bot page.
- **So‘rovnomalar (Surveys)** — create, edit, open/close and delete survey rounds (they can't overlap). Demo data
  is shown here with one “Delete demo data” button (removes only demo rounds and their feedback).
- **Telegram bot** — online status, public address, settings the bot picks up within 10 s (login open/closed,
  comments on/off, editing ratings on/off, a notice at the top of the survey, support contacts, emoji reactions,
  the faculty channel button), automatic reminders (3 days and 1 day before a survey ends, to students who haven't
  finished), and messages to students with delivery counts:
  - to everyone, chosen years, chosen groups, a kafedra (students taught by its teachers this semester) or a
    specialty — and, while a survey is open, only those who haven't finished it (or only those who have);
  - with a photo, video or file (uploaded to Telegram once, then reused) and an optional “open survey” button;
  - a live preview of how it looks in Telegram, and *O‘zimga sinash* — send it to your own Telegram first.
  - **The menu picture**: the bot's cards carry a picture on top (a demo one is in `app/assets/menu.jpg`).
    Upload your own on this page (best 1280 × 640 px, 2:1) — it is saved as `data/media/menu.jpg`, and copying a
    file there works too. No restart needed.
- **Izohlar (Comments)** — every written comment with search and filters (choosing a group offers only its
  teachers, choosing a teacher only their groups); the **Excel** button downloads what is shown (the only Excel export). Specialty codes (IQT, BXA, …) are shown by full name (`app/faculty.py`).
- **Adminlar** — superadmins manage accounts; *viewers* only see the analytics, and for each viewer a switch decides
  whether they see which student gave a rating (off: names and HEMIS ids are left out everywhere, Excel too).
  Everyone can change their own password (click your name).
- **Programmer account** (`python -m app.cli admin-create <name> --role programmer`) — not shown to other admins and
  they can't change it. It also has *Jurnal*: every login (device, IP, how long), page opened, change made (old →
  new values, including settings) and error, by session and as a timeline; *Suhbatlar*: the bot's conversations as
  Telegram shows them to the bot's owner (people on the left; their messages, the bot's replies with buttons, button
  taps, reactions, edits and deletions on the right; refreshes by itself) with a box to write to that person as the
  bot — logged from now on by `app/bot/chatlog.py`, passport numbers never stored, kept for a year; *Baholar*: change
  or delete a rating when a student asks; and the data structure (tables, links, row counts) on the Data page.
- **Ko‘rinish (Display)** — the "Aa" button next to your name: text size (90–150 %), light/dark theme,
  high contrast, less motion, wider spacing, underlined links, and *Baho beruvchilarni yashirish* — your own panel
  shows "Talaba" instead of who rated (Excel too), e.g. while showing your screen. Saved with the account.
- **The bot for admins** — link a dashboard account to Telegram on *Mening hisobim* (a one-time link, or your
  @username: the first message saves the Telegram ID, so a later username change doesn't matter; a superadmin can
  enter it for others on *Adminlar*). The bot then shows that person an admin card instead of the student menu:
  the survey's numbers, *🔗 Sayt manzili* (and `/link`), *📈 Batafsil*, a *📊 Statistika* Mini App (charts on the phone,
  no password — Telegram vouches for the person; `app/web/miniapp.py`), alerts when the address changes, an optional
  daily report at 20:00 while a survey is open, and for superadmins *🛠 Yangi manzil olish*. Admins' actions in the
  bot are in the programmer's *Jurnal* too.

**The bot** has no keyboard to open or close: `/start` sends one card (the menu picture, the survey status and
buttons), and sections open in that same card with ⬅️ Back — *O‘qituvchilarim*, *Profil* (with *Hisobdan chiqish*,
log out), *Til*, *Yordam*, the faculty channel. *📅 Dars jadvali* (or `/timetable`) sends the group's week from
EduPage as a picture (`app/bot/pictures.py`), with the day's classes in the caption.

Students are reached through their group (Guruhlar → group name), or *Barcha talabalar* on the Groups page.
Every table sorts by several columns: the first column clicked orders it, the next ones order within it.

**Kafedras.** EduPage doesn't say which kafedra a teacher belongs to, so a teacher without one gets the kafedra
that teaches most of their subjects (`app/services/departments.py`, TIIAME's kafedra and faculty names) — on
every timetable sync for new teachers, or with *Fanlarga qarab to‘ldirish* / `python -m app.cli departments-guess`.
Teachers of other faculties' kafedras (Oliy matematika, Gumanitar fanlar, …) are grouped under their faculty.
A kafedra set by hand or from the teachers Excel is never changed by the guess.

**Backups.** Every night at 03:30 (`talaba-backup.timer`; it catches up if the computer was off) the database and
uploaded files are copied to `data/backups` — the newest 14 are kept. `scripts/backup.sh` makes one now,
`scripts/backup.sh list` shows them, `scripts/backup.sh restore <file>` puts one back (it saves the current data
first). Copy a backup to another disk now and then: a copy on the same disk doesn't survive the disk.

Command line equivalents: `python -m app.cli --help` (`timetable-sync`, `departments-guess`, `import-students`,
`demo [--clear]`, `reset-data --yes`, …).

## Data model

```
departments ─< teachers ─< teaching_assignments >─ groups ─< students
                               │        │
                           subjects  semesters ─< survey_campaigns
                                                    │
                          feedback (campaign, student, teacher, group,
                                    teaching, fairness, professionalism 1-10, comment)
```

Plus `app_settings` (dashboard settings the bot reads), `broadcasts` (messages to students), `timetable_snapshots`
(EduPage downloads), `import_logs` (upload history).

- **departments** are kafedras, each with its faculty (see *Kafedras* above).
- **teaching_assignments** decides whom a student can rate: every teacher assigned to the student's group
  in the current semester.
- **Feedback is open** (linked to the student). One evaluation per student, teacher and campaign is enforced
  by a unique constraint. Anonymous feedback may be added later.
- **Passports** are never stored, only an HMAC hash keyed by `SECRET_KEY` in `.env`.
  Back up `.env`: if `SECRET_KEY` changes, students must be re-imported before anyone can log in.

## Excel import

Group names are matched on “admission year – number – specialty” (`26-01-IQT uz` = `26-01 IQT`), so HEMIS and
EduPage spellings meet. Headers are matched flexibly (Uzbek / Russian / English, apostrophes and punctuation ignored, title rows
above the header are skipped). If a real file uses a header the importer doesn't recognise, you get an error
listing the columns it found; add the header to the alias lists in `app/importers/excel.py`.

- **Students:** upsert by HEMIS id; keeps each student's Telegram link; names in capitals are tidied.
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

- A student sees only teachers assigned to their group in the current semester.
- 3 criteria, each 1-10: teaching quality (*O‘qitish sifati*), fairness and assessment (*Adolatlilik va baholash*),
  professionalism and attitude to students (*Kasbiy mahorat va talabalar bilan munosabat*); optional comment.
  Columns: `teaching`, `fairness`, `professionalism`; the texts are in `app/web/i18n.py` and the admin i18n.
- One evaluation per student, teacher and survey round; re-submitting updates it until the round closes
  (unless “changing a submitted rating” is turned off on the Bot page).
- The Mini App authenticates with Telegram's signed `initData`; no separate login.
