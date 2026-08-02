#!/usr/bin/env python3
"""curate/YYYY-MM/DD.json -> output/YYYY-MM/DD/01.png..NN.png (ein Bild pro Fakt) + caption.txt

Nutzung:
    python3 render.py curate/2026-08/17.json
    python3 render.py curate/2026-08          # ganzer Monat
"""
import json
import sys
import tempfile
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from playwright.sync_api import sync_playwright

SIZE = 1080
OUT_DIR = Path(__file__).parent / "output"
TEMPLATE_DIR = Path(__file__).parent / "templates"

MONTHS_DE = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli",
             "August", "September", "Oktober", "November", "Dezember"]

_env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))
_template = _env.get_template("post_card.html.j2")


# ponytail: Namensnennung erfüllt die CC-BY-SA-Pflicht von Wikipedia/muffinlabs
# (beide CC BY-SA, Fakten-Text ist ein abgeleitetes Werk der Wikipedia-Sätze).
SOURCE_NAMES = {
    "wikipedia": "Wikipedia",
    "muffinlabs": "history.muffinlabs.com",
    "wikidata": "Wikidata",
    "numbersapi": "numbersapi.com",
}


def build_caption(data: dict) -> str:
    year, month, day = (int(x) for x in data["date"].split("-"))
    intro = data.get("caption_intro", "").strip()

    if intro:
        lines = [f"📅 {day}. {MONTHS_DE[month - 1]} {year}: {intro}", ""]
    else:
        lines = [f"📅 {day}. {MONTHS_DE[month - 1]} {year} — was an diesem Tag geschah:", ""]

    used_sources = []
    for fact in data["facts"]:
        year_label = f"{fact['year']}: " if fact.get("year") else ""
        text = fact.get("text_de") or fact["text"]
        lines.append(f"• {year_label}{text}")
        name = SOURCE_NAMES.get(fact.get("source"))
        if name and name not in used_sources:
            used_sources.append(name)

    lines.append("")
    if used_sources:
        lines.append(f"Quellen: {', '.join(used_sources)} (CC BY-SA)")
    lines.append("#aufdenTag #geschichte #onthisday #wissen")
    return "\n".join(lines)


def render_fact_png(day: str, month: str, fact: dict, index: int, total: int, out_path: Path) -> None:
    html = _template.render(day=day, month=month, fact=fact, index=index, total=total)

    # ponytail: Template referenziert Fonts relativ ("../fonts/..."), das setzt voraus,
    # dass die gerenderte HTML NEBEN dem Template liegt (templates/) — nicht im tief
    # verschachtelten output/<Monat>/<Tag>/. Sonst laden die Fonts lautlos nicht
    # (verifiziert: Font-Status "error", falscher Pfad output/<Monat>/fonts/).
    with tempfile.NamedTemporaryFile(dir=TEMPLATE_DIR, suffix=".html", delete=False) as f:
        tmp_html = Path(f.name)
        f.write(html.encode("utf-8"))

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": SIZE, "height": SIZE}, device_scale_factor=1)
            page.goto(tmp_html.resolve().as_uri())
            page.evaluate("document.fonts.ready")
            page.screenshot(path=str(out_path), clip={"x": 0, "y": 0, "width": SIZE, "height": SIZE})
            browser.close()
    finally:
        tmp_html.unlink()


def render_day(data: dict, out_dir: Path) -> None:
    _, month, day = (int(x) for x in data["date"].split("-"))
    day_dir = out_dir / f"{day:02d}"
    day_dir.mkdir(parents=True, exist_ok=True)

    facts = data["facts"]
    for i, fact in enumerate(facts, start=1):
        render_fact_png(str(day), MONTHS_DE[month - 1], fact, i, len(facts), day_dir / f"{i:02d}.png")

    (day_dir / "caption.txt").write_text(build_caption(data), encoding="utf-8")


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
        print(f"gerendert: {f.name} -> output/{month_key}/{f.stem}/ ({len(data['facts'])} Slides)")


if __name__ == "__main__":
    sys.exit(main())
