"""Pictures the bot sends: a group's week as one clean image.

Drawn with Pillow at twice the size and scaled down, so text and rounded corners stay smooth after Telegram
compresses the photo. Portrait and one column: it reads on a phone without zooming sideways.
"""
from dataclasses import dataclass
from functools import lru_cache
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageColor, ImageDraw, ImageFont, features

FONTS = Path(__file__).resolve().parent.parent / "assets" / "fonts"
X = 2                 # drawn at 2x, saved at 1x
WEIGHTS = {"regular": 400, "medium": 500, "semibold": 600, "bold": 700, "extrabold": 800}

# The dashboard's palette (admin.css), so a lesson type has the same colour everywhere.
INK, INK2, MUTED, FAINT = "#111113", "#46464d", "#6b6b73", "#a0a0a8"
BORDER = "#e6e6ea"
TYPE_COLORS = {"lecture": "#5b5bd6", "practice": "#1d9bd1", "seminar": "#d9488b", "lab": "#e0961a", "other": "#8e8e96"}
TYPE_ORDER = ("lecture", "practice", "seminar", "lab", "other")


@lru_cache(maxsize=64)
def font(size: int, weight: str = "regular", family: str = "Inter") -> ImageFont.FreeTypeFont:
    """size in final (1x) pixels."""
    engine = ImageFont.Layout.RAQM if features.check("raqm") else ImageFont.Layout.BASIC
    f = ImageFont.truetype(str(FONTS / f"{family}.ttf"), size * X, layout_engine=engine)
    axes = [WEIGHTS[weight]] if family != "Inter" else [min(32, max(14, size)), WEIGHTS[weight]]  # Inter: opsz, wght
    f.set_variation_by_axes(axes)
    return f


def _w(text: str, f) -> float:
    return f.getlength(text) / X


def wrap(text: str, f, width: float, max_lines: int = 2) -> list[str]:
    """Words into lines no wider than `width`; the last line ends with … if the text doesn't fit."""
    lines, cur = [], ""
    for word in text.split():
        trial = f"{cur} {word}".strip()
        if _w(trial, f) <= width or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        last = lines[-1]
        while last and _w(last + "…", f) > width:
            last = last[:-1].rstrip()
        lines[-1] = last + "…"
    return lines


class Canvas:
    """Coordinates in 1x pixels; everything is drawn at X times the size."""

    def __init__(self, width: int, height: int, bg: str):
        self.img = Image.new("RGB", (width * X, height * X), bg)
        self.d = ImageDraw.Draw(self.img)

    def box(self, x0, y0, x1, y1, fill, radius=0, outline=None, width=1):
        self.d.rounded_rectangle((x0 * X, y0 * X, x1 * X, y1 * X), radius=radius * X, fill=fill,
                                 outline=outline, width=width * X if outline else 0)

    def text(self, x, y, s, f, fill, anchor="la"):
        self.d.text((x * X, y * X), s, font=f, fill=fill, anchor=anchor)

    def line(self, x0, y0, x1, y1, fill, width=1):
        self.d.line((x0 * X, y0 * X, x1 * X, y1 * X), fill=fill, width=width * X)

    def pill(self, x, y, s, f, fg, bg, pad=12, h=34, right=False) -> float:
        """A rounded label; x is its left edge (or right edge if right=True). Returns its width."""
        w = _w(s, f) + 2 * pad
        x0 = x - w if right else x
        self.box(x0, y, x0 + w, y + h, bg, radius=h / 2)
        self.text(x0 + w / 2, y + h / 2, s, f, fg, anchor="mm")
        return w

    def png(self, width: int) -> bytes:
        out = BytesIO()
        img = self.img.resize((width, round(self.img.height * width / self.img.width)), Image.LANCZOS)
        img.save(out, "PNG", optimize=True)
        return out.getvalue()


# ================================================================ Timetable

def _mix(color: str, pct: float, base: str = "#ffffff") -> str:
    """color-mix(in srgb, color pct%, base) - as admin.css tints the lesson cards."""
    a, b = ImageColor.getrgb(color), ImageColor.getrgb(base)
    return "#" + "".join(f"{round(x * pct + y * (1 - pct)):02x}" for x, y in zip(a, b))


SURFACE2 = "#f6f6f8"


@dataclass
class Card:
    """One lesson in a cell, already broken into lines."""
    type: str
    week: str
    subject: list[str]
    meta: list[str]

    @property
    def height(self) -> int:
        return 12 + 18 + 6 + 21 * len(self.subject) + 6 + 19 * len(self.meta) + 10


