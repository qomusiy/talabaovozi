"""Group names: which groups belong to the Economics Faculty, and how to match the same group across sources.

HEMIS and EduPage spell groups differently: "26-01-IQT uz" / "26-01 IQT", "26-03 IQT ru" / "26-03 IQT (ru)".
`group_key` reduces both to "26-01 IQT" - admission year, number and specialty code - which is how groups
are matched everywhere.
"""
import re

from app.config import get_settings

_APOSTROPHES = "'‘’ʻʼ`"
_NAME = re.compile(rf"^\s*(\d{{2}})\s*-\s*(\d+[a-zA-Z]?)[\s-]+([A-Za-z{_APOSTROPHES}]+)")


def _norm_code(code: str) -> str:
    return re.sub(f"[{_APOSTROPHES}\\s]", "", code).upper()


def group_parts(group_name: str) -> tuple[str, str, str] | None:
    """'26-13a BXA (ru)' -> ('26', '13a', 'BXA');  anything that isn't a group name -> None."""
    m = _NAME.match(group_name or "")
    return (m.group(1), m.group(2).lower(), m.group(3)) if m else None


def group_key(group_name: str) -> str | None:
    """'26-01-IQT uz' and '26-01 IQT' -> '26-01 IQT';  "24-20 FTO‘IT" -> '24-20 FTOIT'."""
    parts = group_parts(group_name)
    return f"{parts[0]}-{parts[1].zfill(2) if parts[1].isdigit() else parts[1]} {_norm_code(parts[2])}" if parts else None


def group_code(group_name: str) -> str | None:
    """'25-16 FTO‘IT (ru)' -> 'FTOIT' (for comparisons).  None if the name doesn't look like a group."""
    parts = group_parts(group_name)
    return _norm_code(parts[2]) if parts else None


def display_code(group_name: str) -> str | None:
    """'25-16 FTO‘IT (ru)' -> "FTO'IT" (for showing)."""
    parts = group_parts(group_name)
    return re.sub(f"[{_APOSTROPHES}]", "'", parts[2]).upper() if parts else None


# Specialty codes (as in group names) are kept for data and code; people see these names.
# Keyed by the normalised code (group_code): "FTO‘IT" -> "FTOIT".
SPECIALTY_NAMES: dict[str, dict[str, str]] = {
    "ATT": {"uz": "Axborot tizimlari va texnologiyalari", "en": "Information Systems and Technologies",
            "ru": "Информационные системы и технологии"},
    "BB": {"uz": "Biznesni boshqarish", "en": "Business Management", "ru": "Управление бизнесом"},
    "FTORT": {"uz": "Filologiya va tillarni o‘qitish: rus tili", "en": "Philology and Language Teaching: Russian",
              "ru": "Филология и преподавание языков: русский язык"},
    "FTOIT": {"uz": "Filologiya va tillarni o‘qitish: ingliz tili", "en": "Philology and Language Teaching: English",
              "ru": "Филология и преподавание языков: английский язык"},
    "TUR": {"uz": "Turizm va mehmondo‘stlik", "en": "Tourism and Hospitality", "ru": "Туризм и гостеприимство"},
    "IQT": {"uz": "Iqtisodiyot", "en": "Economics", "ru": "Экономика"},
    "BXA": {"uz": "Buxgalteriya hisobi", "en": "Accounting", "ru": "Бухгалтерский учёт"},
    "STAT": {"uz": "Statistika", "en": "Statistics", "ru": "Статистика"},
}


def specialty_name(code: str | None, lang: str = "uz") -> str:
    """"FTO'IT" -> 'Filologiya va tillarni o‘qitish: ingliz tili'; an unknown code is shown as it is."""
    names = SPECIALTY_NAMES.get(_norm_code(code or ""))
    return (names.get(lang) or names["uz"]) if names else (code or "")


def faculty_codes() -> set[str]:
    return {_norm_code(c) for c in get_settings().faculty_group_codes.split(",") if c.strip()}


def is_faculty_group(group_name: str) -> bool:
    return group_code(group_name) in faculty_codes()
