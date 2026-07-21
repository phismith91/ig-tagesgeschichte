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
   Ergebnis in `output/2026-08/17/`: `01.png` (1080×1080) + `caption.txt`.
   (Aktuell noch 1 Bild pro Tag; ein künftiges Carousel legt weitere Slides
   als `02.png`, `03.png`, … in denselben Tagesordner — kommt als eigene Spec.)

4. **Posten**: manuell, oder mit einem Scheduler (Meta Business Suite, Buffer,
   Later …) — Instagram-Posting selbst ist hier nicht automatisiert.

## Automatisierung (optional)

Fetch, Render und der Kuratier-Server lassen sich als systemd-`--user`-Units
laufen lassen, dann bleibt als manueller Schritt nur noch das Kuratieren im
Browser (Schritt 2). Einmaliges Setup:

```bash
mkdir -p ~/.config/systemd/user
cp systemd/*.service systemd/*.timer ~/.config/systemd/user/
chmod +x fetch_next_month.sh render_today.sh post_today.sh
loginctl enable-linger $USER
systemctl --user daemon-reload
systemctl --user enable --now ig-curate-server.service
systemctl --user enable --now ig-fetch.timer
systemctl --user enable --now ig-render.timer
systemctl --user enable --now ig-post.timer
```

`loginctl enable-linger $USER` ist nötig, damit die Dienste auch ohne aktive
Login-Session weiterlaufen (z.B. nach Neustart ohne Einloggen).

Fetch läuft am 25. jeden Monats (holt den Folgemonat), Render täglich um
06:00 Uhr für den aktuellen Tag — überspringt still, falls der Tag noch
nicht kuratiert wurde. Posten läuft täglich um 06:10 Uhr (10 Minuten nach
dem Rendern) und lädt das Ergebnis automatisch auf Instagram hoch —
überspringt still, falls für heute noch nichts gerendert wurde.

### Instagram-Posting

Voraussetzung: `.env` enthält `META_ACCESS_TOKEN` (long-lived Access-Token) und `IG_USER_ID`
(App-Scoped Instagram-User-ID, siehe Meta-App-Dashboard → Instagram API → Generate access
tokens). Das Repo muss ein public GitHub-Repo mit Remote `origin` sein — Bilder werden über
`raw.githubusercontent.com` öffentlich gehostet, da die Instagram Graph API eine öffentliche
HTTPS-Bild-URL verlangt (kein Datei-Upload). Kein manueller Freigabe-Schritt — die Kuratierung
selbst ist die Freigabe.

Testen / nachschauen:
```bash
systemctl --user start ig-fetch.service      # manuell antriggern
journalctl --user -u ig-fetch -f             # Log verfolgen
systemctl --user list-timers                 # Timer-Übersicht
```

## Design ändern

Alle visuellen Parameter (Farben, Schriftgrößen, Ränder) stehen oben in
`render.py` als Konstanten (`BG`, `ACCENT`, `TEXT`, `SIZE`, …).

## Setup

```
pip install -r requirements.txt
```
