# KI-geschriebene Caption statt Fakten-Wiederholung

## Problem

`build_caption()` (`render.py`) listet ausgewählte Fakten nur als Bullet-Liste unter einer
Standardzeile ("was an diesem Tag geschah") auf. Manuell kuratierte Tage (Browser-UI,
`curate_server.py`) bekommen gar keine Intro. Automatisch kuratierte Tage (`ig-curate.timer` →
`auto_curate.py` → `curate_agent.py`) bekommen nur dann eine echte KI-Intro, wenn
`LLM_API_KEY` gesetzt ist — aktuell nicht der Fall, also läuft `_fallback_curation()`s
Formel-Satz ("Vom Jahr X bis Y: ... Ereignisse, die man kennen sollte."). Ergebnis: die
Caption liest sich wie eine reine Wiederholung der Fakten, nie wie ein geschriebener Text.

## Ziel

Für **jeden** Tag — egal ob manuell oder automatisch kuratiert — schreibt ein LLM eine
inhaltlich verbindende 2-3-Satz-Einleitung basierend auf den final ausgewählten Fakten, bevor
gerendert/gepostet wird. Fällt der LLM-Call aus (kein Key, Netzfehler, API down), degradiert
das System auf die bestehende Formel-Intro — nie ein Blocker für den täglichen Post.

## Architektur

### Neues Modul `caption_agent.py`

- `write_intro(facts: list[dict], api_key: str | None, base_url: str, model: str) -> str`
  Baut aus den übergebenen Fakten (Jahr, `text_de`/`text`) einen Prompt, ruft das LLM auf,
  gibt die geschriebene Einleitung zurück. Bei fehlendem `api_key` oder jedem Fehler
  (Netzwerk, HTTP-Status, Parsing) → Fallback auf `_fallback_intro(facts)` (aus
  `curate_agent._fallback_curation` extrahierte Formel-Logik, dort künftig importiert statt
  dupliziert). Wirft nie eine Exception nach außen.

- `ensure_intro(curate_path: Path) -> None`
  Lädt `curate/YYYY-MM/DD.json`. Wenn `caption_intro` bereits gesetzt und nicht leer: no-op
  (idempotent, kein wiederholter LLM-Call bei erneutem Render). Wenn Datei nicht existiert:
  no-op (silent-skip-Konvention wie überall sonst in der Pipeline). Sonst: `write_intro()`
  aufrufen, Ergebnis zurück ins JSON schreiben.

- CLI-Einstieg: `python3 caption_agent.py curate/2026-08/07.json` → `ensure_intro(...)`.

### LLM-Anbindung: OpenCode Zen, Claude Haiku 4.5

Wiederverwendung der bestehenden `.env`-Variablen `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL`
(gleiche Namen wie `curate_agent.py`, damit es nur eine LLM-Konfiguration im Projekt gibt).

- `LLM_BASE_URL=https://opencode.ai/zen/v1`
- `LLM_MODEL=claude-haiku-4-5`
- `LLM_API_KEY=<echter Key, vom User anzulegen>`

**Wichtig:** Claude-Modelle laufen bei OpenCode Zen über den Anthropic-Messages-Endpoint
(`{base_url}/messages`, Request-Form `{"model", "max_tokens", "messages": [{"role": "user",
"content": ...}]}`, Response `content[0]["text"]`, Auth vermutlich `x-api-key` +
`anthropic-version: 2023-06-01` statt `Authorization: Bearer`) — **nicht** das
OpenAI-Chat-Completions-Format, das `curate_agent.py` für andere Modelle nutzt.
`caption_agent.py` implementiert das Anthropic-Format eigenständig, kein Shared Code mit
`curate_agent._llm_curation`. Der exakte Auth-Header muss beim ersten echten Aufruf mit einem
gültigen Key verifiziert werden (Implementierungsplan sieht dafür einen manuellen Testlauf vor,
bevor der Timer scharf geschaltet wird).

### Pipeline-Integration: `render_today.sh`

Ein Aufruf vor `render.py`, kein neuer systemd-Timer:

```bash
python3 caption_agent.py "curate/$MONTH/$DAY.json"
python3 render.py "curate/$MONTH/$DAY.json"
```

Gilt für beide Kuratierungswege (manuell via UI, automatisch via `ig-curate.timer`), weil
`render_today.sh` so oder so als letzter Schritt vor dem Rendern läuft — unabhängig davon, wie
`curate/*.json` entstanden ist.

### Prompt (Entwurf)

Ähnlich der bestehenden Intro-Anforderung in `curate_agent._build_prompt`, aber ohne
Auswahl-Aufgabe (Fakten stehen schon fest):

> Du bist Redakteur für den deutschen Instagram-History-Account "heute.today". Hier sind die
> für heute ausgewählten historischen Ereignisse: [Jahr + Text je Fakt]. Schreibe eine kurze,
> eingängige Einleitung auf Deutsch (2-3 Sätze), die einen inhaltlichen roten Faden zwischen
> den Ereignissen findet oder eine Gemeinsamkeit/einen Kontrast hervorhebt. Keine reine
> Aufzählung, kein Clickbait. Gib nur den Einleitungstext zurück, sonst nichts.

## Fehlerverhalten

- Kein `LLM_API_KEY` → `write_intro` gibt sofort die Formel-Intro zurück (kein Netzcall).
- LLM-Call schlägt fehl (Timeout, 4xx/5xx, kaputtes JSON) → gleiche Formel-Intro, Fehler nur
  auf stderr geloggt (kein Notify-Mail-Aufwand für eine Qualitäts-Degradation, nicht für einen
  Ausfall — der Post geht trotzdem raus).
- `curate/*.json` fehlt (Tag noch nicht kuratiert) → no-op, wie der Rest der Pipeline.

## Tests

`tests/test_caption_agent.py`:
- `write_intro` mit gemocktem erfolgreichem LLM-Call → gibt den Text aus der Response zurück.
- `write_intro` ohne `api_key` → Formel-Intro, kein HTTP-Call (Mock nie aufgerufen).
- `write_intro` mit HTTP-Fehler/Exception → Formel-Intro.
- `ensure_intro` bei bereits vorhandenem `caption_intro` → Datei unverändert, kein Call.
- `ensure_intro` bei fehlender Datei → no-op, keine Exception.
- `ensure_intro` schreibt `caption_intro` korrekt zurück ins JSON.

`tests/test_render_today.sh`: Ergänzung, dass `caption_agent.py` vor `render.py` mit dem
richtigen Pfad aufgerufen wird (Stub-Erweiterung analog zum bestehenden Muster).

## Out of Scope

- Kein Umbau von `curate_agent.py`s eigener LLM-Auswahl+Intro-Logik (bleibt wie sie ist, betrifft
  nur den reinen Auto-Kuratierungspfad ohne menschliche Auswahl).
- Keine rückwirkende Neu-Generierung von Captions für bereits gepostete Tage.
- Kein Review-Schritt in der Browser-UI, um die generierte Caption vor dem Post zu sehen/zu
  editieren (bewusst nicht gewünscht — läuft komplett automatisch).
