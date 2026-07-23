# Ponytail-Audit-Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Drei Ponytail-Audit-Findings beheben — toten Code entfernen, doppelte .env-Parser-Logik
konsolidieren, String-Dispatch durch direkte Funktionsreferenzen ersetzen. Reines Refactoring,
kein Verhaltensunterschied.

**Architecture:** Drei unabhängige Tasks, je einer pro Finding. Kein gemeinsamer Code-Pfad
zwischen den drei Findings, daher beliebige Reihenfolge möglich — Plan hält die Reihenfolge aus
der Spec bei.

**Tech Stack:** Python 3 (unverändert), keine neuen Dependencies.

---

## Wichtiger Fallstrick bei Task 3 (nicht neu recherchieren, bereits geprüft)

`tests/test_fetch_candidates.py::test_fetch_day_isolates_source_failure` patcht
`sources.fetch_wikipedia` etc. per `monkeypatch.setattr(sources, "fetch_wikipedia", ...)`
**nach** dem Modul-Import. Würde `FETCHERS` als Liste von Funktionsreferenzen auf **Modulebene**
gebaut (`FETCHERS = [sources.fetch_wikipedia, ...]` außerhalb einer Funktion), würden diese
Referenzen beim Import fest gebunden — das Monkeypatching danach hätte keine Wirkung mehr, der
bestehende Test würde brechen (`RuntimeError("down")` aus dem echten `fetch_wikipedia` statt der
gepatchten Lambda-Funktion). Fix: die Funktionsreferenzen-Liste wird **innerhalb** von
`fetch_day()` gebaut (bei jedem Aufruf neu ausgewertet, `sources.fetch_wikipedia` also live
nachgeschlagen), nicht als Modul-Konstante. Siehe Task 3 Step 3 unten — dort exakt so umgesetzt.

## File-Struktur

- `curate_logic.py` (modifiziert) — `next_unfinished_day()` + `_MONTH_RE` raus
- `curate_server.py` (modifiziert) — `/api/next`-Zweig + `parse_qs`-Import raus
- `tests/test_curate_logic.py` (modifiziert) — 4 Tests raus
- `env.py` (neu) — `load_env_var()`, verschoben aus `post_instagram.py`
- `tests/test_env.py` (neu) — Tests, verschoben aus `tests/test_translate.py`
- `post_instagram.py` (modifiziert) — eigene `load_env_var()` raus, Import aus `env.py`
- `translate.py` (modifiziert) — `load_api_key()` raus
- `tests/test_translate.py` (modifiziert) — die 3 `load_api_key`-Tests raus
- `fetch_candidates.py` (modifiziert) — `FETCHER_NAMES`/`getattr` raus, `env.load_env_var` statt `translate.load_api_key`
- `tests/test_fetch_candidates.py` (modifiziert) — `translate.load_api_key`-Monkeypatch auf `env.load_env_var` umgestellt

---

### Task 1: Toten Code entfernen (`next_unfinished_day` + `/api/next`)

**Files:**
- Modify: `curate_logic.py`
- Modify: `curate_server.py`
- Modify: `tests/test_curate_logic.py`

- [ ] **Step 1: Verifizieren, dass wirklich nichts mehr `/api/next` aufruft**

```bash
grep -rn "api/next\|next_unfinished_day" curate_ui/ systemd/ *.sh 2>/dev/null
```

Erwartet: keine Treffer (nur noch in `curate_logic.py`/`curate_server.py`/Tests selbst, die
in diesem Task ohnehin verschwinden).

- [ ] **Step 2: `next_unfinished_day()` + `_MONTH_RE` aus `curate_logic.py` entfernen**

Entferne aus `curate_logic.py`:
1. Die Konstante `_MONTH_RE = re.compile(r"^\d{4}-\d{2}$")` (Zeile 9) — wird nur von
   `next_unfinished_day()` verwendet.
2. Den kompletten Kommentarblock + Funktion `next_unfinished_day()` am Dateiende (die letzten
   ca. 18 Zeilen, vom `# ponytail: von curate_ui/app.js seit 2026-07-19...`-Kommentar bis zum
   Funktionsende).

`_DATE_RE` bleibt (wird von `_day_path()` weiter gebraucht).

- [ ] **Step 3: `/api/next`-Zweig aus `curate_server.py` entfernen**

Entferne aus `do_GET()` den kompletten Block:

