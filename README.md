# ig-tagesgeschichte

Faceless-Instagram-Channel: täglich 3 historische Ereignisse zum aktuellen Datum,
als fertiges Bild im festen Design + Caption-Text.

## Workflow

1. **Kandidaten holen** (einmal pro Monat, im Voraus): zieht Kandidaten aus
   4 Quellen (Wikipedia, Wikidata, muffinlabs, numbersapi), übersetzt
   nicht-deutsche Kandidaten automatisch per DeepL
   ```
   python3 fetch_candidates.py 2026 8
   ```
   Schreibt `candidates/2026-08/01.json` … `31.json`. Braucht `DEEPL_API_KEY`
   in `.env` (Vorlage: `.env.example`), sonst bleiben englische Kandidaten
   unübersetzt.

2. **Kuratieren im Browser**:
   ```
   python3 curate_server.py
   ```
   `http://localhost:8420` öffnen, Kandidaten anklicken (Reihenfolge der
   Klicks = spätere Slide-Reihenfolge, max. 9 pro Tag), „Speichern & weiter"
   springt automatisch zum nächsten unkuratierten Tag. Schreibt
   `curate/2026-08/01.json` … `31.json`.

3. **Rendern**: erzeugt die fertigen Bilder + Captions
   ```
   python3 render.py curate/2026-08          # ganzer Monat
   python3 render.py curate/2026-08/17.json  # einzelner Tag
   ```
   Ergebnis in `output/2026-08/`: `17.png` (1080×1080) + `17_caption.txt`.
   (Aktuell noch 1-Bild-Format; Carousel-Rendering mit einem Slide pro
   kuratiertem Event kommt als eigene Spec.)

4. **Posten**: manuell, oder mit einem Scheduler (Meta Business Suite, Buffer,
   Later …) — Instagram-Posting selbst ist hier nicht automatisiert.

## Design ändern

Alle visuellen Parameter (Farben, Schriftgrößen, Ränder) stehen oben in
`render.py` als Konstanten (`BG`, `ACCENT`, `TEXT`, `SIZE`, …).

## Setup

```
pip install -r requirements.txt
```
