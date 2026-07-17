# Multi-Source-Fetch + Kuratier-Tool

Status: approved
Datum: 2026-07-17

## Ziel

Statt automatisch 3 Wikipedia-Fakten pro Tag zu übernehmen, sollen alle
verfügbaren Kandidaten aus mehreren Quellen gesammelt werden. Der Nutzer
kuratiert die Auswahl selbst über eine Browser-Oberfläche (anklicken statt
Skript entscheidet).

Out of scope für diese Spec: Bild-Rendering, Carousel-Slides, Branding.
`render.py` bleibt vorerst unverändert (altes 1-Bild-Format) und wird in
einer eigenen Spec auf Carousel-Output umgebaut, sobald Kandidaten mit
variabler Anzahl (bis zu 9) unterstützt werden müssen.

## Nicht-Ziele

- Kein automatisches Dedup zwischen Quellen — der Mensch erkennt Duplikate
  beim Klicken selbst, das ist zuverlässiger als Heuristiken.
- Kein Reordering per Drag&Drop im Tool — Klickreihenfolge bestimmt die
  spätere Slide-Reihenfolge; wer umsortieren will, klickt ab und neu an.
- Keine Multi-User-Unterstützung — ein lokaler Server für eine Person.

## Repo-Struktur (Änderungen)

```
fetch_candidates.py     # NEU: 4 Quellen -> candidates/YYYY-MM/DD.json
curate_server.py        # NEU: stdlib http.server, Browser-UI
curate_ui/
  index.html             # NEU
  app.js                 # NEU
  style.css               # NEU
fetch_month.py           # ENTFERNT (Logik geht in fetch_candidates.py auf)
render.py                 # unverändert (konsumiert weiterhin curate/*.json)
.env.example               # NEU: DEEPL_API_KEY=
requirements.txt            # + keine neuen Pflicht-Deps (DeepL via stdlib urllib oder requests, das schon da ist)
```

`candidates/` und `curate/` bleiben wie bisher lokale Datenordner
(candidates/ neu gitignored — reine Rohdaten, regenerierbar; curate/ bleibt
getrackt, das ist der redaktionelle Inhalt).

## 1. fetch_candidates.py

Aufruf: `python3 fetch_candidates.py 2026 8` (Jahr, Monat) — analog zum
bisherigen `fetch_month.py`.

Für jeden Tag des Monats, für jede der 4 Quellen einzeln in try/except
(eine kaputte Quelle darf die anderen 3 nicht verhindern):

1. **Wikipedia** (`de.wikipedia.org/api/rest_v1/feed/onthisday/selected/MM/DD`)
   — wie bisher, aber ungekappt (alle `selected`-Events, nicht nur 3).
2. **Wikidata** (SPARQL-Query auf `query.wikidata.org/sparql`, gefiltert auf
   `MONTH(?date)=MM && DAY(?date)=DD` über P585/P571 o.ä.) — bekannt langsam
   bzw. kann timeouten. Timeout großzügig (30s), bei Fehler/Timeout: Quelle
   für den Tag leer, Warnung auf stdout, weiter im Ablauf.
3. **muffinlabs** (`history.muffinlabs.com/date/MM/DD`) — englisch.
4. **numbersapi** (`numbersapi.com/MM/DD/date`) — englisch, ein Fließtext
   statt Liste, wird als einzelner Kandidat behandelt.

**Übersetzung:** jeder Kandidat, dessen Quelle nicht deutsch ist (muffinlabs,
numbersapi, ggf. Wikidata-Labels), wird zusätzlich per DeepL-API übersetzt.
DeepL-Call ebenfalls try/except-isoliert — schlägt die Übersetzung fehl
(kein Key gesetzt, Kontingent leer, Netzwerkfehler), bleibt `text_de: null`
und die Karte im Tool zeigt den Originaltext mit Sprache-Badge.

DeepL-Key kommt aus `.env` (eigener kleiner Parser, keine neue Dependency —
paar Zeilen `KEY=VALUE`-Parsing reichen, `python-dotenv` wird nicht
gebraucht). `.env` ist gitignored, `.env.example` mit leerem
`DEEPL_API_KEY=` liegt im Repo.

