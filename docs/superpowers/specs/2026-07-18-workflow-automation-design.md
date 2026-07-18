# Workflow-Automatisierung: Design

**Ziel:** Kein manueller `python3 ...`-Aufruf mehr im Alltag. Der einzige verbleibende manuelle Schritt ist die Kuratierung im Browser (Klicks, menschliche Auswahl) sowie das Posten selbst (weiterhin nicht automatisiert, siehe README).

**Architektur:** Drei systemd-`--user`-Units auf dem lokalen Rechner:

1. Ein Dauerdienst für den Kuratier-Server.
2. Ein monatlicher Timer für den Fetch (nächster Monat, Vorlauf).
3. Ein täglicher Timer für den Render (heutiger Tag).

## Komponenten

### 1. `ig-curate-server.service`

Läuft dauerhaft im Hintergrund, startet automatisch nach Boot/Login (vorausgesetzt Linger ist aktiviert, siehe unten).

```ini
[Unit]
Description=ig-tagesgeschichte Kuratier-Server

[Service]
WorkingDirectory=%h/projects/ig-tagesgeschichte
ExecStart=/usr/bin/python3 curate_server.py
Restart=always

[Install]
WantedBy=default.target
```

### 2. `fetch_next_month.sh` (neu)

```bash
#!/bin/bash
# ponytail: date -d "+1 month" statt eigener Jahr/Monat-Rechnung
set -e
cd "$(dirname "$0")"
YEAR=$(date -d "+1 month" +%Y)
MONTH=$(date -d "+1 month" +%-m)
python3 fetch_candidates.py "$YEAR" "$MONTH"
```

### 3. `ig-fetch.service` + `ig-fetch.timer`

```ini
# ig-fetch.service
[Unit]
Description=ig-tagesgeschichte: Kandidaten für nächsten Monat holen

[Service]
Type=oneshot
WorkingDirectory=%h/projects/ig-tagesgeschichte
ExecStart=%h/projects/ig-tagesgeschichte/fetch_next_month.sh
```

```ini
# ig-fetch.timer
[Unit]
Description=Monatlicher Trigger für ig-fetch.service

[Timer]
OnCalendar=*-*-25 03:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

`Persistent=true`: falls der Rechner am 25. aus war, holt systemd den verpassten Lauf beim nächsten Boot nach.

### 4. `render_today.sh` (neu)

```bash
#!/bin/bash
# ponytail: render.py läuft bei fehlendem Einzeltag-Pfad bereits still durch (leerer glob, exit 0) —
# kein Extra-Check nötig, wenn der Tag noch nicht kuratiert ist.
cd "$(dirname "$0")"
python3 render.py "curate/$(date +%Y-%m)/$(date +%d).json"
```

### 5. `ig-render.service` + `ig-render.timer`

```ini
# ig-render.service
[Unit]
Description=ig-tagesgeschichte: heutigen Tag rendern

[Service]
Type=oneshot
WorkingDirectory=%h/projects/ig-tagesgeschichte
ExecStart=%h/projects/ig-tagesgeschichte/render_today.sh
```

```ini
# ig-render.timer
[Unit]
Description=Täglicher Trigger für ig-render.service

[Timer]
OnCalendar=*-*-* 06:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

## Fehlerverhalten

- **Fetch schlägt komplett fehl** (z.B. kein Internet): Service wird von systemd als failed markiert, sichtbar via `journalctl --user -u ig-fetch`. Kein automatischer Retry — nächster reguläter Lauf ist in einem Monat. Bewusst kein Retry-Mechanismus (YAGNI) — bei Bedarf später per `Restart=on-failure` + `RestartSec=` nachrüstbar.
- **Render, Tag noch nicht kuratiert:** `render.py` läuft mit nicht-existierendem Einzeltag-Pfad bereits heute still durch (bestätigt: `src.is_file()` ist `False`, `src.glob("*.json")` auf einem nicht-existierenden Pfad liefert eine leere Liste, Loop tut nichts, exit 0). Kein Code-Fix nötig, kein Fehlerlog, keine Benachrichtigung — der Job holt den Tag beim nächsten Lauf nach, sobald kuratiert wurde.
- **Kuratier-Server crasht:** `Restart=always` startet ihn neu.

## Setup-Voraussetzung

`--user`-Services laufen normalerweise nur, solange eine Login-Session aktiv ist. Damit sie auch nach Logout/Reboot ohne aktive Session weiterlaufen:

```bash
loginctl enable-linger $USER
```

Einmaliger Schritt, kommt als Setup-Anweisung ins README.

## Installation (README-Ergänzung)

```bash
mkdir -p ~/.config/systemd/user
cp systemd/*.service systemd/*.timer ~/.config/systemd/user/
chmod +x fetch_next_month.sh render_today.sh
loginctl enable-linger $USER
systemctl --user daemon-reload
systemctl --user enable --now ig-curate-server.service
systemctl --user enable --now ig-fetch.timer
systemctl --user enable --now ig-render.timer
```

## Testen

- Manueller Trigger: `systemctl --user start ig-fetch.service` bzw. `ig-render.service`
- Log: `journalctl --user -u ig-fetch -f` / `-u ig-render -f` / `-u ig-curate-server -f`
- Timer-Übersicht: `systemctl --user list-timers`

## Nicht-Ziele

- Posten selbst bleibt manuell (unverändert, siehe README).
- Kein Retry-Mechanismus für fehlgeschlagenen Fetch (YAGNI, s.o.).
- Kein Server/VPS-Deployment — läuft explizit nur lokal.
