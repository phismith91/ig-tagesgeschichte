# ig-tagesgeschichte

> This repository is a **channel repo** powered by the
> [`ig-faceless`](https://github.com/phismith91/ig-faceless) framework.
> Channel-specific configuration lives in `config/channel.yaml`.

Faceless-Instagram-Channel: täglich bis zu 9 historische Ereignisse zum aktuellen
Datum, als Instagram-Carousel (ein Bild pro Ereignis) + Caption-Text.

## Setup

```bash
pip install --user --break-system-packages -r requirements.txt
# oder, falls das Framework-Repo lokal vorliegt:
pip install -e /path/to/ig-faceless
python3 -m playwright install chromium
```

Kopiere `.env.example` nach `.env` und fülle die Werte aus:

- `META_ACCESS_TOKEN` — long-lived Instagram-Graph-API-Token
- `IG_USER_ID` — App-Scoped Instagram-User-ID
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`, `SMTP_TO`

## Workflow (mit ig-faceless)

1. **Kandidaten holen** (einmal pro Monat, im Voraus):
   ```bash
   ig-faceless fetch 2026-08-01
   ```
   Schreibt `candidates/2026-08/01.json` … `31.json`.

2. **Kuratieren im Browser**:
   ```bash
   ig-faceless curate
   ```
   Öffnet `http://localhost:8420`, Kandidaten anklicken (max. 9 pro Tag),
   „Speichern & weiter" springt automatisch zum nächsten unkuratierten Tag.
   Die ausgewählten Fakten werden automatisch absteigend nach Jahr sortiert
   gespeichert (neuestes Ereignis zuerst). Schreibt `curate/2026-08/01.json` … `31.json`.

3. **Rendern**: erzeugt die fertigen Bilder + Captions:
   ```bash
   ig-faceless render 2026-08-17
   ```
   Ergebnis in `output/2026-08/17/`: `01.png` … `NN.png` (1080×1080, eins pro
   Fakt, bis zu 9) + `caption.txt`.

4. **Posten**: läuft automatisch als Instagram-Carousel, siehe „Automatisierung".
   Kuratierung ist der einzige manuelle Schritt, danach läuft alles von selbst.

## Automatisierung

Das Framework generiert passende systemd-Units:

```bash
ig-faceless systemd generate > /tmp/ig-faceless-tagesgeschichte.units
```

Die Units landen in `~/.config/systemd/user/` (siehe Framework-Dokumentation).

`loginctl enable-linger $USER` ist nötig, damit die Dienste auch ohne aktive
Login-Session weiterlaufen (z.B. nach Neustart ohne Einloggen).

### Instagram-Posting

Voraussetzung: `.env` enthält `META_ACCESS_TOKEN` und `IG_USER_ID`.
Das Repo muss ein public GitHub-Repo mit Remote `origin` sein — Bilder werden über
`raw.githubusercontent.com` öffentlich gehostet, da die Instagram Graph API eine öffentliche
HTTPS-Bild-URL verlangt (kein Datei-Upload). Kein manueller Freigabe-Schritt — die Kuratierung
selbst ist die Freigabe.

### Robustheit

Das Framework übernimmt:

- State-Tracking der bereits geposteten Tage in `.state/`
- Retry bei temporären Instagram-API-Fehlern
- E-Mail-Benachrichtigungen bei Erfolg oder Fehler
- Tägliche Health-Checks

## Legacy-Scripts

Während der Migration liegen noch die alten Scripts (`fetch_candidates.py`,
`curate_server.py`, `render.py`, `post_instagram.py`, etc.) im Repo. Sie
funktionieren weiterhin, werden aber durch das Framework abgelöst.

## Design ändern

Layout, Farben und Typografie stehen in `templates/post_card.html.j2`
(HTML/CSS, Jinja2-Platzhalter für Tag/Monat/Fakt). Fonts liegen als woff2
unter `fonts/`.
