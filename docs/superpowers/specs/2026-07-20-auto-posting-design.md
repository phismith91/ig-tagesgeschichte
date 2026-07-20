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

```
POST https://graph.facebook.com/v21.0/{ig-user-id}/media
  params: image_url=<raw-url>, caption=<caption.txt>, access_token=<token>
  -> { "id": "<creation_id>" }

POST https://graph.facebook.com/v21.0/{ig-user-id}/media_publish
  params: creation_id=<creation_id>, access_token=<token>
  -> { "id": "<media_id>" }
```

## Meta Graph API — Facebook Page

Ein-Schritt (Page-Fotos erlauben URL direkt mit `published=true`):

```
POST https://graph.facebook.com/v21.0/{page-id}/photos
  params: url=<raw-url>, caption=<caption.txt>, published=true, access_token=<page-access-token>
  -> { "id": "<photo_id>", "post_id": "<post_id>" }
```

## Neue `.env`-Variablen

```
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
2. Meta-App auf developers.facebook.com + Produkt "Instagram Graph API"
3. Access-Token generieren (zunächst kurzlebig, dann gegen long-lived tauschen)
4. IDs (`ig-user-id`, `page-id`) über Graph-API-Explorer ermitteln
5. Alle drei Werte in `.env` eintragen

## Nicht-Ziele (explizit)

- Kein automatischer Token-Refresh
- Kein Freigabe-/Review-Schritt vor dem Live-Posten
- Kein Duplikat-Schutz / State-Tracking für bereits geposteter Tage
- Kein Carousel (folgt separat, sobald mehr als 1 Bild/Tag gerendert wird)