**Schema** `candidates/YYYY-MM/DD.json`:
```json
{
  "date": "2026-07-17",
  "candidates": [
    {
      "id": "wp-0",
      "source": "wikipedia",
      "lang": "de",
      "year": 1976,
      "text": "In der kanadischen Stadt Montreal werden die XXI. Olympischen Sommerspiele eröffnet.",
      "text_de": null,
      "source_url": "https://de.wikipedia.org/wiki/Montreal"
    },
    {
      "id": "ml-2",
      "source": "muffinlabs",
      "lang": "en",
      "year": 1941,
      "text": "Germany invades the Soviet Union...",
      "text_de": "Deutschland fällt in die Sowjetunion ein...",
      "source_url": null
    }
  ]
}
```
`id` ist `<quellen-kürzel>-<index>`, stabil innerhalb eines Fetch-Laufs,
wird von der UI referenziert.

Rate-Limits: gleiche Retry/Backoff-Logik wie bisher (429 → `Retry-After`
abwarten, bis zu 5 Versuche), pro Quelle unabhängig.

## 2. curate_server.py

Start: `python3 curate_server.py [--port 8420]`. Reiner stdlib
`http.server`/`BaseHTTPRequestHandler`, kein Framework.

**Endpoints:**
- `GET /` → liefert `curate_ui/index.html`
- `GET /app.js`, `GET /style.css` → statisch aus `curate_ui/`
- `GET /api/next?month=2026-08` → liefert das nächste Datum im Monat ohne
  vorhandene `curate/YYYY-MM/DD.json` (oder erstes Datum, wenn alle fertig)
- `GET /api/day/2026-08-17` → liest `candidates/2026-08/17.json`, merged mit
  bereits vorhandener `curate/2026-08/17.json` (falls schon mal gespeichert),
  liefert beides ans Frontend
- `POST /api/day/2026-08-17` Body `{"selected_ids": ["wp-0", "ml-2"]}` →
  löst IDs gegen die Kandidatenliste auf (in der übergebenen Reihenfolge =
  Slide-Reihenfolge), schreibt `curate/2026-08/17.json` im bestehenden
  Schema (`{"date": ..., "facts": [...]}`), inkl. `text_de` falls vorhanden

Server validiert serverseitig `len(selected_ids) <= 9` (nicht nur im
Frontend) — 400 Fehler sonst.

## 3. curate_ui/ (Frontend)

Eine Seite, Vanilla JS, kein Build-Step, kein npm.

- Kopfzeile: Datum + Monats-Fortschritt (z. B. „17/31 Tage kuratiert")
- Kandidaten-Karten darunter: Quelle-Badge (Wikipedia/Wikidata/muffinlabs/
  numbersapi), Jahr, Text (übersetzter Text prominent falls vorhanden,
  Original klein darunter), Sprache-Badge falls nicht Deutsch
- Klick auf Karte: toggelt Auswahl, ausgewählte Karten bekommen eine
  Ordnungszahl (1, 2, 3, ...) sichtbar oben links auf der Karte —
  das ist die spätere Slide-Reihenfolge
- Ab 9 ausgewählten Karten: weitere Klicks auf unausgewählte Karten sind
  deaktiviert (visuelles Feedback, kein Fehler-Alert)
- „Speichern & weiter"-Button: `POST /api/day/...`, danach Redirect zu
  `/api/next`-Ergebnis
- Bereits kuratierte Tage bleiben über direkten Aufruf/Navigation erreichbar
  und änderbar — kein Einbahnstraßen-Zwang

## Fehlerbehandlung

- Einzelne Quelle down beim Fetch → Tag bekommt einfach weniger Kandidaten,
  kein Abbruch des gesamten Monats-Laufs
- DeepL down/kein Key → Originaltext bleibt stehen, nichts blockiert
- Kuratier-Server: ungültiges Datum in URL → 404 mit Klartext-Meldung

## Migration

Bestehende `curate/2026-07/*.json` (altes Schema, 3 Fakten, ohne `id`/`lang`/
`text_de`) bleiben unverändert gültig — `render.py` erwartet nur `facts`
mit `year`/`text`, das ist weiterhin erfüllt. Kein Migrations-Skript nötig.
