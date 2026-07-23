# Ponytail-Audit-Cleanup: Design

**Ziel:** Drei Findings aus dem Repo-weiten `/ponytail-audit` beheben — toten Code entfernen,
doppelte .env-Parser-Logik konsolidieren, String-Dispatch durch direkte Funktionsreferenzen
ersetzen. Reines Refactoring, keine neue Funktionalität, kein Verhaltensunterschied für
Nutzer:innen.

**Nicht-Ziel:** Das 4. Audit-Finding (`_create_media_container()`/`_create_carousel_item()`
Near-Duplikate in `post_instagram.py`) wird bewusst nicht angefasst — bei 2 Aufrufstellen kein
harter Cut, nur vorgemerkt für den Fall einer dritten Variante.

## 1. Toten Code entfernen

`next_unfinished_day()` (`curate_logic.py`) und der `/api/next`-Endpoint (`curate_server.py`)
werden seit dem Nav-Redesign (◀/▶/Heute-Buttons in `curate_ui/app.js`) von keinem Client-Code
mehr aufgerufen — verifiziert per `grep` über `curate_ui/*.js`, keine Treffer. Werden entfernt:

- `curate_logic.py`: Funktion `next_unfinished_day()` (Zeilen 59-72) und die zugehörige
  `_MONTH_RE`-Konstante, falls sie nach dem Entfernen keine andere Verwendung mehr hat (wird
  in der Implementierung geprüft, nicht blind mitgelöscht).
- `curate_server.py`: der `if parsed.path == "/api/next":`-Zweig in `do_GET()`.
- `tests/test_curate_logic.py`: die 4 Tests, die ausschließlich `next_unfinished_day()` testen.

## 2. Gemeinsame .env-Lese-Funktion

Neues Modul `env.py` (Repo-Root, neben den anderen Top-Level-Modulen wie `translate.py`,
`sources.py`) mit genau einer Funktion:

```python
def load_env_var(key: str, env_path: str = ".env") -> str | None:
```

Identisch zur bestehenden Implementierung in `post_instagram.py` (Zeilen 12-21) — die wird
nach `env.py` verschoben. `post_instagram.py` und `translate.py` importieren `load_env_var`
aus `env.py` statt eigener Implementierung. `translate.py`s `load_api_key()` entfällt komplett,
Aufrufer (`fetch_candidates.py`) ruft direkt `env.load_env_var("DEEPL_API_KEY")` statt
`translate.load_api_key()`.

## 3. String-Dispatch durch direkte Referenzen ersetzen

`fetch_candidates.py`: `FETCHER_NAMES = ["fetch_wikipedia", ...]` + `getattr(sources, name)`
wird zu einer direkten Liste von Funktionsreferenzen:

```python
FETCHERS = [sources.fetch_wikipedia, sources.fetch_wikidata, sources.fetch_muffinlabs, sources.fetch_numbersapi]
```

`fetch_day()` iteriert direkt über `FETCHERS` (Funktionsobjekte statt Namen), kein `getattr`
mehr nötig. Die Fehlerbehandlung pro Fetcher (`try/except` mit `fetcher.__name__` fürs Logging)
bleibt inhaltlich gleich, nutzt aber `fetcher.__name__` statt der vorherigen `name`-Variable.

## Tests

Bestehende Tests für `translate.py` (`load_api_key`) wandern sinngemäß nach `tests/test_env.py`
für `env.load_env_var()` — Testfälle bleiben inhaltlich identisch (Datei fehlt, Key fehlt,
leerer Wert, Wert vorhanden), nur der Funktionsname/Import ändert sich. Kein neuer Testbedarf
für Punkt 1 (Löschen) oder Punkt 3 (Dispatch-Vereinfachung) über die bestehende
`fetch_candidates`-Testabdeckung hinaus — `fetch_day()`s bestehende Tests (falls vorhanden)
müssen weiter grün sein.

## Fehlerverhalten

Unverändert — dieses Cleanup ändert kein beobachtbares Verhalten, nur interne Struktur.
