#!/usr/bin/env python3
"""curate/YYYY-MM/DD.json -> output/YYYY-MM/DD.png + DD_caption.txt

Nutzung:
    python3 render.py curate/2026-08/17.json
    python3 render.py curate/2026-08          # ganzer Monat
"""
import json
import sys
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

SIZE = 1080
BG = (18, 18, 26)
ACCENT = (255, 200, 60)
TEXT = (240, 240, 240)
MUTED = (170, 170, 180)
MARGIN = 80
OUT_DIR = Path(__file__).parent / "output"

MONTHS_DE = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli",
             "August", "September", "Oktober", "November", "Dezember"]


FONT_REGULAR = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(FONT_BOLD if bold else FONT_REGULAR, size)


MAX_LINES_PER_FACT = 3


def wrap(draw: ImageDraw.ImageDraw, text: str, f: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    avg_char_w = draw.textlength("x", font=f) or 10
    chars_per_line = max(10, int(max_width / avg_char_w))
    lines = textwrap.wrap(text, width=chars_per_line)
    if len(lines) > MAX_LINES_PER_FACT:
        lines = lines[:MAX_LINES_PER_FACT]
        lines[-1] = lines[-1].rstrip(".,;: ") + " …"
    return lines


def render_day(data: dict, out_dir: Path) -> None:
    year, month, day = (int(x) for x in data["date"].split("-"))
    img = Image.new("RGB", (SIZE, SIZE), BG)
    draw = ImageDraw.Draw(img)

    f_daynum = font(140, bold=True)
    f_month = font(46)
    f_headline = font(38)
    f_year = font(34, bold=True)
    f_fact = font(30)
    f_footer = font(24)

    y = MARGIN
    draw.text((MARGIN, y), f"{day}.", font=f_daynum, fill=ACCENT)
    daynum_w = draw.textlength(f"{day}.", font=f_daynum)
    draw.text((MARGIN + daynum_w + 20, y + 55), MONTHS_DE[month - 1], font=f_month, fill=TEXT)
    y += 190

    draw.text((MARGIN, y), "Das geschah an diesem Tag", font=f_headline, fill=MUTED)
    y += 70
    draw.line([(MARGIN, y), (SIZE - MARGIN, y)], fill=ACCENT, width=3)
    y += 40

    max_width = SIZE - 2 * MARGIN
    for fact in data["facts"]:
        year_label = str(fact["year"]) if fact.get("year") else ""
        draw.text((MARGIN, y), year_label, font=f_year, fill=ACCENT)
        y += 44
        for line in wrap(draw, fact["text"], f_fact, max_width):
            draw.text((MARGIN, y), line, font=f_fact, fill=TEXT)
            y += 40
        y += 26

    draw.text((MARGIN, SIZE - MARGIN), "@tagesgeschichte", font=f_footer, fill=MUTED)

    out_dir.mkdir(parents=True, exist_ok=True)
    img.save(out_dir / f"{day:02d}.png")

    caption_lines = [f"📅 {day}. {MONTHS_DE[month - 1]} {year} — was an diesem Tag geschah:", ""]
    for fact in data["facts"]:
        caption_lines.append(f"• {fact['year']}: {fact['text']}")
    caption_lines += ["", "#aufdenTag #geschichte #onthisday #wissen"]
    (out_dir / f"{day:02d}_caption.txt").write_text("\n".join(caption_lines), encoding="utf-8")


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        return 1
    src = Path(sys.argv[1])
    files = [src] if src.is_file() else sorted(src.glob("*.json"))
    for f in files:
        data = json.loads(f.read_text(encoding="utf-8"))
        month_key = data["date"][:7]
        render_day(data, OUT_DIR / month_key)
        print(f"gerendert: {f.name} -> output/{month_key}/{f.stem}.png")


if __name__ == "__main__":
    sys.exit(main())
