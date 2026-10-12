"""Excel templates for the dashboard's uploads.

Each template has
- the sheet(s) to fill in, with headers the importers know, an explanation on every header (hover it in Excel),
  drop-down lists filled from the database (groups, teachers, kafedras, lesson types) and id columns kept as text,
  so Excel doesn't turn 376231103290 into 3.76E+11;
- "Yo‘riqnoma": what each column means, which are required, how the upload works;
- "Namuna": a filled-in example. It is never imported - only the sheets to fill in are.
The teachers upload takes one file for two things: teachers, and who teaches whom.
"""
from dataclasses import dataclass, field
from io import BytesIO

from openpyxl import Workbook
from openpyxl.comments import Comment
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

INFO_SHEETS = {"Yo‘riqnoma", "Namuna", "Ro‘yxatlar"}  # never imported
LESSON_TYPES = ["ma’ruza", "amaliy", "laboratoriya", "seminar"]
DAYS = ["Dushanba", "Seshanba", "Chorshanba", "Payshanba", "Juma", "Shanba"]

INK, ACCENT, SOFT, MUTED = "111113", "3B3CAE", "EEF0FF", "6B6B73"
HEAD_FILL = PatternFill("solid", fgColor=ACCENT)
REQ_FILL = PatternFill("solid", fgColor="23247A")
LINE = Side(style="thin", color="D4D4D8")


@dataclass
class Column:
    header: str
    note: str                 # shown on the header and in Yo‘riqnoma
    width: int = 18
    required: bool = False
    text: bool = False        # keep as text (long ids)
    choices: str | None = None  # name of a list: groups / teachers / departments / types / days / weeks / periods
    strict: bool = False      # only values from the list


@dataclass
class Sheet:
    title: str
    columns: list[Column]
    sample: list[list] = field(default_factory=list)


