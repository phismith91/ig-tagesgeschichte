# Instagram Carousel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Jeder Tag wird als ein Instagram-Carousel gepostet (1 Slide pro kuratiertem Fakt, bis
zu 9 Slides) statt als Einzelbild mit allen Fakten zusammengequetscht. Rendering wechselt von
Pillow zu Jinja2+Playwright (echtes HTML/CSS-Design statt Pixel-Zeichnen).

**Architektur:** `render.py` rendert pro Fakt eine eigene 1080×1080-Karte via Playwright-
Screenshot eines Jinja2-Templates → `output/<Monat>/<Tag>/01.png ... NN.png`. `post_today.sh`
findet alle PNGs im Tagesordner statt hartkodiert `01.png`. `post_instagram.py` bekommt einen
Carousel-Flow (Kind-Container pro Slide → Carousel-Container → Publish), mit Fallback auf
Einzelbild-Post falls nur 1 Slide übrig bleibt, und Teilfehler-Toleranz (fehlgeschlagene Slides
werden übersprungen, nicht der ganze Post abgebrochen).

**Tech Stack:** Jinja2 (Templating), Playwright + Chromium (Headless-Screenshot), bestehend:
Python 3, bash, systemd `--user`.

---

## Wichtiger Implementierungs-Fallstrick (bereits verifiziert, nicht neu recherchieren)

Das Template referenziert Fonts relativ: `url('../fonts/SpaceGrotesk-Medium.woff2')` — das
geht davon aus, dass die gerenderte HTML-Datei **neben dem Template** liegt (`templates/`),
sodass `../fonts/` zu `<repo-root>/fonts/` auflöst. Unser `output/<Monat>/<Tag>/`-Ordner liegt
aber **zwei Ebenen tief** unter dem Repo-Root — wird die temporäre Render-HTML dort abgelegt,
löst `../fonts/` fälschlich zu `output/<Monat>/fonts/` auf und die Fonts laden lautlos nicht
(kein Fehler, nur falscher Fallback-Font im Bild). Verifiziert mit echtem Playwright: Fonts
melden Status `"error"`, `requestfailed`-Events zeigen den falschen Pfad.

**Fix (in Task 3 unten bereits eingebaut):** Die temporäre Render-HTML wird immer in
`templates/` selbst geschrieben (per `tempfile.NamedTemporaryFile(dir=TEMPLATE_DIR, ...)`),
egal wohin das fertige PNG am Ende soll. Verifiziert: mit diesem Fix laden alle vier Fonts
korrekt (`"loaded"`, keine `requestfailed`-Events).

## File-Struktur

- `fonts/` (neu) — 4 woff2-Dateien + 2 OFL-Lizenztexte
- `templates/post_card.html.j2` (neu) — Jinja2-Template, unverändert von der Design-Lieferung übernommen
- `render.py` (komplett ersetzt) — Pillow raus, Jinja2+Playwright rein
- `post_instagram.py` (erweitert) — Carousel-Flow zusätzlich zum bestehenden Einzelbild-Flow
- `post_today.sh` (angepasst) — Glob über `*.png` statt hartkodiert `01.png`
- `requirements.txt` (angepasst) — `Pillow` raus, `jinja2` + `playwright` rein
- `README.md` (ergänzt) — `playwright install chromium`-Hinweis

---

### Task 1: Fonts besorgen (Space Grotesk + Source Sans 3 als woff2)

**Files:**
- Create: `fonts/SpaceGrotesk-Medium.woff2`
- Create: `fonts/SpaceGrotesk-Bold.woff2`
- Create: `fonts/SourceSans3-Regular.woff2`
- Create: `fonts/SourceSans3-SemiBold.woff2`
- Create: `fonts/OFL-SpaceGrotesk.txt`
- Create: `fonts/OFL-SourceSans3.txt`

Google Fonts liefert diese Familien nur als **Variable Fonts** (eine Datei mit allen Gewichten),
nicht als separate statische Dateien. Wir müssen sie selbst auf feste Gewichte "instancen" und
zu woff2 konvertieren. Bereits vollständig verifiziert (Downloads funktionieren, Konvertierung
läuft fehlerfrei durch, Ergebnis-Dateien sind gültige woff2s, Playwright lädt sie korrekt).

- [ ] **Step 1: Tools installieren**

```bash
pip install --user --break-system-packages fonttools brotli
```

Erwartet: keine Fehler. (`--break-system-packages` ist auf diesem VPS nötig, da Python
PEP-668-geschützt ist und dieses Projekt schon jetzt ohne venv arbeitet — siehe `requests`/
`Pillow`, die genauso installiert sind.)

- [ ] **Step 2: Variable-Font-Quelldateien laden**

