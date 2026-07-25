# heute.today Robustheit — Design

## Ziel

`heute.today` soll nicht mehr doppelt posten und nicht mehr stumm ausfallen. Jeden Morgen um 06:10 Uhr muss klar sein: entweder wurde gepostet oder es gibt eine verständliche Benachrichtigung mit Fehlergrund.

## Nicht-Ziele

- Keine komplexe Datenbank (bleibt bei JSON-Dateien).
- Kein generisches Notification-Framework für mehrere Kanäle.
- Kein automatisches Repostieren alter Tage.
- Kein Monitoring-UI oder Dashboard.

## Komponenten

### 1. Post-State-Tracking

Jeder erfolgreich gepostete Tag bekommt eine State-Datei:

```
state/posted/2026-07-25.json
```

Inhalt:

```json
{
  "date": "2026-07-25",
  "posted_at": "2026-07-25T06:10:14+00:00",
  "platform": "instagram",
  "media_id": "1234567890",
  "image_urls": [
    "https://raw.githubusercontent.com/.../01.png"
  ]
}
```

`post_today.sh` prüft **vor** Git-Add/Push/API-Call, ob die State-Datei existiert. Falls ja, bricht es mit `exit 0` und Log-Zeile `skip: 2026-07-25 already posted` ab.

State-Dateien werden **nicht** in Git gepusht. Sie sind reiner lokaler Betriebszustand.

### 2. Retry-Logik

`post_instagram.py` bekommt Retry-Logik für retry-fähige Fehler:

- Retry-fähig: Netzwerk-Fehler, Timeouts, HTTP 5xx, Instagram-Status `IN_PROGRESS` dauert länger als erwartet.
- Nicht retry-fähig: HTTP 4xx (Token ungültig, User-ID falsch, Bild-URL nicht erreichbar), Status `EXPIRED`/`ERROR`.

Konfiguration:

- Max. 3 Versuche
- Backoff: 3s, 9s
- Gesamtes Retry-Fenster max. 60s

Wenn ein einzelner Slide in einem Carousel fehlschlägt, wird er weiterhin übersprungen (bestehendes Verhalten). Retries gelten nur für die API-Call-Schicht.

### 3. E-Mail-Benachrichtigungen

Nach jedem Posting-Versuch wird eine E-Mail verschickt — egal ob Erfolg oder Misserfolg.

Empfänger:

```
philippdschmidt@outlook.com
```

Inhalt:

- **Erfolg:** Datum, Media-ID, Anzahl der geposteten Bilder, kurzer Hinweis.
- **Fehler:** Datum, Fehlermeldung, Schritt (`git push`, `media container`, `media_publish`, ...), ob Retries ausgeschöpft wurden.

Versand über SMTP. Neue `.env`-Variablen:

```dotenv
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=...
SMTP_PASSWORD=...
SMTP_FROM=...
NOTIFY_EMAIL_TO=philippdschmidt@outlook.com
```

Wenn SMTP nicht konfiguriert ist, läuft `post_today.sh` trotzdem durch, es gibt nur eine Warnung im Log.

### 4. Health Check

`health_check.py` prüft einmal täglich (eigener Timer, z. B. 02:00 Uhr) oder manuell:

- Kandidaten für die nächsten 7 Tage existieren.
- Kuratierte Dateien für die nächsten 3 Tage existieren.
- Systemd-Timer `ig-fetch`, `ig-curate`, `ig-render`, `ig-post` sind aktiv.
- `.env` enthält alle benötigten Werte (Token, User-ID, SMTP wenn Notifications gewünscht).

Bei Problemen wird eine E-Mail mit konkreter Liste geschickt. Keine E-Mail, wenn alles grün ist.

## Architektur

```
post_today.sh
  ├─ check state/posted/<date>.json
  │   └─ exists → skip
  ├─ git add / commit / push
  ├─ python3 post_instagram.py ...
  │   ├─ retry wrapper
  │   └─ on success → write state
  └─ notify.py success|failure
      └─ send email via SMTP

health_check.py
  ├─ check candidates/curate/state
  ├─ check systemd timers
  ├─ check .env
  └─ notify.py (only on failure)
```

## Dateien

- `state/posted/` — neues Verzeichnis (local, nicht in Git)
- `notify.py` — sendet E-Mails
- `post_instagram.py` — Retry-Logik integrieren
- `post_today.sh` — State-Check + Notification-Aufruf
- `health_check.py` — neues Skript
- `systemd/ig-health.service` und `systemd/ig-health.timer` — täglicher Check
- `.env.example` — SMTP + Notify-Variablen ergänzen
- `.gitignore` — `state/` ignorieren
- Tests:
  - `tests/test_post_state.py`
  - `tests/test_notify.py` (SMTP gemockt)
  - `tests/test_post_instagram_retry.py`
  - `tests/test_health_check.py`

## Fehlerverhalten

| Situation | Verhalten |
|---|---|
| Bereits gepostet | `post_today.sh` bricht still ab |
| Git push fehlschlägt | Retry, dann Failure-E-Mail, kein API-Call |
| Instagram API temporär down | 3 Versuche, dann Failure-E-Mail |
| Token ungültig | Sofort Failure-E-Mail, keine Retries |
| SMTP nicht konfiguriert | Log-Warnung, Posting läuft trotzdem |
| Health Check findet Lücke | E-Mail mit konkreter Fehlerliste |

## Tests

- State-Check: bestehende Datei führt zu Skip.
- Retry: 502-Fehler wird wiederholt, 401-Fehler sofort abgebrochen.
- Notify: SMTP-Transporter wird gemockt, Inhalt enthält Datum und Ergebnis.
- Health Check: fehlende Kandidaten und inaktive Timer erzeugen E-Mail.

## nächster Schritt

Nach Freigabe dieses Designs wird `superpowers:writing-plans` aufgerufen, um einen Implementierungsplan zu erstellen.
