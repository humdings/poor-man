#!/usr/bin/env python3
"""Draw the static share image from a data snapshot.

The nightly job writes data/og.png beside data/series.json. The page's
Open Graph and Twitter card tags point at that file. No API key, and
nothing is rendered on a server: the PNG is a committed file.

The type is Liberation (SIL Open Font License). See scripts/fonts/COPYRIGHT.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, PngImagePlugin

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from metric import trailing_cpi_half_life  # noqa: E402

FONT_DIR = Path(__file__).resolve().parent / "fonts"
OUT = ROOT / "data" / "og.png"
WIDTH = 1200
HEIGHT = 630

BG = (16, 20, 15)
INK = (243, 239, 228)
MUTED = (163, 156, 140)
GOLD = (228, 177, 90)
LINE = (58, 64, 52)


def format_card_number(value: float) -> str:
    """One decimal, matching the page, with a thousands separator past 999."""
    rounded = round(float(value), 1)
    if abs(rounded) >= 1000:
        return f"{round(rounded):,}"
    return f"{rounded:.1f}"


def card_facts(document: dict) -> dict:
    """Default M2 day count and the latest positive CPI half-life."""
    m2 = next(row for row in document["headlines_default"] if row["id"] == "m2")
    days = m2.get("days")
    half = trailing_cpi_half_life(document["deflators"]["cpi"]["points"])
    latest = next((row for row in reversed(half) if row["years"] is not None), None)
    return {
        "state": m2.get("state"),
        "date": m2.get("date"),
        "days": days,
        "days_label": format_card_number(days) if isinstance(days, (int, float)) else None,
        "half_life": None if latest is None else latest["years"],
        "half_label": None if latest is None else format_card_number(latest["years"]),
        "half_date": None if latest is None else latest["date"],
    }


def _font(filename: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT_DIR / filename), size)


def _fit(draw: ImageDraw.ImageDraw, text: str, filename: str, size: int, max_width: int) -> ImageFont.FreeTypeFont:
    while size > 36:
        font = _font(filename, size)
        if draw.textlength(text, font=font) <= max_width:
            return font
        size -= 4
    return _font(filename, 36)


def write_share_card(document: dict, path: Path = OUT) -> dict:
    """Paint the card and return the facts written into the PNG text chunks."""
    facts = card_facts(document)
    image = Image.new("RGB", (WIDTH, HEIGHT), BG)
    wash = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    ImageDraw.Draw(wash).ellipse((-280, -320, 760, 460), fill=(228, 177, 90, 26))
    image = Image.alpha_composite(image.convert("RGBA"), wash).convert("RGB")
    draw = ImageDraw.Draw(image)

    serif = "LiberationSerif-Bold.ttf"
    sans = "LiberationSans-Regular.ttf"
    sans_bold = "LiberationSans-Bold.ttf"

    word = _font(serif, 42)
    draw.text((68, 48), "Poor Man's Bailout", font=word, fill=GOLD)
    sub = _font(sans, 22)
    draw.text((70, 104), "Days of monetary expansion equal to all of bitcoin.", font=sub, fill=MUTED)
    draw.line((68, 152, WIDTH - 68, 152), fill=LINE, width=2)
    draw.line((WIDTH // 2, 188, WIDTH // 2, 548), fill=LINE, width=2)

    days_text = facts["days_label"] if facts["days_label"] else ("Paused" if facts["state"] == "contracting" else "—")
    half_text = facts["half_label"] if facts["half_label"] else "—"
    _column(
        draw,
        x=68,
        kicker="US M2  ·  12-month trailing",
        number=days_text,
        unit="days" if facts["days_label"] else "",
        caption="One bitcoin market cap\nof monetary expansion.",
        serif=serif,
        sans=sans,
        sans_bold=sans_bold,
    )
    _column(
        draw,
        x=WIDTH // 2 + 48,
        kicker="Dollar half-life",
        number=half_text,
        unit="years" if facts["half_label"] else "",
        caption="Trailing 12-month CPI.\nln(2) / ln(1 + inflation).",
        serif=serif,
        sans=sans,
        sans_bold=sans_bold,
    )

    foot = _font(sans, 20)
    draw.text((68, 574), "humdings.github.io/poor-man", font=foot, fill=MUTED)

    info = PngImagePlugin.PngInfo()
    info.add_text("days", facts["days_label"] or "none")
    info.add_text("half_life", facts["half_label"] or "none")
    info.add_text("headline_date", facts["date"] or "")
    info.add_text("half_date", facts["half_date"] or "")
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, format="PNG", pnginfo=info)
    return facts


def _column(draw, x, kicker, number, unit, caption, serif, sans, sans_bold) -> None:
    label = _font(sans_bold, 22)
    draw.text((x, 196), kicker, font=label, fill=MUTED)
    number_font = _fit(draw, number, serif, 128, 460)
    draw.text((x, 240), number, font=number_font, fill=GOLD)
    if unit:
        unit_font = _font(sans, 28)
        draw.text((x, 392), unit, font=unit_font, fill=INK)
    caption_font = _font(sans, 24)
    draw.multiline_text((x, 448), caption, font=caption_font, fill=MUTED, spacing=6)


def main() -> int:
    document = json.loads((ROOT / "data" / "series.json").read_text(encoding="utf-8"))
    facts = write_share_card(document, OUT)
    print(
        f"Wrote {OUT} ({OUT.stat().st_size} bytes): "
        f"{facts['days_label']} days, half-life {facts['half_label']} years"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