TEMPLATES: dict[str, dict] = {
    "students": {
        "title": "Guruhlardagi talabalar soni",
        "intro": [
            "Har bir guruhda nechta talaba borligi — «qancha talabadan qanchasi so‘rovnomada qatnashdi» uchun.",
            "So‘rovnoma anonim: talabalarning ismlari kerak emas va saqlanmaydi — faqat sonlar.",
            "Ikki usul: har bir guruhga bitta qator va «Talabalar soni»; yoki HEMIS’dan olingan ro‘yxat "
            "(har talabaga bitta qator) — bot ularni guruh bo‘yicha o‘zi sanaydi.",
            "Yangi semestrda «Faylda yo‘q guruhlar sonini tozalash» belgisi bilan yuklang.",
            "«Raqami» ustuni ixtiyoriy: talabalar biladigan guruh raqamlarini (302, 306, ...) bir yo‘la kiritish uchun. "
            "Faqat Guruh va Raqami to‘ldirilgan qator talabalar sonini o‘zgartirmaydi.",
        ],
        "sheets": [Sheet("Guruhlar", [
            Column("Guruh", "Guruh nomi, dars jadvalidagidek: 25-16 IQT, 26-03 IQT (ru).", 20, True, choices="groups"),
            Column("Talabalar soni", "Guruhdagi talabalar soni. HEMIS ro‘yxatini yuklasangiz, bo‘sh qoldiring — "
                   "har bir qator bitta talaba deb sanaladi.", 16),
            Column("Kurs", "1–4. Bo‘sh qolsa, guruh nomidan aniqlanadi.", 8),
            Column("Raqami", "Talabalar guruhni biladigan raqam, masalan 302 — botda guruh nomi o‘rniga shu chiqadi. "
                   "Bo‘sh qolsa, o‘zgarmaydi.", 10),
        ], [["25-16 IQT", 28, 2, "216"], ["26-03 IQT (ru)", 25, 1, "103"]])],
    },
    "teaching": {
        "title": "O‘qituvchilar va biriktirishlar",
        "intro": [
            "Bitta faylda ikki varaq: «O‘qituvchilar» (to‘liq ism, kafedra, lavozim, xona) va «Biriktirishlar» "
            "(kim qaysi guruhga qaysi fandan dars beradi).",
            "Keraklisini to‘ldiring — ikkalasini ham, yoki faqat bittasini. Bo‘sh varaq e’tiborsiz qoladi.",
            "«O‘qituvchilar»: dars jadvalidagi o‘qituvchilarga ma’lumot qo‘shiladi (jadvaldagi ismi bo‘yicha topiladi).",
            "«Biriktirishlar» to‘ldirilsa, joriy semestrdagi biriktirishlar shu fayldagilar bilan almashadi va "
            "dars jadvali ularni boshqa o‘zgartirmaydi (Ma’lumotlar sahifasida yana jadvalga qaytarish mumkin).",
            "Talaba botda tanlagan guruhiga biriktirilgan o‘qituvchilarni baholaydi.",
        ],
        "sheets": [
            Sheet("O‘qituvchilar", [
                Column("F.I.Sh.", "O‘qituvchining to‘liq ismi: Qodirov Rustam Sobirovich.", 34, True),
                Column("Jadvaldagi ism", "Dars jadvalida qanday yozilgan: Qodirov RS. Shu bo‘yicha jadvaldagi "
                       "o‘qituvchi topiladi.", 22, choices="teachers"),
                Column("Kafedra", "Kafedra nomi. Ro‘yxatda bo‘lmasa — yangi kafedra yaratiladi.", 30, choices="departments"),
                Column("Lavozim", "dotsent, katta o‘qituvchi, professor, assistent …", 18),
                Column("Xona", "Ish xonasi: B-207.", 10),
            ], [["Qodirov Rustam Sobirovich", "Qodirov RS", "Iqtisodiyot", "dotsent", "B-207"],
                ["Saidova Madina Karimovna", "Saidova Madina", "Ingliz tili", "katta o‘qituvchi", "A-203"]]),
            Sheet("Biriktirishlar", [
                Column("O‘qituvchi", "Jadvaldagi yoki to‘liq ismi. Topilmasa — yangi o‘qituvchi qo‘shiladi.", 28, True,
                       choices="teachers"),
                Column("Guruh", "Guruh nomi: 25-16 IQT.", 18, True, choices="groups"),
                Column("Fan", "Fan nomi: Makroiqtisodiyot.", 34, True),
                Column("Turi", "ma’ruza, amaliy, laboratoriya yoki seminar.", 14, choices="types", strict=True),
            ], [["Qodirov RS", "25-16 IQT", "Makroiqtisodiyot", "ma’ruza"],
                ["Qodirov RS", "25-17 IQT", "Makroiqtisodiyot", "ma’ruza"],
                ["Saidova Madina", "25-16 IQT", "Ingliz tili", "amaliy"]]),
        ],
    },
    "timetable": {
        "title": "Dars jadvali",
        "intro": [
            "EduPage ishlatib bo‘lmaganda. Har qator — bitta dars.",
            "Bir dars bir necha guruhga bo‘lsa, guruhlarni vergul bilan yozing: 25-16 IQT, 25-17 IQT.",
            "Juftliklar: 1 — 08:00, 2 — 09:30, 3 — 11:00, 4 — 13:00, 5 — 14:30, 6 — 16:00.",
            "«Hafta»: A yoki B — dars haftama-hafta almashsa; har hafta bo‘lsa bo‘sh qoldiring.",
            "Yuklangach EduPage’dan avtomatik tekshirish o‘chadi.",
        ],
        "sheets": [Sheet("Dars jadvali", [
            Column("Kun", "Dushanba … Shanba.", 13, True, choices="days", strict=True),
            Column("Juftlik", "1–6.", 9, True, choices="periods", strict=True),
            Column("Guruh", "Bir yoki bir necha guruh, vergul bilan.", 26, choices="groups"),
            Column("Fan", "Fan nomi.", 30, True),
            Column("Turi", "ma’ruza, amaliy, laboratoriya yoki seminar.", 14, choices="types", strict=True),
            Column("O‘qituvchi", "Bir yoki bir necha o‘qituvchi, vergul bilan.", 26, choices="teachers"),
            Column("Xona", "B-207.", 10),
            Column("Hafta", "A yoki B; har hafta bo‘lsa bo‘sh.", 8, choices="weeks", strict=True),
        ], [["Dushanba", 1, "25-16 IQT, 25-17 IQT", "Makroiqtisodiyot", "ma’ruza", "Qodirov RS", "B-207", ""],
            ["Dushanba", 3, "25-16 IQT", "Makroiqtisodiyot", "amaliy", "Saidova Madina", "A-203", "A"]])],
    },
}


