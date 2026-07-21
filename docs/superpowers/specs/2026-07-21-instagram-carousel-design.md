# Instagram Carousel: Design

**Ziel:** Statt einem Bild mit allen Fakten zusammengequetscht wird jeder kuratierte Fakt eine
eigene Bild-Karte. Instagram bekommt weiterhin genau **einen Post pro Tag**, aber als Carousel
mit bis zu 9 Slides (je nach Kuratierungsumfang).

**Nicht-Ziel:** Facebook-Posting (weiterhin Phase 2, keine FB-Seite vorhanden). Kein
automatischer Font-Lizenz-Check über das Herunterladen der Open-Font-License-Dateien hinaus.
Kein Pillow-Fallback — Playwright wird der einzige Rendering-Weg.

## Herkunft des Designs

Templates/Konzept kommen aus einer separaten Claude-Code-Session (Design-Auftrag), Ergebnis
lag als Zip vor: `templates/post_card.html.j2` (Jinja2, ein Aufruf = eine Karte/ein Fakt),
`render_snippet.py` (Playwright-Rendering-Beispiel), `tests/*.html` (Randfälle: langer Fakt,
kurzer Fakt, fehlende Jahreszahl). Stil: dunkles oklch-Blau, Space Grotesk (Jahreszahl,
Wordmark) + Source Sans 3 (Fließtext), radialer Glow-Akzent, dynamische Textgröße nach
Zeichenlänge. Fonts fehlten im Zip — werden als Teil dieser Implementierung besorgt.

## Architektur

`render.py` wird komplett von Pillow auf Jinja2+Playwright umgestellt (kein Pillow-Fallback,
YAGNI — der alte Pfad würde nie mehr benutzt). Pro Tag und pro kuratiertem Fakt wird das
Template einmal gerendert und per Playwright (headless Chromium) als PNG geschossen:

```text
output/<Monat>/<Tag>/01.png, 02.png, ..., NN.png   (ein PNG pro Fakt, Reihenfolge = Kuratierungsreihenfolge)
output/<Monat>/<Tag>/caption.txt                     (unverändert: Liste aller Fakten als Text)
```

`post_today.sh` findet alle `*.png` im Tagesordner (nicht mehr hart `01.png`), committet+pusht
sie zusammen mit `caption.txt`, baut für jedes Bild eine `raw.githubusercontent.com`-URL und
ruft `post_instagram.py` mit der Caption-Datei plus allen Bild-URLs auf.

## Carousel-Posting-Flow (`post_instagram.py`)

Neuer CLI-Vertrag: `python3 post_instagram.py <caption_datei> <url1> [<url2> ... <urlN>]`
(vorher: genau `<image_url> <caption_datei>`, jetzt variable Anzahl URLs, Caption zuerst).

1. **Pro Bild-URL:** Child-Media-Container erstellen —
   `POST /{ig-user-id}/media` mit `image_url`, `is_carousel_item=true`, **kein** `caption`
   (Caption gehört nur auf den Carousel-Container, nicht auf einzelne Slides).
   Schlägt ein Slide fehl: Fehler auf stderr loggen (landet in `journalctl`), **nicht abbrechen**
   — mit den übrigen Slides weitermachen. Bewusste Nutzerentscheidung: lieber ein
   unvollständiges Carousel posten als gar keinen Post an dem Tag.
2. **Nach allen Versuchen, je nach Anzahl erfolgreicher Child-Container:**
   - **≥ 2 erfolgreich:** Carousel-Container erstellen —
     `POST /{ig-user-id}/media` mit `media_type=CAROUSEL`, `children=[creation_id, ...]`,
     `caption=<caption.txt-Inhalt>` — dann `media_publish` wie bisher.
   - **genau 1 erfolgreich:** kein Carousel-Container nötig (Instagram verlangt mindestens 2
     Children pro Carousel). Der bereits erstellte Child-Container kann nicht direkt publiziert
     werden, da er ohne `caption` erstellt wurde (Slides tragen nie eine eigene Caption) — daher
     stattdessen der bestehende Einzelbild-Flow von Grund auf: neuer Media-Container **ohne**
     `is_carousel_item`, dafür **mit** `caption`, dann `media_publish` wie im Phase-1-Code.
   - **0 erfolgreich:** `RuntimeError` — Skript bricht ab, kein Post, `set -e` in `post_today.sh`
     sorgt für sichtbaren Fehler in `journalctl`.

## Fonts

Space Grotesk (500, 700) und Source Sans 3 (400, 600), beide Open Font License, geladen von
`github.com/google/fonts`, liegen als `.woff2` unter `fonts/` im Repo (kein Web-Font-CDN, kein
Internetzugriff zur Render-Zeit nötig — Template referenziert sie relativ per `@font-face`).

## Neue Dependencies

`jinja2`, `playwright` in `requirements.txt`. Einmaliger manueller Schritt auf dem VPS:
`playwright install chromium` (README-Ergänzung, analog zum bisherigen Font-Setup-Hinweis).

## Tests

- **Rendering:** Playwright-Tests laufen mit echtem headless Chromium (kein Mock) — prüfen
  Randfälle aus den mitgelieferten `tests/*.html`: langer Fakt-Text, kurzer Text, fehlende
  Jahreszahl, sowie dass `render.py` für N Fakten genau N PNGs erzeugt.
- **Carousel-API:** wie bisher gemockter `requests.post`, erweitert um: N Child-Container-Calls,
  Carousel-Container-Call mit korrekter `children`-Liste, und alle drei Fallpfade (≥2 / genau 1
  / 0 erfolgreiche Slides).
- **`post_today.sh`:** Stub-Mechanismus erweitert auf variable Bild-Anzahl (Glob über `*.png`
  statt hartkodiertem `01.png`).

## Fehlerverhalten (Ergänzung zur bestehenden Spec)

Teilfehler beim Carousel-Upload brechen den Post nicht ab (siehe oben) — abweichend von der
bisherigen Phase-1-Spec ("kein Post ohne alle Daten"), explizite Nutzerentscheidung für dieses
Feature: mehr Automatisierung, auch mit unvollständigem Ergebnis, ist hier wichtiger als
Vollständigkeit. Alle anderen Fehlerpfade (kein Bild fürs heutige Datum, `git push` schlägt
fehl, 0 erfolgreiche Slides) bleiben wie in der Phase-1-Spec: silent skip bzw. klarer Abbruch,
kein Retry.