```python
        if parsed.path == "/api/next":
            month = parse_qs(parsed.query).get("month", [""])[0]
            try:
                date = curate_logic.next_unfinished_day(CANDIDATES_DIR, CURATE_DIR, month)
            except ValueError as e:
                self._json(400, {"error": str(e)})
                return
            if date is None:
                self._json(404, {"error": f"keine Kandidaten für Monat {month}"})
                return
            self._json(200, {"date": date})
            return
```

Und ändere den Import-Header von:

```python
from urllib.parse import urlparse, parse_qs
```

zu:

```python
from urllib.parse import urlparse
```

(`parse_qs` wurde ausschließlich vom entfernten `/api/next`-Zweig benutzt.)

- [ ] **Step 4: 4 Tests aus `tests/test_curate_logic.py` entfernen**

Entferne diese 4 Testfunktionen komplett:
- `test_next_unfinished_day_skips_curated`
- `test_next_unfinished_day_all_done_returns_first`
- `test_next_unfinished_day_no_candidates_returns_none`
- `test_next_unfinished_day_rejects_bad_month`

Alle anderen Tests (inkl. `_write_candidates`-Hilfsfunktion, die auch von
`test_load_candidates_reads_file` benutzt wird) bleiben unverändert.

- [ ] **Step 5: Tests laufen lassen**

Run: `python3 -m pytest tests/test_curate_logic.py tests/test_curate_server.py -v`
Expected: alle verbleibenden Tests PASS, keine Referenzfehler auf `next_unfinished_day`.

- [ ] **Step 6: Commit**

```bash
git add curate_logic.py curate_server.py tests/test_curate_logic.py
git commit -m "chore: toten next_unfinished_day()/api/next-Code entfernen (ponytail-audit)"
```

---

### Task 2: Gemeinsame `.env`-Lese-Funktion (`env.py`)

**Files:**
- Create: `env.py`
- Create: `tests/test_env.py`
- Modify: `post_instagram.py`
- Modify: `translate.py`
- Modify: `tests/test_translate.py`
- Modify: `fetch_candidates.py` (nur der `load_api_key`-Aufruf, Rest folgt in Task 3)
- Modify: `tests/test_fetch_candidates.py` (nur der `load_api_key`-Monkeypatch)

- [ ] **Step 1: `env.py` anlegen**

```python
"""Liest einzelne Werte aus einer .env-Datei (kein python-dotenv nötig)."""
from pathlib import Path


def load_env_var(key: str, env_path: str = ".env") -> str | None:
    path = Path(env_path)
    if not path.exists():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith(f"{key}="):
            value = line.split("=", 1)[1].strip()
            return value or None
    return None
```

- [ ] **Step 2: `tests/test_env.py` anlegen**

```python
import env


def test_load_env_var_reads_file(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("IG_USER_ID=28194940543437064\nMETA_ACCESS_TOKEN=dummy-token\n")
    monkeypatch.chdir(tmp_path)
    assert env.load_env_var("IG_USER_ID") == "28194940543437064"
    assert env.load_env_var("META_ACCESS_TOKEN") == "dummy-token"


def test_load_env_var_missing_file_returns_none(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert env.load_env_var("IG_USER_ID") is None


def test_load_env_var_missing_key_returns_none(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("SOME_OTHER_KEY=x\n")
    monkeypatch.chdir(tmp_path)
    assert env.load_env_var("IG_USER_ID") is None


def test_load_env_var_empty_value_returns_none(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("IG_USER_ID=\n")
    monkeypatch.chdir(tmp_path)
    assert env.load_env_var("IG_USER_ID") is None
```

- [ ] **Step 3: Test laufen lassen, muss passen (env.py existiert schon aus Step 1)**

Run: `python3 -m pytest tests/test_env.py -v`
Expected: PASS (4 Tests)

- [ ] **Step 4: `post_instagram.py` — eigene `load_env_var()` raus, aus `env.py` importieren**

Entferne aus `post_instagram.py` die komplette Funktion:

```python
def load_env_var(key: str, env_path: str = ".env") -> str | None:
    """Liest einen einzelnen Wert aus einer .env-Datei (kein python-dotenv nötig)."""
    path = Path(env_path)
    if not path.exists():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith(f"{key}="):
            value = line.split("=", 1)[1].strip()
            return value or None
    return None
```

Ändere den Import-Header von:

```python
import sys
from pathlib import Path

import requests
```

zu:

```python
import sys

import requests

from env import load_env_var
```