def _style_header(ws, columns: list[Column]) -> None:
    for i, col in enumerate(columns, 1):
        cell = ws.cell(row=1, column=i, value=col.header)
        cell.font = Font(bold=True, color="FFFFFF", size=11)
        cell.fill = REQ_FILL if col.required else HEAD_FILL
        cell.alignment = Alignment(vertical="center", horizontal="left", indent=1)
        cell.border = Border(bottom=LINE)
        cell.comment = Comment(("Majburiy. " if col.required else "") + col.note, "Talaba Ovozi", width=260, height=110)
        ws.column_dimensions[get_column_letter(i)].width = col.width
    ws.row_dimensions[1].height = 26
    ws.freeze_panes = "A2"
    ws.sheet_view.zoomScale = 110


def _lists_sheet(wb: Workbook, lists: dict[str, list]) -> dict[str, str]:
    """A hidden sheet with the drop-down values; returns list name -> range formula."""
    ws = wb.create_sheet("Ro‘yxatlar")
    ws.sheet_state = "hidden"
    ranges = {}
    for i, (name, values) in enumerate(lists.items(), 1):
        letter = get_column_letter(i)
        ws.cell(row=1, column=i, value=name)
        for r, v in enumerate(values, 2):
            ws.cell(row=r, column=i, value=v)
        ranges[name] = f"'Ro‘yxatlar'!${letter}$2:${letter}${max(2, len(values) + 1)}"
    return ranges


def _data_sheet(wb: Workbook, sheet: Sheet, ranges: dict[str, str], first: bool, rows: int = 3000) -> None:
    ws = wb.active if first else wb.create_sheet()
    ws.title = sheet.title
    _style_header(ws, sheet.columns)
    for i, col in enumerate(sheet.columns, 1):
        letter = get_column_letter(i)
        if col.text:
            for r in range(2, rows + 2):
                ws[f"{letter}{r}"].number_format = "@"
        if col.choices and col.choices in ranges:
            dv = DataValidation(type="list", formula1=ranges[col.choices], allow_blank=True,
                                showErrorMessage=col.strict, errorTitle="Talaba Ovozi",
                                error="Ro‘yxatdagi qiymatlardan birini tanlang.")
            dv.add(f"{letter}2:{letter}{rows + 1}")
            ws.add_data_validation(dv)
    ws.auto_filter.ref = f"A1:{get_column_letter(len(sheet.columns))}1"