def timetable_png(*, group: str, about: str, days: list[dict], rows: list[dict], labels: dict, footer: str,
                  out_width: int = 2400) -> bytes:
    """The week as the dashboard draws it: days across, periods down, each lesson a tinted card.

    The whole week, no day marked as today: students save it and look at it every day.
    days: [{"name", "count"}]; rows: [{"n", "start", "end", "cells": [[lesson]], "lunch": "12:20–13:00" | None}],
    lesson: {"subject", "type", "week", "room", "teachers"}; labels: {"title", "lunch", "week_A", "week_B", "room",
    "type_<kind>"}."""
    width, pad, gap, time_w = 1600, 32, 8, 84
    col_w = (width - 2 * pad - time_w - gap * len(days)) / len(days)
    inner = col_w - 2 - 14 - 10          # card text width (border, left bar + padding, right padding)
    f_type, f_week = font(11, "semibold"), font(11, "semibold")
    f_subj, f_meta = font(16, "semibold"), font(14)

    # Lay the cards out first: every row is as tall as its fullest cell.
    laid = []
    for r in rows:
        cells = []
        for lessons in r["cells"]:
            cards = []
            for x in lessons:
                meta = []
                if x["room"]:
                    meta.append(wrap(f"{labels['room']} {x['room']}", f_meta, inner, 1)[0])
                if x["teachers"]:
                    meta.append(wrap(", ".join(x["teachers"]), f_meta, inner, 1)[0])
                cards.append(Card(x["type"], x["week"], wrap(x["subject"], f_subj, inner, 3), meta))
            cells.append(cards)
        need = max([sum(c.height for c in cards) + 6 * max(0, len(cards) - 1) for cards in cells] + [0])
        laid.append((r, cells, max(92, need)))

    head_h, day_h, foot_h = 92, 62, 44
    lunch_h = 34
    height = pad + head_h + day_h + gap + sum(h + gap for _, _, h in laid) \
        + sum(lunch_h for r, _, _ in laid if r["lunch"]) + foot_h
    c = Canvas(width, int(height), "#ffffff")

    # ---- Title and legend
    c.text(pad, pad + 2, labels["title"].upper(), font(13, "semibold"), MUTED)
    c.text(pad, pad + 22, group, font(34, "extrabold", "Manrope"), INK)
    gx = pad + _w(group, font(34, "extrabold", "Manrope")) + 16
    c.text(gx, pad + 44, about, font(16, "medium"), INK2)
    used = [k for k in TYPE_ORDER if any(x.type == k for _, cells, _ in laid for cards in cells for x in cards)]
    x = width - pad
    for k in reversed(used):
        label = labels[f"type_{k}"]
        x -= _w(label, font(15, "medium"))
        c.text(x, pad + 40, label, font(15, "medium"), INK2, anchor="lm")
        x -= 18
        c.box(x, pad + 34, x + 11, pad + 45, TYPE_COLORS[k], radius=2)
        x -= 18

    # ---- Day headers
    y = pad + head_h
    cols = [pad + time_w + gap + i * (col_w + gap) for i in range(len(days))]
    for d, x0 in zip(days, cols):
        c.box(x0, y, x0 + col_w, y + day_h, SURFACE2, radius=10, outline=BORDER)
        c.text(x0 + 14, y + 12, d["name"], font(17, "semibold"), INK)
        c.text(x0 + 14, y + 46, d["count"], font(13, "medium"), MUTED, anchor="lm")
    y += day_h + gap

    # ---- Periods
    for r, cells, h in laid:
        c.text(pad + 6, y + 14, str(r["n"]), font(19, "bold"), INK)
        c.text(pad + 6, y + 42, r["start"], font(14, "medium"), MUTED)
        c.text(pad + 6, y + 61, r["end"], font(14, "medium"), MUTED)
        for x0, cards in zip(cols, cells):
            if not cards:
                c.box(x0, y, x0 + col_w, y + h, SURFACE2, radius=10)
                continue
            cy = y
            for card in cards:
                tint = TYPE_COLORS[card.type]
                c.box(x0, cy, x0 + col_w, cy + card.height, _mix(tint, .06), radius=9,
                      outline=_mix(tint, .22, BORDER), width=1)
                c.box(x0 + 1, cy + 1, x0 + 4, cy + card.height - 1, tint, radius=2)
                tx = x0 + 15
                c.text(tx, cy + 12, labels[f"type_{card.type}"].upper(), f_type, INK2)
                if card.week:
                    c.pill(x0 + col_w - 10, cy + 10, labels[f"week_{card.week}"], f_week, INK2, "#ffffff", pad=7, h=19,
                           right=True)
                ly = cy + 12 + 18 + 6
                for line in card.subject:
                    c.text(tx, ly, line, f_subj, INK)
                    ly += 21
                ly += 6
                for line in card.meta:
                    c.text(tx, ly, line, f_meta, INK2)
                    ly += 19
                cy += card.height + 6
        y += h + gap
        if r["lunch"]:
            text = f"{labels['lunch'].upper()} · {r['lunch']}"
            tw = _w(text, font(13, "semibold"))
            mid = width / 2
            for x0, x1 in ((pad, mid - tw / 2 - 14), (mid + tw / 2 + 14, width - pad)):
                xx = x0
                while xx < x1:
                    c.line(xx, y + lunch_h / 2 - 4, min(xx + 4, x1), y + lunch_h / 2 - 4, "#c8c8ce")
                    xx += 8
            c.text(mid, y + lunch_h / 2 - 4, text, font(13, "semibold"), MUTED, anchor="mm")
            y += lunch_h

    c.text(width / 2, y + foot_h / 2 - 4, footer, font(14, "medium"), FAINT, anchor="mm")
    return c.png(out_width)


class BadImage(ValueError):
    pass


def normalize_photo(data: bytes, max_side: int = 2560) -> bytes:
    """An uploaded picture as a JPEG Telegram accepts as a photo (not too big, not too thin)."""
    try:
        img = Image.open(BytesIO(data))
        img.load()
    except Exception as e:
        raise BadImage(str(e)) from e
    if max(img.size) / max(1, min(img.size)) > 20:
        raise BadImage("too thin")
    img = img.convert("RGB")
    img.thumbnail((max_side, max_side), Image.LANCZOS)
    out = BytesIO()
    img.save(out, "JPEG", quality=90, optimize=True)
    return out.getvalue()
