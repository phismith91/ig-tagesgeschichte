# ig-tagesgeschichte

Faceless-Instagram-Channel: täglich 3 historische Ereignisse zum aktuellen Datum,
als fertiges Bild im festen Design + Caption-Text.

## Workflow

1. **Fetch** (einmal pro Monat, im Voraus): zieht Kandidaten von Wikipedia
   ```
   python3 fetch_month.py 2026 8
   ```
   Schreibt `curate/2026-08/01.json` … `31.json` — je 3 Fakten (Jahr, Text, Quelle).

2. **Kuratieren**: die JSON-Dateien in `curate/2026-08/` von Hand durchgehen,
   Texte anpassen/kürzen, schlechte Fakten austauschen. Feld `facts` ist eine
   einfache Liste `{year, text, source_url}` — direkt editierbar.

3. **Rendern**: erzeugt die fertigen Bilder + Captions
   ```
   python3 render.py curate/2026-08          # ganzer Monat
   python3 render.py curate/2026-08/17.json  # einzelner Tag
   ```
   Ergebnis in `output/2026-08/`: `17.png` (1080×1080, postfertig) +
   `17_caption.txt` (Text + Hashtags zum Reinkopieren).

4. **Posten**: manuell, oder mit einem Scheduler (Meta Business Suite, Buffer,
   Later …) — Instagram-Posting selbst ist hier nicht automatisiert.

## Design ändern

Alle visuellen Parameter (Farben, Schriftgrößen, Ränder) stehen oben in
`render.py` als Konstanten (`BG`, `ACCENT`, `TEXT`, `SIZE`, …).

## Setup

```
pip install -r requirements.txt
```