def _guide(wb: Workbook, spec: dict) -> None:
    ws = wb.create_sheet("Yo‘riqnoma")
    ws.sheet_view.showGridLines = False
    ws.column_dimensions["A"].width = 3
    ws.column_dimensions["B"].width = 22
    ws.column_dimensions["C"].width = 13
    ws.column_dimensions["D"].width = 70
    ws["B2"] = spec["title"]
    ws["B2"].font = Font(bold=True, size=16, color=INK)
    ws["B3"] = "Talaba Ovozi · Ma’lumotlar sahifasiga yuklash uchun"
    ws["B3"].font = Font(size=10, color=MUTED)
    row = 5
    for line in spec["intro"]:
        ws.cell(row=row, column=2, value="•  " + line).alignment = Alignment(wrap_text=True, vertical="top")
        ws.merge_cells(start_row=row, start_column=2, end_row=row, end_column=4)
        ws.row_dimensions[row].height = 30 if len(line) > 95 else 18
        row += 1
    for sheet in spec["sheets"]:
        row += 1
        ws.cell(row=row, column=2, value=f"«{sheet.title}» varag‘i").font = Font(bold=True, size=12, color=ACCENT)
        row += 1
        for i, head in enumerate(("Ustun", "Majburiy", "Izoh"), 2):
            c = ws.cell(row=row, column=i, value=head)
            c.font, c.fill = Font(bold=True, color="FFFFFF"), HEAD_FILL
            c.alignment = Alignment(vertical="center", indent=1)
        row += 1
        for col in sheet.columns:
            ws.cell(row=row, column=2, value=col.header).font = Font(bold=True)
            ws.cell(row=row, column=3, value="ha" if col.required else "—")
            note = ws.cell(row=row, column=4, value=col.note)
            note.alignment = Alignment(wrap_text=True, vertical="top")
            for i in (2, 3, 4):
                ws.cell(row=row, column=i).border = Border(bottom=LINE)
                ws.cell(row=row, column=i).fill = PatternFill("solid", fgColor=SOFT) if col.required else PatternFill()
            ws.row_dimensions[row].height = 30 if len(col.note) > 80 else 18
            row += 1
    row += 1
    ws.cell(row=row, column=2, value="To‘ldirilgan namunani «Namuna» varag‘ida ko‘ring — u yuklanmaydi.").font = Font(
        italic=True, color=MUTED)


def _samples(wb: Workbook, spec: dict) -> None:
    ws = wb.create_sheet("Namuna")
    row = 1
    for sheet in spec["sheets"]:
        if len(spec["sheets"]) > 1:
            ws.cell(row=row, column=1, value=f"«{sheet.title}»").font = Font(bold=True, color=ACCENT)
            row += 1
        for i, col in enumerate(sheet.columns, 1):
            c = ws.cell(row=row, column=i, value=col.header)
            c.font, c.fill = Font(bold=True, color="FFFFFF"), HEAD_FILL
            ws.column_dimensions[get_column_letter(i)].width = max(ws.column_dimensions[get_column_letter(i)].width or 0,
                                                                   col.width)
        for values in sheet.sample:
            row += 1
            for i, v in enumerate(values, 1):
                ws.cell(row=row, column=i, value=v).font = Font(color=MUTED)
        row += 3
    ws.sheet_properties.tabColor = "B4B4BB"


def template_xlsx(kind: str, lists: dict[str, list] | None = None, sample: bool = False) -> BytesIO:
    """The template for `kind`. `lists`: drop-down values from the database (groups, teachers, departments).
    sample=True puts the examples into the sheets to fill in (for tests and demos)."""
    spec = TEMPLATES[kind]
    wb = Workbook()
    ranges = _lists_sheet(wb, {"types": LESSON_TYPES, "days": DAYS, "periods": [1, 2, 3, 4, 5, 6], "weeks": ["A", "B"],
                               **(lists or {})})
    for i, sheet in enumerate(spec["sheets"]):
        _data_sheet(wb, sheet, ranges, first=i == 0)
        if sample:
            ws = wb[sheet.title]
            for r, values in enumerate(sheet.sample, 2):
                for c, v in enumerate(values, 1):
                    ws.cell(row=r, column=c, value=v)
    _guide(wb, spec)
    _samples(wb, spec)
    order = [s.title for s in spec["sheets"]] + ["Yo‘riqnoma", "Namuna", "Ro‘yxatlar"]
    wb._sheets = [wb[name] for name in order]
    wb.active = 0
    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf
