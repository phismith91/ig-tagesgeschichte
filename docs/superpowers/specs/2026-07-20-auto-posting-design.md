# Auto-Posting (Instagram + Facebook): Design

**Ziel:** Der letzte manuelle Schritt entfällt. Kuratieren im Browser bleibt der einzige menschliche Eingriff — Fetch, Render und jetzt auch das tägliche Posten auf Instagram + Facebook laufen automatisch.

**Nicht-Ziel:** Kein Freigabe-Schritt vor dem Posten — die Kuratierung selbst ist die Freigabe (explizite Nutzerentscheidung). Kein automatischer Access-Token-Refresh (manuell, ~alle 60 Tage, dokumentiert). Kein Carousel (noch 1 Bild/Tag, wie bisher).

## Warum GitHub als Bild-Host

Metas Graph API verlangt für Instagram-Media-Container zwingend eine öffentlich erreichbare **HTTPS**-Bild-URL (kein Datei-Upload, kein `localhost`). Eigene Domain+TLS wollte der Nutzer nicht aufsetzen. Da das Repo ohnehin öffentlich auf GitHub landen soll, dient `raw.githubusercontent.com` als kostenloser, zertifikatsfreier Bild-Host — kein zusätzlicher Account, kein Server, kein DNS.

**Voraussetzung:** GitHub-Repo ist public (bestätigt). `.env` bleibt weiterhin über `.gitignore` ausgeschlossen — Secrets landen nie im Repo.

## Ablauf (täglich, nach dem Rendern)

1. `ig-render.timer` rendert wie bisher `output/<Monat>/<Tag>/01.png` + `caption.txt` um 06:00 (silent skip, falls Tag nicht kuratiert).
2. Neuer `ig-post.timer` läuft 10 Minuten später (06:10) und ruft `post_today.sh` auf:
   - Prüft, ob `output/<Monat>/<Tag>/01.png` existiert (heutiges Datum). Falls nicht: **silent skip**, gleiches Verhalten wie Render bei unkuratierten Tagen.
   - `git add output/ && git commit && git push` (nur falls es Änderungen gibt)
   - Baut die Bild-URL: `https://raw.githubusercontent.com/<user>/<repo>/main/output/<Monat>/<Tag>/01.png`
   - Liest `caption.txt` als Post-Beschreibung
   - Postet via Meta Graph API auf Instagram UND Facebook (siehe unten)

## Meta Graph API — Instagram

Zwei-Schritt-Prozess (Meta-Pflicht, kein Ein-Schritt-Posten möglich):

```http
POST https://graph.facebook.com/v21.0/{ig-user-id}/media
  params: image_url=<raw-url>, caption=<caption.txt>, access_token=<token>
  -> { "id": "<creation_id>" }

POST https://graph.facebook.com/v21.0/{ig-user-id}/media_publish
  params: creation_id=<creation_id>, access_token=<token>
  -> { "id": "<media_id>" }
```

## Meta Graph API — Facebook Page

Ein-Schritt (Page-Fotos erlauben URL direkt mit `published=true`):

```http
POST https://graph.facebook.com/v21.0/{page-id}/photos
  params: url=<raw-url>, caption=<caption.txt>, published=true, access_token=<page-access-token>
  -> { "id": "<photo_id>", "post_id": "<post_id>" }
```

## Neue `.env`-Variablen

```dotenv
META_ACCESS_TOKEN=...      # long-lived Page-Access-Token (~60 Tage gültig)
IG_USER_ID=...             # Instagram Business Account ID
FB_PAGE_ID=...             # Facebook Page ID
```

Alle drei kommen aus dem externen Setup (Facebook-Seite + Meta-App + Token-Generierung), das der Nutzer selbst durchführt — nicht Teil dieses Code-Plans.

## Fehlerverhalten

- **Kein gerendertes Bild für heute:** `post_today.sh` beendet sich still, exit 0 (wie `render_today.sh` bei fehlender Kuratierung).
- **Git push schlägt fehl** (z.B. kein Netz): Skript bricht mit Fehler ab, postet nicht (kein Bild ohne öffentliche URL). Kein Retry — nächster Tag versucht es neu, sichtbar via `journalctl --user -u ig-post`.
- **Meta-API-Call schlägt fehl** (abgelaufener Token, Rate-Limit, ungültige ID): Klarer Fehler in den Logs, kein Retry, kein Absturz des restlichen Systems. Nutzer merkt's spätestens beim nächsten Blick auf den Instagram-Feed und erneuert den Token manuell.
- **Bereits geposteter Tag erneut versucht** (z.B. manueller Re-Run): Kein Duplikat-Schutz in v1 — der Timer läuft nur 1x täglich reguär, ein versehentlicher zweiter manueller Lauf würde doppelt posten. Bewusst kein State-Tracking (YAGNI) — Risiko ist gering (Timer läuft automatisch, manuelles Doppel-Triggern ist eine bewusste Nutzeraktion).

## Vorkuratieren (mehrere Wochen im Voraus)

Kein Sonderfall: `post_today.sh` postet ausschließlich `output/<heutiges Datum>/`, unabhängig davon wie lange dieser Tag schon kuratiert/gerendert vorliegt. Vorkuratieren ändert nichts am Ablauf.

## Setup-Reihenfolge (extern, durch Nutzer)

1. Facebook-Seite anlegen, mit Instagram-Account verknüpfen
2. Meta-App auf developers.facebook.com anlegen, Produkt "Instagram" hinzufügen
   (Berechtigungen: `instagram_basic`, `instagram_content_publish`,
   `pages_show_list`, `pages_read_engagement`, `pages_manage_posts`)
3. Mit dem **Graph API Explorer** (Test-Tool im App-Dashboard, kein eigenes
   Produkt) einen Access-Token generieren und die Berechtigungen zuweisen
4. Token gegen long-lived Version tauschen (kurzlebig → ~60 Tage gültig)
5. IDs (`ig-user-id`, `page-id`) ebenfalls über den Graph API Explorer ermitteln
6. Alle drei Werte in `.env` eintragen

## Phasen-Entscheidung (2026-07-20)

Facebook-Seite ist noch nicht eingerichtet. Erste Implementierung deckt **nur Instagram** ab
(`post_today.sh` postet ausschließlich auf Instagram). Facebook-Teil (Abschnitt "Meta Graph API
— Facebook Page", `FB_PAGE_ID`) folgt als separate Erweiterung, sobald die Seite existiert —
kein Code dafür in dieser Runde.

**Zusätzlich per Live-Setup ermittelt (weicht von ursprünglicher Setup-Reihenfolge oben ab):**
Diese Instagram-App nutzt den neueren "Instagram API"-Flow (Instagram Business Login, nicht
Facebook Login) unter `graph.instagram.com`. Generierter Access-Token war bereits long-lived
(~60 Tage), kein Exchange-Schritt nötig. Die für Graph-Calls relevante ID ist die App-Scoped
User-ID aus `/me` (hier `28194940543437064`) — **nicht** die im Setup-Dashboard angezeigte
klassische Business-Account-ID (`17841449503289529`, altes Facebook-Login-Format). `.env` enthält
bereits `META_ACCESS_TOKEN` + `IG_USER_ID` mit den korrekten Werten.

## Nicht-Ziele (explizit)

- Kein automatischer Token-Refresh
- Kein Freigabe-/Review-Schritt vor dem Live-Posten
- Kein Duplikat-Schutz / State-Tracking für bereits geposteter Tage
- Kein Carousel (folgt separat, sobald mehr als 1 Bild/Tag gerendert wird)