```bash
mkdir -p fonts
cd fonts
curl -sL -o _SpaceGrotesk-var.ttf "https://raw.githubusercontent.com/google/fonts/main/ofl/spacegrotesk/SpaceGrotesk%5Bwght%5D.ttf"
curl -sL -o _SourceSans3-var.ttf "https://raw.githubusercontent.com/google/fonts/main/ofl/sourcesans3/SourceSans3%5Bwght%5D.ttf"
ls -la _*.ttf
```

Erwartet: `_SpaceGrotesk-var.ttf` (~136 KB), `_SourceSans3-var.ttf` (~646 KB).

- [ ] **Step 3: Auf feste Gewichte instancen**

```bash
cd fonts
python3 -m fontTools.varLib.instancer _SpaceGrotesk-var.ttf wght=500 -o _SpaceGrotesk-Medium.ttf
python3 -m fontTools.varLib.instancer _SpaceGrotesk-var.ttf wght=700 -o _SpaceGrotesk-Bold.ttf
python3 -m fontTools.varLib.instancer _SourceSans3-var.ttf wght=400 -o _SourceSans3-Regular.ttf
python3 -m fontTools.varLib.instancer _SourceSans3-var.ttf wght=600 -o _SourceSans3-SemiBold.ttf
```

Erwartet: 4 Zeilen `Saving instance font ...ttf`, evtl. harmlose
`Attempting to fix OTLOffsetOverflowError` Meldungen bei Source Sans 3 (bereits beobachtet,
kein Fehler — die Instanz wird trotzdem korrekt gespeichert).

- [ ] **Step 4: Zu woff2 konvertieren**

```bash
cd fonts
python3 -c "
from fontTools.ttLib import TTFont
for name in ['SpaceGrotesk-Medium', 'SpaceGrotesk-Bold', 'SourceSans3-Regular', 'SourceSans3-SemiBold']:
    font = TTFont(f'_{name}.ttf')
    font.flavor = 'woff2'
    font.save(f'{name}.woff2')
"
ls -la *.woff2
rm _SpaceGrotesk-var.ttf _SourceSans3-var.ttf _SpaceGrotesk-Medium.ttf _SpaceGrotesk-Bold.ttf _SourceSans3-Regular.ttf _SourceSans3-SemiBold.ttf
```

Erwartet: `SpaceGrotesk-Medium.woff2` (~32 KB), `SpaceGrotesk-Bold.woff2` (~31 KB),
`SourceSans3-Regular.woff2` (~103 KB), `SourceSans3-SemiBold.woff2` (~102 KB). Die
Zwischendateien (`_*.ttf`) werden danach gelöscht — nur die woff2s kommen ins Repo.

- [ ] **Step 5: Lizenztexte dazulegen (OFL verlangt das bei Weiterverbreitung)**

```bash
curl -s -o fonts/OFL-SpaceGrotesk.txt "https://raw.githubusercontent.com/google/fonts/main/ofl/spacegrotesk/OFL.txt"
curl -s -o fonts/OFL-SourceSans3.txt "https://raw.githubusercontent.com/google/fonts/main/ofl/sourcesans3/OFL.txt"
```

- [ ] **Step 6: Commit**

```bash
git add fonts/
git commit -m "feat: Space Grotesk + Source Sans 3 als statische woff2 (aus Google-Fonts-Variable-Fonts instanced)"
```

---

### Task 2: Template ins Repo übernehmen

**Files:**
- Create: `templates/post_card.html.j2`

- [ ] **Step 1: Template-Datei anlegen**