(`Path` wird nirgendwo sonst in `post_instagram.py` gebraucht — falls doch, `from pathlib import Path` behalten. Prüfen vor dem Entfernen.)

Alle Aufrufstellen von `load_env_var(...)` in `post_instagram.py` (in `main()`) bleiben
unverändert — der Funktionsname ist identisch, nur die Herkunft ändert sich.

- [ ] **Step 5: `tests/test_post_instagram.py` prüfen**

`tests/test_post_instagram.py` enthält 4 Tests, die `post_instagram.load_env_var(...)` direkt
aufrufen (`test_load_env_var_reads_env_file`, `test_load_env_var_missing_file_returns_none`,
`test_load_env_var_missing_key_returns_none`, `test_load_env_var_empty_value_returns_none`).
Da `post_instagram.py` jetzt `from env import load_env_var` macht, ist `post_instagram.load_env_var`
weiterhin gültig (der Name existiert im Modul-Namespace, importiert statt lokal definiert) —
diese Tests sollten unverändert weiter funktionieren. **Nicht ändern, nur verifizieren:**

Run: `python3 -m pytest tests/test_post_instagram.py -v`
Expected: alle Tests PASS (keine Änderung nötig).

- [ ] **Step 6: `translate.py` — `load_api_key()` raus**

Entferne aus `translate.py` die komplette Funktion `load_api_key()` (Zeilen mit `def load_api_key`
bis zum `return None` davor). Entferne auch `from pathlib import Path`, falls `Path` sonst
nirgends in `translate.py` benutzt wird (prüfen).

Neuer Datei-Kopf (Docstring bleibt inhaltlich, nur der Hinweis auf die jetzt fehlende lokale
Funktion entfällt implizit):

```python
"""DeepL-Übersetzung für nicht-deutsche Kandidaten. Key kommt aus .env (Free-Tier, kein python-dotenv nötig).

ponytail: Auth per Header (Authorization: DeepL-Auth-Key ...) statt Body-Parameter —
DeepL hat den Body-Parameter "auth_key" im Nov. 2025 als Legacy-Methode abgeschafft
(https://developers.deepl.com/docs/resources/breaking-changes-change-notices/november-2025-deprecation-of-legacy-auth-methods).
"""
import requests
```

- [ ] **Step 7: `tests/test_translate.py` — die 3 `load_api_key`-Tests raus**

Entferne:
- `test_load_api_key_reads_env_file`
- `test_load_api_key_missing_file_returns_none`
- `test_load_api_key_empty_value_returns_none`

Der `from pathlib import Path`-Import am Dateikopf von `tests/test_translate.py` kann bleiben
oder raus, je nachdem ob er nach dem Entfernen noch gebraucht wird (kurz prüfen — vermutlich
nicht mehr nötig, da nur die entfernten Tests `Path`-artige `tmp_path`-Fixtures nutzten, die
selbst kein `Path`-Import brauchen; `Path` wurde hier nie direkt referenziert, nur importiert —
kann vermutlich ersatzlos raus).

- [ ] **Step 8: `fetch_candidates.py` — Aufruf umstellen**

Ändere in `fetch_candidates.py`:

```python
import sources
import translate
```

zu:

```python
import env
import sources
import translate
```

Und:

```python
    api_key = translate.load_api_key()
```

zu:

```python
    api_key = env.load_env_var("DEEPL_API_KEY")
```

(`translate` bleibt importiert — `translate.translate(...)` wird in `fetch_day()` weiter benutzt.)

- [ ] **Step 9: `tests/test_fetch_candidates.py` — Monkeypatch umstellen**

In `test_main_writes_candidates_file`:

```python
    monkeypatch.setattr(fetch_candidates.translate, "load_api_key", lambda: None)
```

wird zu:

```python
    monkeypatch.setattr(fetch_candidates.env, "load_env_var", lambda key: None)
```

- [ ] **Step 10: Kompletten Testlauf**

Run: `python3 -m pytest -q`
Expected: alle Tests PASS, keine Regressionen.

- [ ] **Step 11: Commit**

```bash
git add env.py tests/test_env.py post_instagram.py translate.py tests/test_translate.py fetch_candidates.py tests/test_fetch_candidates.py
git commit -m "chore: .env-Parser-Logik in env.py konsolidiert, load_api_key()/eigenes load_env_var() entfernt (ponytail-audit)"
```

---

