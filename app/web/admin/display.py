"""How the dashboard looks to one person ("Ko‘rinish"): text size, theme, contrast, motion, spacing, links.

Saved with the account (admins.prefs), so it follows the person to another computer or phone, and set on <html>
by the server, so a page never flashes in the wrong size or colours first. admin.css does the rest.
Text sizes follow WCAG 1.4.4 (text can grow without breaking the page); "wider spacing" is WCAG 1.4.12.
"""
from markupsafe import Markup, escape

TEXT_SIZES = (90, 100, 112, 125, 150)   # percent of the normal size
THEMES = ("auto", "light", "dark")
# hide_names: this person's own panel doesn't show who rated (Admin.sees_identity);
# group_numbers: groups show the number students know them by too, "302 · 24-09 BXA (ing)" (Group.number).
DEFAULTS = {"text": 100, "theme": "auto", "contrast": False, "motion": False, "spacing": False, "links": False,
            "hide_names": False, "group_numbers": False}
FLAGS = ("contrast", "motion", "spacing", "links", "hide_names", "group_numbers")


def clean(prefs: dict | None) -> dict:
    p = dict(DEFAULTS)
    for key, value in (prefs or {}).items():
        if key == "text" and str(value).isdigit() and int(value) in TEXT_SIZES:
            p["text"] = int(value)
        elif key == "theme" and value in THEMES:
            p["theme"] = value
        elif key in FLAGS:
            p[key] = value in (True, "true", "1", 1, "on")
    return p


def html_attrs(prefs: dict | None) -> Markup:
    p = clean(prefs)
    attrs = []
    if p["text"] != 100:
        attrs.append(f'data-text="{p["text"]}"')
    if p["theme"] != "auto":
        attrs.append(f'data-theme="{escape(p["theme"])}"')
    attrs += [f'data-{k}' for k in ("contrast", "motion", "spacing", "links") if p[k]]
    return Markup(" ".join(attrs))