```html
<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<title>heute.today — Fakten-Karte</title>
<style>
@font-face{font-family:'Space Grotesk';src:url('../fonts/SpaceGrotesk-Medium.woff2') format('woff2');font-weight:500;font-display:block;}
@font-face{font-family:'Space Grotesk';src:url('../fonts/SpaceGrotesk-Bold.woff2') format('woff2');font-weight:700;font-display:block;}
@font-face{font-family:'Source Sans 3';src:url('../fonts/SourceSans3-Regular.woff2') format('woff2');font-weight:400;font-display:block;}
@font-face{font-family:'Source Sans 3';src:url('../fonts/SourceSans3-SemiBold.woff2') format('woff2');font-weight:600;font-display:block;}
*{margin:0;padding:0;box-sizing:border-box;}
html,body{width:1080px;height:1080px;overflow:hidden;}
body{background:oklch(0.17 0.02 260);font-family:'Source Sans 3',sans-serif;}
</style>
</head>
<body>
{% set raw_text = fact.text %}
{% set len = raw_text|length %}
{% if len > 260 %}{% set fact_text = raw_text[:257] ~ '…' %}{% else %}{% set fact_text = raw_text %}{% endif %}
{% if len <= 70 %}{% set text_size = 64 %}
{% elif len <= 130 %}{% set text_size = 54 %}
{% elif len <= 200 %}{% set text_size = 46 %}
{% else %}{% set text_size = 40 %}
{% endif %}
  <div style="position:relative;width:1080px;height:1080px;overflow:hidden;color:oklch(0.97 0.005 260);">
    <div style="position:absolute;width:900px;height:900px;border-radius:50%;background:radial-gradient(oklch(0.55 0.17 210/0.35),transparent 70%);top:-260px;right:-320px;filter:blur(10px);"></div>
    <div style="position:relative;height:100%;display:flex;flex-direction:column;padding:80px 72px;">
      <div style="font:600 30px 'Source Sans 3',sans-serif;letter-spacing:.1em;text-transform:uppercase;color:oklch(0.75 0.17 210);">{{ day }}. {{ month }}</div>
      {% if fact.year %}
      <div style="font:700 220px/0.95 'Space Grotesk',sans-serif;margin:16px 0 30px;">{{ fact.year }}</div>
      {% else %}
      <div style="height:64px"></div>
      {% endif %}
      <div style="flex:1;display:flex;align-items:center;">
        <p style="font:500 {{ text_size }}px/1.35 'Source Sans 3',sans-serif;margin:0;max-width:880px;text-wrap:pretty;">{{ fact_text }}</p>
      </div>
      <div style="display:flex;justify-content:space-between;align-items:center;border-top:1px solid oklch(1 0 0/0.15);padding-top:28px;">
        <div style="font:700 28px 'Space Grotesk',sans-serif;color:oklch(0.75 0.17 210);">heute.today</div>
        {% if total and total > 1 %}<div style="font:500 24px 'Source Sans 3',sans-serif;color:oklch(0.97 0.005 260/0.6);">{{ index }} / {{ total }}</div>{% endif %}
      </div>
    </div>
  </div>
</body>
</html>
```

- [ ] **Step 2: Commit**

```bash
git add templates/post_card.html.j2
git commit -m "feat: Jinja2-Template für Instagram-Fakten-Karten (Design-Lieferung übernommen)"
```

---

### Task 3: `render.py` auf Jinja2+Playwright umstellen

**Files:**
- Modify: `render.py` (komplett ersetzt)
- Modify: `tests/test_render.py` (komplett ersetzt)
- Modify: `requirements.txt`

- [ ] **Step 1: Dependencies installieren**

```bash
pip install --user --break-system-packages jinja2 playwright
python3 -m playwright install chromium
```

Erwartet: `playwright install chromium` lädt den Chromium-Browser herunter (kann 1-2 Minuten
dauern), keine Fehler am Ende.

- [ ] **Step 2: Neuen Test schreiben (ersetzt kompletten Inhalt von `tests/test_render.py`)**

```python
from pathlib import Path

from render import build_caption, render_day


def test_render_day_writes_one_png_per_fact(tmp_path):
    data = {
        "date": "2026-08-07",
        "facts": [
            {"year": 1926, "text": "Das Planetarium Jena wird eröffnet."},
            {"year": None, "text": "Ein Ereignis ohne bekanntes Jahr."},
            {"year": 1969, "text": "Die Apollo-11-Mission landet als erste bemannte Mission auf dem Mond."},
        ],
    }
    render_day(data, tmp_path)

    day_dir = tmp_path / "07"
    assert (day_dir / "01.png").exists()
    assert (day_dir / "02.png").exists()
    assert (day_dir / "03.png").exists()
    assert not (day_dir / "04.png").exists()

    caption = (day_dir / "caption.txt").read_text(encoding="utf-8")
    assert "1926" in caption
    assert "Planetarium Jena" in caption
    assert "Apollo-11" in caption


def test_render_day_single_fact(tmp_path):
    data = {
        "date": "2026-07-04",
        "facts": [{"year": 1969, "text": "Erste Mondlandung."}],
    }
    render_day(data, tmp_path)

    day_dir = tmp_path / "04"
    assert (day_dir / "01.png").exists()
    assert not (day_dir / "02.png").exists()


def test_build_caption_format():
    data = {
        "date": "2026-08-07",
        "facts": [{"year": 1926, "text": "Das Planetarium Jena wird eröffnet."}],
    }
    caption = build_caption(data)
    assert caption.startswith("📅 7. August 2026")
    assert "• 1926: Das Planetarium Jena wird eröffnet." in caption
    assert caption.endswith("#aufdenTag #geschichte #onthisday #wissen")


def test_render_day_no_leftover_render_html_in_templates_dir():
    # ponytail: die temporäre Render-HTML wird in templates/ geschrieben (Font-Pfad-Fix,
    # siehe Plan-Kopf) — dieser Test stellt sicher, dass sie danach wieder aufgeräumt wird.
    templates_dir = Path(__file__).parent.parent / "templates"
    before = set(templates_dir.glob("*.html"))

    data = {"date": "2026-08-07", "facts": [{"year": 1926, "text": "Test."}]}
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        render_day(data, Path(tmp))

    after = set(templates_dir.glob("*.html"))
    assert before == after
```