### Task 3: String-Dispatch durch direkte Funktionsreferenzen ersetzen

**Files:**
- Modify: `fetch_candidates.py`

Baut auf Task 2 auf (gleiche Datei) — `import env` aus Task 2 bleibt.

- [ ] **Step 1: `FETCHER_NAMES`-Konstante entfernen**

Entferne die Modul-Konstante:

```python
FETCHER_NAMES = ["fetch_wikipedia", "fetch_wikidata", "fetch_muffinlabs", "fetch_numbersapi"]
```

- [ ] **Step 2: `fetch_day()` auf direkte Funktionsreferenzen umstellen**

Ändere:

```python
def fetch_day(month: int, day: int, api_key: str | None) -> list[dict]:
    candidates = []
    for name in FETCHER_NAMES:
        fetcher = getattr(sources, name)
        try:
            candidates.extend(fetcher(month, day))
        except Exception as e:
            print(f"  {name} fehlgeschlagen: {e}")
    for c in candidates:
        if c["lang"] != "de":
            c["text_de"] = translate.translate(c["text"], c["lang"], api_key)
    return candidates
```

zu:

```python
def fetch_day(month: int, day: int, api_key: str | None) -> list[dict]:
    candidates = []
    # ponytail: Funktionsreferenzen HIER innerhalb der Funktion aufgebaut (nicht als
    # Modul-Konstante) — sonst würde monkeypatch.setattr(sources, "fetch_wikipedia", ...)
    # in Tests wirkungslos, weil eine Modul-Konstante die alte Referenz schon beim Import
    # fest einfrieren würde. So wird sources.fetch_wikipedia bei jedem Aufruf live nachgeschlagen.
    fetchers = (sources.fetch_wikipedia, sources.fetch_wikidata, sources.fetch_muffinlabs, sources.fetch_numbersapi)
    for fetcher in fetchers:
        try:
            candidates.extend(fetcher(month, day))
        except Exception as e:
            print(f"  {fetcher.__name__} fehlgeschlagen: {e}")
    for c in candidates:
        if c["lang"] != "de":
            c["text_de"] = translate.translate(c["text"], c["lang"], api_key)
    return candidates
```

- [ ] **Step 3: Bestehenden Test laufen lassen (prüft genau den Monkeypatch-Fallstrick)**

Run: `python3 -m pytest tests/test_fetch_candidates.py -v`
Expected: PASS, insbesondere `test_fetch_day_isolates_source_failure` (der Test, der
`sources.fetch_wikipedia` monkeypatcht und beweist, dass die gepatchte Version tatsächlich
benutzt wird statt der echten).

- [ ] **Step 4: Kompletten Testlauf**

Run: `python3 -m pytest -q`
Expected: alle Tests PASS.

- [ ] **Step 5: Commit**

```bash
git add fetch_candidates.py
git commit -m "chore: FETCHER_NAMES/getattr-Dispatch durch direkte Funktionsreferenzen ersetzt (ponytail-audit)"
```

---

## Self-Review (durchgeführt)

**Spec-Abdeckung:**
- Finding 1 (toter Code) → Task 1 ✅
- Finding 2 (env.py-Konsolidierung) → Task 2 ✅
- Finding 3 (String-Dispatch) → Task 3 ✅
- Finding 4 (Near-Duplikate post_instagram.py) → bewusst nicht in diesem Plan, wie in Spec festgehalten ✅

**Placeholder-Scan:** keine TBD/TODO gefunden.

**Typkonsistenz:** `load_env_var(key: str, env_path: str = ".env") -> str | None` durchgängig
gleich in `env.py` (Task 2), `post_instagram.py`s Import (Task 2), und allen Aufrufstellen.
`fetch_day(month: int, day: int, api_key: str | None) -> list[dict]`-Signatur unverändert
zwischen Task 2 (Aufrufer in `main()`) und Task 3 (Implementierung selbst).

**Kritischer Punkt eigens verifiziert:** der Monkeypatch-Fallstrick in Task 3 wurde vor
Plan-Erstellung durch Lesen des bestehenden Tests (`test_fetch_day_isolates_source_failure`,
patcht `sources.fetch_wikipedia` nach Import) erkannt und die Lösung (Funktionsreferenzen-Tupel
innerhalb der Funktion statt als Modul-Konstante) entsprechend in Task 3 Step 2 eingebaut —
keine Annahme, sondern am tatsächlichen Testcode nachvollzogen.