- [ ] **Step 3: Test laufen lassen, muss fehlschlagen**

Run: `python3 -m pytest tests/test_render.py -v`
Expected: FAIL (`ImportError: cannot import name 'build_caption' from 'render'` — die Funktion
gibt es in der alten Pillow-Version nicht)

- [ ] **Step 4: `render.py` komplett ersetzen**

```python
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


def build_caption(data: dict) -> str:
    year, month, day = (int(x) for x in data["date"].split("-"))
    lines = [f"📅 {day}. {MONTHS_DE[month - 1]} {year} — was an diesem Tag geschah:", ""]
    for fact in data["facts"]:
        lines.append(f"• {fact['year']}: {fact['text']}")
    lines += ["", "#aufdenTag #geschichte #onthisday #wissen"]
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
```

- [ ] **Step 5: Test laufen lassen, muss passen**

Run: `python3 -m pytest tests/test_render.py -v`
Expected: PASS (4 Tests) — dauert spürbar länger als vorher (~1-3s pro Slide, da echter
Chromium-Start+Screenshot pro Fakt, kein Mock)

- [ ] **Step 6: `requirements.txt` anpassen**

Alter Inhalt:
```
requests
Pillow
```

Neuer Inhalt:
```
requests
jinja2
playwright
```

- [ ] **Step 7: Commit**

```bash
git add render.py tests/test_render.py requirements.txt
git commit -m "feat: render.py auf Jinja2+Playwright umgestellt (1 PNG pro Fakt statt alle in einem Bild)"
```

---

### Task 4: `post_instagram.py` um Carousel-Flow erweitern

**Files:**
- Modify: `post_instagram.py`
- Modify: `tests/test_post_instagram.py`

- [ ] **Step 1: Neue Tests hinzufügen (an bestehende `tests/test_post_instagram.py` anhängen)**

```python
from post_instagram import post_carousel_to_instagram


@patch("post_instagram.requests.post")
def test_post_carousel_with_multiple_slides(mock_post):
    # 3 Kind-Container, dann Carousel-Container, dann Publish
    mock_post.side_effect = [
        MagicMock(status_code=200, json=lambda: {"id": "child-1"}),
        MagicMock(status_code=200, json=lambda: {"id": "child-2"}),
        MagicMock(status_code=200, json=lambda: {"id": "child-3"}),
        MagicMock(status_code=200, json=lambda: {"id": "carousel-container"}),
        MagicMock(status_code=200, json=lambda: {"id": "media-final"}),
    ]

    media_id = post_carousel_to_instagram(
        image_urls=["https://example.com/1.png", "https://example.com/2.png", "https://example.com/3.png"],
        caption="Testcaption",
        ig_user_id="28194940543437064",
        access_token="dummy-token",
    )

    assert media_id == "media-final"
    assert mock_post.call_count == 5

    for i, call in enumerate(mock_post.call_args_list[:3]):
        assert call.args[0] == "https://graph.instagram.com/v21.0/28194940543437064/media"
        assert call.kwargs["data"]["image_url"] == f"https://example.com/{i + 1}.png"
        assert call.kwargs["data"]["is_carousel_item"] == "true"
        assert "caption" not in call.kwargs["data"]

    carousel_call = mock_post.call_args_list[3]
    assert carousel_call.args[0] == "https://graph.instagram.com/v21.0/28194940543437064/media"
    assert carousel_call.kwargs["data"]["media_type"] == "CAROUSEL"
    assert carousel_call.kwargs["data"]["children"] == "child-1,child-2,child-3"
    assert carousel_call.kwargs["data"]["caption"] == "Testcaption"

    publish_call = mock_post.call_args_list[4]
    assert publish_call.args[0] == "https://graph.instagram.com/v21.0/28194940543437064/media_publish"
    assert publish_call.kwargs["data"]["creation_id"] == "carousel-container"


@patch("post_instagram.requests.post")
def test_post_carousel_skips_failed_slide_but_continues(mock_post):
    # Slide 2 schlägt fehl (Kind-Container-Erstellung), Rest läuft normal weiter.
    mock_post.side_effect = [
        MagicMock(status_code=200, json=lambda: {"id": "child-1"}),
        MagicMock(status_code=400, json=lambda: {"error": {"message": "slide 2 broken"}}),
        MagicMock(status_code=200, json=lambda: {"id": "child-3"}),
        MagicMock(status_code=200, json=lambda: {"id": "carousel-container"}),
        MagicMock(status_code=200, json=lambda: {"id": "media-final"}),
    ]

    media_id = post_carousel_to_instagram(
        image_urls=["https://example.com/1.png", "https://example.com/2.png", "https://example.com/3.png"],
        caption="Testcaption",
        ig_user_id="28194940543437064",
        access_token="dummy-token",
    )

    assert media_id == "media-final"
    carousel_call = mock_post.call_args_list[3]
    assert carousel_call.kwargs["data"]["children"] == "child-1,child-3"


@patch("post_instagram.requests.post")
def test_post_carousel_falls_back_to_single_image_when_only_one_slide_succeeds(mock_post):
    # 2 von 3 Kind-Containern schlagen fehl -> nur 1 Slide übrig -> normaler Einzelbild-Post
    # (NICHT der schon erstellte Kind-Container, da der ohne caption erstellt wurde).
    mock_post.side_effect = [
        MagicMock(status_code=200, json=lambda: {"id": "child-1"}),
        MagicMock(status_code=400, json=lambda: {"error": {"message": "broken"}}),
        MagicMock(status_code=400, json=lambda: {"error": {"message": "broken"}}),
        MagicMock(status_code=200, json=lambda: {"id": "single-container"}),
        MagicMock(status_code=200, json=lambda: {"id": "media-final"}),
    ]

    media_id = post_carousel_to_instagram(
        image_urls=["https://example.com/1.png", "https://example.com/2.png", "https://example.com/3.png"],
        caption="Testcaption",
        ig_user_id="28194940543437064",
        access_token="dummy-token",
    )

    assert media_id == "media-final"
    assert mock_post.call_count == 5

    fallback_call = mock_post.call_args_list[3]
    assert fallback_call.kwargs["data"]["image_url"] == "https://example.com/1.png"
    assert fallback_call.kwargs["data"]["caption"] == "Testcaption"
    assert "is_carousel_item" not in fallback_call.kwargs["data"]
    assert "media_type" not in fallback_call.kwargs["data"]


@patch("post_instagram.requests.post")
def test_post_carousel_raises_when_all_slides_fail(mock_post):
    mock_post.side_effect = [
        MagicMock(status_code=400, json=lambda: {"error": {"message": "broken"}}),
        MagicMock(status_code=400, json=lambda: {"error": {"message": "broken"}}),
    ]

    try:
        post_carousel_to_instagram(
            image_urls=["https://example.com/1.png", "https://example.com/2.png"],
            caption="Testcaption",
            ig_user_id="28194940543437064",
            access_token="dummy-token",
        )
        assert False, "sollte RuntimeError werfen"
    except RuntimeError as e:
        assert "kein Slide" in str(e) or "0 von" in str(e)
```

- [ ] **Step 2: Test laufen lassen, muss fehlschlagen**

Run: `python3 -m pytest tests/test_post_instagram.py -v`
Expected: FAIL (`ImportError: cannot import name 'post_carousel_to_instagram'`)

- [ ] **Step 3: `post_instagram.py` um Carousel-Funktionen erweitern**

Ersetze den Abschnitt zwischen `_extract_error()` und `main()` (also alles nach der bestehenden
`_extract_error`-Funktion, vor `def main():`) durch:

```python
def _create_carousel_item(image_url: str, ig_user_id: str, access_token: str) -> str:
    res = requests.post(
        f"{GRAPH_API_BASE}/{ig_user_id}/media",
        data={"image_url": image_url, "is_carousel_item": "true", "access_token": access_token},
        timeout=TIMEOUT_SECONDS,
    )
    if res.status_code != 200:
        raise RuntimeError(f"Carousel-Kind-Container fehlgeschlagen: {_extract_error(res)}")
    return res.json()["id"]


def _create_carousel_container(children: list[str], caption: str, ig_user_id: str, access_token: str) -> str:
    res = requests.post(
        f"{GRAPH_API_BASE}/{ig_user_id}/media",
        data={
            "media_type": "CAROUSEL",
            "children": ",".join(children),
            "caption": caption,
            "access_token": access_token,
        },
        timeout=TIMEOUT_SECONDS,
    )
    if res.status_code != 200:
        raise RuntimeError(f"Carousel-Container fehlgeschlagen: {_extract_error(res)}")
    return res.json()["id"]


def post_carousel_to_instagram(image_urls: list[str], caption: str, ig_user_id: str, access_token: str) -> str:
    children = []
    for image_url in image_urls:
        try:
            children.append(_create_carousel_item(image_url, ig_user_id, access_token))
        except RuntimeError as e:
            print(f"Slide übersprungen ({image_url}): {e}", file=sys.stderr)

    if len(children) == 0:
        raise RuntimeError("Carousel-Post abgebrochen: 0 von {} Slides erfolgreich".format(len(image_urls)))

    if len(children) == 1:
        # ponytail: der schon erstellte Kind-Container hat kein caption (Slides tragen nie
        # eine eigene Caption) und kann nicht direkt publiziert werden — daher normaler
        # Einzelbild-Flow von Grund auf, mit dem Bild, das als einziges durchkam.
        return post_to_instagram(image_urls[0], caption, ig_user_id, access_token)

    carousel_id = _create_carousel_container(children, caption, ig_user_id, access_token)
    return _publish_media(carousel_id, ig_user_id, access_token)
```

Außerdem `import sys` an den Kopf der Datei ergänzen, falls noch nicht vorhanden (ist bereits
vorhanden aus Phase 1 — nur zur Sicherheit prüfen).

- [ ] **Step 4: CLI (`main()`) auf variable Bild-Anzahl umstellen**

Ersetze die bestehende `main()`-Funktion komplett durch:

```python
def main():
    if len(sys.argv) < 3:
        print("Nutzung: python3 post_instagram.py <caption_datei> <url1> [<url2> ...]", file=sys.stderr)
        sys.exit(1)

    with open(sys.argv[1], encoding="utf-8") as f:
        caption = f.read()
    image_urls = sys.argv[2:]

    ig_user_id = load_env_var("IG_USER_ID")
    if not ig_user_id:
        raise RuntimeError("IG_USER_ID fehlt in .env")

    access_token = load_env_var("META_ACCESS_TOKEN")
    if not access_token:
        raise RuntimeError("META_ACCESS_TOKEN fehlt in .env")

    if len(image_urls) == 1:
        media_id = post_to_instagram(image_urls[0], caption, ig_user_id, access_token)
    else:
        media_id = post_carousel_to_instagram(image_urls, caption, ig_user_id, access_token)
    print(f"gepostet: {media_id}")
```

- [ ] **Step 5: Test laufen lassen, muss passen**

Run: `python3 -m pytest tests/test_post_instagram.py -v`
Expected: PASS (alle bisherigen + 4 neuen Tests)

- [ ] **Step 6: Commit**

```bash
git add post_instagram.py tests/test_post_instagram.py
git commit -m "feat: Instagram-Carousel-Flow (Kind-Container + Carousel-Container, Fallback auf Einzelbild bei 1 Slide, Teilfehler-Toleranz)"
```

---

### Task 5: `post_today.sh` auf variable Bild-Anzahl umstellen

**Files:**
- Modify: `post_today.sh`
- Modify: `tests/test_post_today.sh`

- [ ] **Step 1: Test anpassen (kompletter neuer Inhalt von `tests/test_post_today.sh`)**

```bash
#!/bin/bash
# tests/test_post_today.sh
# ponytail: Bash-Test mit Stub-PATH statt echtem git/python3 — testet nur Orchestrierung.
set -e
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$DIR"

TMP=$(mktemp -d)
trap 'rm -rf "$TMP" "$DIR/output/2099-01" "$DIR/output/2099-02" "$DIR/output/2099-03"' EXIT

cat > "$TMP/git" <<'EOF'
#!/bin/bash
echo "git $*" >> "$GIT_CALLS_LOG"
exit 0
EOF
chmod +x "$TMP/git"

cat > "$TMP/python3" <<'EOF'
#!/bin/bash
echo "python3 $*" >> "$PYTHON_CALLS_LOG"
exit 0
EOF
chmod +x "$TMP/python3"

export PATH="$TMP:$PATH"
export GIT_CALLS_LOG="$TMP/git_calls.log"
export PYTHON_CALLS_LOG="$TMP/python_calls.log"
touch "$GIT_CALLS_LOG" "$PYTHON_CALLS_LOG"

# Testfall 1: Tag hat 3 gerenderte Slides -> alle 3 + Caption werden committet/gepusht,
# post_instagram.py bekommt Caption-Pfad zuerst, dann alle 3 URLs.
mkdir -p "output/2099-01/15"
echo "fake1" > "output/2099-01/15/01.png"
echo "fake2" > "output/2099-01/15/02.png"
echo "fake3" > "output/2099-01/15/03.png"
echo "Testcaption" > "output/2099-01/15/caption.txt"

REFERENCE_DATE="2099-01-15" ./post_today.sh

if ! grep -q "add output/2099-01/15/01.png output/2099-01/15/02.png output/2099-01/15/03.png output/2099-01/15/caption.txt" "$GIT_CALLS_LOG"; then
  echo "FAIL: git add wurde nicht mit allen 3 PNGs + Caption aufgerufen"
  cat "$GIT_CALLS_LOG"
  exit 1
fi
if ! grep -q "^git push$" "$GIT_CALLS_LOG"; then
  echo "FAIL: git push wurde nicht aufgerufen"
  exit 1
fi
PYCALL="$(cat "$PYTHON_CALLS_LOG")"
if [[ "$PYCALL" != post_instagram.py\ output/2099-01/15/caption.txt\ *2099-01/15/01.png*2099-01/15/02.png*2099-01/15/03.png ]]; then
  echo "FAIL: post_instagram.py wurde nicht mit caption zuerst + allen 3 URLs aufgerufen"
  echo "GOT: $PYCALL"
  exit 1
fi
rm -rf "output/2099-01"

# Testfall 2: Tag ist NICHT gerendert -> Skript beendet sich still, ruft nichts auf
: > "$GIT_CALLS_LOG"
: > "$PYTHON_CALLS_LOG"
REFERENCE_DATE="2099-02-28" ./post_today.sh
if [ -s "$GIT_CALLS_LOG" ] || [ -s "$PYTHON_CALLS_LOG" ]; then
  echo "FAIL: bei fehlendem Bild dürfen weder git noch python3 aufgerufen werden"
  exit 1
fi

# Testfall 3: "nichts zu committen" darf das Skript NICHT abbrechen (Diff-Guard, siehe
# Commit 47547c1 aus Phase 1 — Regression-Test bleibt relevant, jetzt mit 2 Slides).
cat > "$TMP/git" <<'EOF'
#!/bin/bash
echo "git $*" >> "$GIT_CALLS_LOG"
case "$1" in
  commit) exit 1 ;;
  *) exit 0 ;;
esac
EOF
chmod +x "$TMP/git"

mkdir -p "output/2099-03/01"
echo "fake1" > "output/2099-03/01/01.png"
echo "fake2" > "output/2099-03/01/02.png"
echo "Testcaption" > "output/2099-03/01/caption.txt"
: > "$GIT_CALLS_LOG"
: > "$PYTHON_CALLS_LOG"

RC=0
REFERENCE_DATE="2099-03-01" ./post_today.sh || RC=$?
rm -rf "output/2099-03"

if [ "$RC" -ne 0 ]; then
  echo "FAIL: post_today.sh ist abgebrochen, obwohl 'nichts zu committen' nur den commit betrifft"
  exit 1
fi
if ! grep -q "^git push$" "$GIT_CALLS_LOG"; then
  echo "FAIL: git push wurde trotz No-Op-Commit nicht aufgerufen"
  exit 1
fi
if [ ! -s "$PYTHON_CALLS_LOG" ]; then
  echo "FAIL: post_instagram.py wurde trotz No-Op-Commit nicht aufgerufen"
  exit 1
fi

echo "PASS"
```

- [ ] **Step 2: Test laufen lassen, muss fehlschlagen**

Run: `./tests/test_post_today.sh`
Expected: FAIL (Testfall 1 — `post_today.sh` kennt noch kein Glob über `*.png`, sucht nur `01.png`)

- [ ] **Step 3: `post_today.sh` anpassen**

Kompletter neuer Inhalt:

```bash
#!/bin/bash
# ponytail: gleiches REFERENCE_DATE-Override-Muster wie render_today.sh/fetch_next_month.sh.
set -e
cd "$(dirname "$0")"
REF=${REFERENCE_DATE:-now}

MONTH=$(date -d "$REF" +%Y-%m)
DAY=$(date -d "$REF" +%d)
DAY_DIR="output/$MONTH/$DAY"
CAPTION="$DAY_DIR/caption.txt"

# ponytail: gleiches silent-skip wie render_today.sh — Tag noch nicht kuratiert/gerendert.
if [ ! -f "$CAPTION" ]; then
  exit 0
fi

IMAGES=("$DAY_DIR"/*.png)

git add "${IMAGES[@]}" "$CAPTION"
# ponytail: no-op commit ("nothing to commit") darf das Skript nicht abbrechen —
# sonst kann ein Operator nach fehlgeschlagenem Instagram-Post nicht neu
# anstoßen, wenn der Git-Teil beim ersten Versuch schon durchgelaufen war.
git diff --staged --quiet || git commit -m "post: $MONTH/$DAY"
git push

# ponytail: set -e sorgt dafür, dass ein fehlgeschlagener push hier abbricht —
# kein Post ohne öffentlich erreichbare Bild-URLs.
IMAGE_URLS=()
for img in "${IMAGES[@]}"; do
  IMAGE_URLS+=("https://raw.githubusercontent.com/phismith91/ig-tagesgeschichte/master/$img")
done

python3 post_instagram.py "$CAPTION" "${IMAGE_URLS[@]}"
```

Beachte: der Existenz-Check prüft jetzt `caption.txt` statt `01.png` (Bild-Dateinamen sind nicht
mehr garantiert `01.png` allein — `caption.txt` wird von `render_day()` immer als letztes
geschrieben und existiert genau dann, wenn der Tag vollständig gerendert wurde).

- [ ] **Step 4: Test laufen lassen, muss passen**

Run: `./tests/test_post_today.sh`
Expected: `PASS`

- [ ] **Step 5: Commit**

```bash
git add post_today.sh tests/test_post_today.sh
git commit -m "fix: post_today.sh auf variable Bild-Anzahl umgestellt (Carousel-Unterstützung)"
```

---

### Task 6: README-Ergänzung (Playwright-Setup)

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Hinweis zum Rendern-Abschnitt ergänzen**

Suche den Abschnitt, der das Rendern beschreibt (`python3 render.py ...`), und ergänze direkt
danach:

```markdown
Rendering nutzt Playwright (headless Chromium) statt eines reinen Python-Zeichners — einmaliges
Setup nötig:

```bash
pip install --user --break-system-packages -r requirements.txt
python3 -m playwright install chromium
```
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: Playwright-Setup-Hinweis fürs Rendern ergänzt"
```

---

### Task 7: Finale Prüfung

**Files:** keine Änderungen, nur Verifikation.

- [ ] **Step 1: Komplette Test-Suite laufen lassen**

```bash
python3 -m pytest -q
./tests/test_fetch_next_month.sh
./tests/test_render_today.sh
./tests/test_post_today.sh
```

Expected: alle grün, keine Fehler.

- [ ] **Step 2: Echten Tagesrender + Carousel-API-Aufruf gegen ein Beispiel aus `curate/`
  manuell durchspielen** (nur lokal rendern, NICHT `post_today.sh` ausführen — das würde
  echt auf Instagram posten):

```bash
python3 render.py curate/2026-07/21.json
ls output/2026-07/21/
```

Erwartet: mehrere `NN.png` (eins pro kuratiertem Fakt in `curate/2026-07/21.json`) +
`caption.txt`. Bild(er) stichprobenartig öffnen und prüfen, dass die Fonts korrekt aussehen
(nicht der Browser-Standard-Sans-Fallback) und das Design dem Template entspricht.

---

## Self-Review (durchgeführt)

**Spec-Abdeckung:**
- Fonts besorgen (Space Grotesk + Source Sans 3, OFL) → Task 1 ✅
- Template übernehmen → Task 2 ✅
- render.py komplett auf Jinja2+Playwright, kein Pillow-Fallback → Task 3 ✅
- Carousel-Flow (≥2/genau 1/0 erfolgreiche Slides, Teilfehler-Toleranz) → Task 4 ✅
- post_today.sh variable Bild-Anzahl → Task 5 ✅
- requirements.txt + README (playwright install chromium) → Task 3 Step 6 + Task 6 ✅
- Tests für alle Komponenten → jeweils in den Tasks ✅

**Placeholder-Scan:** keine TBD/TODO gefunden.

**Typkonsistenz:** `post_carousel_to_instagram(image_urls: list[str], caption: str, ig_user_id: str, access_token: str) -> str`
durchgängig in Tests (Task 4) und Implementierung (Task 4) gleich verwendet.
`build_caption(data: dict) -> str` und `render_day(data: dict, out_dir: Path) -> None`
konsistent zwischen Test (Task 3) und Implementierung (Task 3) benutzt. `post_today.sh`s
neuer CLI-Aufruf (`caption_datei` zuerst, dann URLs) stimmt zwischen Task 5 (bash) und
Task 4 (Python `main()`) überein.

**Verifiziert vor Plan-Erstellung (nicht nur angenommen):** Font-Download+Instancing+woff2-
Konvertierung real durchgeführt und funktioniert. Playwright+Chromium real installiert und
getestet. Der Font-Pfad-Fallstrick (temp-HTML-Ablageort) real reproduziert UND der Fix real
verifiziert (Font-Ladestatus vorher `"error"`, nachher `"loaded"`, keine `requestfailed`-
Events mehr). Ein Beispiel-Rendering wurde visuell geprüft (dunkles Design, korrekte Fonts,
Radial-Glow, Jahr/Text/Wordmark korrekt positioniert).
