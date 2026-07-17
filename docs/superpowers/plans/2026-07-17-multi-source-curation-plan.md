# Multi-Source-Fetch + Kuratier-Tool Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Vier Quellen (Wikipedia, Wikidata, muffinlabs, numbersapi) liefern rohe Tages-Kandidaten; ein lokales Browser-Tool lässt den Nutzer per Klick auswählen; die Auswahl landet im bestehenden `curate/YYYY-MM/DD.json`-Schema.

**Architecture:** Drei unabhängige Stufen, jede eine reine Datei-zu-Datei- bzw. Datei-zu-HTTP-Transformation: `fetch_candidates.py` (Netzwerk → `candidates/*.json`), `curate_server.py` + `curate_ui/` (Browser-Klicks → `curate/*.json`), `render.py` (unverändert, konsumiert `curate/*.json` weiter). Geschäftslogik pro Stufe liegt in eigenständigen, netzwerkfreien Modulen (`sources.py`, `translate.py`, `curate_logic.py`) — testbar ohne echte HTTP-Calls.

**Tech Stack:** Python 3, `requests` (schon vorhanden), stdlib `http.server` fürs Tool, Vanilla-JS-Frontend ohne Build-Step, DeepL API Free für Übersetzung, pytest für Tests.

Spec: `docs/superpowers/specs/2026-07-17-multi-source-curation-design.md`

---

## Vorbereitung

Alle folgenden Tasks setzen voraus, dass im Projektroot `/home/philipp/projects/ig-tagesgeschichte` gearbeitet wird, auf Branch `feature/multi-source-curation` (bereits ausgecheckt).

---

### Task 1: `.env`-Loader + DeepL-Übersetzung (`translate.py`)

**Files:**
- Create: `translate.py`
- Create: `tests/test_translate.py`
- Create: `.env.example`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_translate.py
from pathlib import Path

import translate


def test_load_api_key_reads_env_file(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("DEEPL_API_KEY=abc123:fx\n")
    monkeypatch.chdir(tmp_path)
    assert translate.load_api_key() == "abc123:fx"


def test_load_api_key_missing_file_returns_none(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert translate.load_api_key() is None


def test_load_api_key_empty_value_returns_none(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("DEEPL_API_KEY=\n")
    monkeypatch.chdir(tmp_path)
    assert translate.load_api_key() is None


def test_deepl_endpoint_free_key():
    assert translate.deepl_endpoint("abc123:fx") == "https://api-free.deepl.com/v2/translate"


def test_deepl_endpoint_pro_key():
    assert translate.deepl_endpoint("abc123") == "https://api.deepl.com/v2/translate"


def test_translate_returns_none_without_key():
    assert translate.translate("hello", "en", None) is None


def test_translate_calls_correct_endpoint(monkeypatch):
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"translations": [{"text": "hallo"}]}

    def fake_post(url, data=None, timeout=None):
        captured["url"] = url
        captured["data"] = data
        return FakeResponse()

    monkeypatch.setattr(translate.requests, "post", fake_post)
    result = translate.translate("hello", "en", "abc123:fx")
    assert result == "hallo"
    assert captured["url"] == "https://api-free.deepl.com/v2/translate"
    assert captured["data"]["text"] == "hello"
    assert captured["data"]["source_lang"] == "EN"
    assert captured["data"]["target_lang"] == "DE"


def test_translate_returns_none_on_error(monkeypatch):
    def fake_post(url, data=None, timeout=None):
        raise ConnectionError("down")

    monkeypatch.setattr(translate.requests, "post", fake_post)
    result = translate.translate("hello", "en", "abc123:fx")
    assert result is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_translate.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'translate'`

- [ ] **Step 3: Write `translate.py`**

```python
"""DeepL-Übersetzung für nicht-deutsche Kandidaten. Key kommt aus .env (Free-Tier, kein python-dotenv nötig)."""
from pathlib import Path

import requests


def load_api_key(env_path: str = ".env") -> str | None:
    path = Path(env_path)
    if not path.exists():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("DEEPL_API_KEY="):
            value = line.split("=", 1)[1].strip()
            return value or None
    return None


def deepl_endpoint(api_key: str) -> str:
    host = "api-free.deepl.com" if api_key.endswith(":fx") else "api.deepl.com"
    return f"https://{host}/v2/translate"


def translate(text: str, source_lang: str, api_key: str | None) -> str | None:
    if not api_key:
        return None
    try:
        resp = requests.post(
            deepl_endpoint(api_key),
            data={
                "auth_key": api_key,
                "text": text,
                "source_lang": source_lang.upper(),
                "target_lang": "DE",
            },
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()["translations"][0]["text"]
    except Exception as e:
        print(f"  DeepL-Übersetzung fehlgeschlagen: {e}")
        return None
```

- [ ] **Step 4: Create `.env.example`**

```
DEEPL_API_KEY=
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_translate.py -v`
Expected: `7 passed`

- [ ] **Step 6: Commit**

```bash
git add translate.py tests/test_translate.py .env.example
git commit -m "feat: DeepL-Free-Tier-Übersetzung mit .env-Loader"
```

---

### Task 2: Gemeinsamer Retry-Helper (`sources.py` Grundgerüst)

**Files:**
- Create: `sources.py`
- Create: `tests/test_sources.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_sources.py
import sources


class FakeResponse:
    def __init__(self, status_code=200, json_data=None, headers=None):
        self.status_code = status_code
        self._json = json_data or {}
        self.headers = headers or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._json


def test_get_with_retry_returns_response_on_200(monkeypatch):
    def fake_get(url, timeout=15, **kwargs):
        return FakeResponse(200, {"ok": True})

    monkeypatch.setattr(sources.requests, "get", fake_get)
    resp = sources.get_with_retry("https://example.com")
    assert resp.json() == {"ok": True}


def test_get_with_retry_retries_on_429(monkeypatch):
    calls = []

    def fake_get(url, timeout=15, **kwargs):
        calls.append(1)
        if len(calls) == 1:
            return FakeResponse(429, headers={"Retry-After": "0"})
        return FakeResponse(200, {"ok": True})

    monkeypatch.setattr(sources.requests, "get", fake_get)
    monkeypatch.setattr(sources.time, "sleep", lambda s: None)
    resp = sources.get_with_retry("https://example.com")
    assert resp.json() == {"ok": True}
    assert len(calls) == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_sources.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'sources'`

- [ ] **Step 3: Write `sources.py` (Grundgerüst mit Retry-Helper)**

```python
"""Kandidaten-Fetcher für 4 Quellen. Jede fetch_*-Funktion gibt eine Liste roher Kandidaten-Dicts zurück
oder wirft eine Exception — Isolation gegen Ausfälle passiert im Aufrufer (fetch_candidates.py)."""
import time

import requests

USER_AGENT = {"User-Agent": "ig-tagesgeschichte/1 (privates Projekt)"}


def get_with_retry(url: str, timeout: int = 15, **kwargs) -> requests.Response:
    resp = None
    for attempt in range(5):
        resp = requests.get(url, timeout=timeout, **kwargs)
        if resp.status_code == 429:
            wait = int(resp.headers.get("Retry-After", 5)) * (attempt + 1)
            print(f"  429, warte {wait}s...")
            time.sleep(wait)
            continue
        resp.raise_for_status()
        return resp
    resp.raise_for_status()
    return resp
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_sources.py -v`
Expected: `2 passed`

- [ ] **Step 5: Commit**

```bash
git add sources.py tests/test_sources.py
git commit -m "feat: gemeinsamer Retry-Helper für alle Quellen"
```

---

### Task 3: Quelle Wikipedia (`sources.fetch_wikipedia`)

**Files:**
- Modify: `sources.py`
- Modify: `tests/test_sources.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_sources.py`:

```python
WIKIPEDIA_SAMPLE = {
    "selected": [
        {
            "year": 1976,
            "text": "In der kanadischen Stadt Montreal werden die XXI. Olym\xadpischen Sommerspiele eröffnet.",
            "pages": [{"content_urls": {"desktop": {"page": "https://de.wikipedia.org/wiki/Montreal"}}}],
        },
        {"year": 1941, "text": "Deutschland ...", "pages": []},
    ]
}


def test_fetch_wikipedia_maps_candidates(monkeypatch):
    monkeypatch.setattr(sources, "get_with_retry", lambda url, **kw: FakeResponse(200, WIKIPEDIA_SAMPLE))
    candidates = sources.fetch_wikipedia(7, 17)
    assert len(candidates) == 2
    first = candidates[0]
    assert first["id"] == "wp-0"
    assert first["source"] == "wikipedia"
    assert first["lang"] == "de"
    assert first["year"] == 1976
    assert "\xad" not in first["text"]
    assert first["source_url"] == "https://de.wikipedia.org/wiki/Montreal"
    assert first["text_de"] is None
    assert candidates[1]["source_url"] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_sources.py -v`
Expected: FAIL with `AttributeError: module 'sources' has no attribute 'fetch_wikipedia'`

- [ ] **Step 3: Add `fetch_wikipedia` to `sources.py`**

```python
WIKIPEDIA_API = "https://de.wikipedia.org/api/rest_v1/feed/onthisday/selected/{mm}/{dd}"


def fetch_wikipedia(month: int, day: int) -> list[dict]:
    url = WIKIPEDIA_API.format(mm=f"{month:02d}", dd=f"{day:02d}")
    resp = get_with_retry(url, headers=USER_AGENT)
    events = resp.json().get("selected", [])
    candidates = []
    for i, ev in enumerate(events):
        page = (ev.get("pages") or [{}])[0]
        candidates.append({
            "id": f"wp-{i}",
            "source": "wikipedia",
            "lang": "de",
            "year": ev.get("year"),
            "text": ev.get("text", "").replace("\xad", ""),
            "text_de": None,
            "source_url": page.get("content_urls", {}).get("desktop", {}).get("page"),
        })
    return candidates
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_sources.py -v`
Expected: `3 passed`

- [ ] **Step 5: Commit**

```bash
git add sources.py tests/test_sources.py
git commit -m "feat: Wikipedia-Quelle als Kandidaten-Fetcher"
```

---

### Task 4: Quelle Wikidata (`sources.fetch_wikidata`)

**Files:**
- Modify: `sources.py`
- Modify: `tests/test_sources.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_sources.py`:

```python
WIKIDATA_SAMPLE = {
    "results": {
        "bindings": [
            {
                "date": {"value": "1976-07-17T00:00:00Z"},
                "eventLabel": {"value": "Eröffnung der Olympischen Sommerspiele", "xml:lang": "de"},
            },
            {
                "date": {"value": "1941-07-17T00:00:00Z"},
                "eventLabel": {"value": "Germany invades USSR", "xml:lang": "en"},
            },
        ]
    }
}


def test_fetch_wikidata_maps_candidates(monkeypatch):
    monkeypatch.setattr(sources, "get_with_retry", lambda url, **kw: FakeResponse(200, WIKIDATA_SAMPLE))
    candidates = sources.fetch_wikidata(7, 17)
    assert len(candidates) == 2
    assert candidates[0]["id"] == "wd-0"
    assert candidates[0]["source"] == "wikidata"
    assert candidates[0]["year"] == 1976
    assert candidates[0]["lang"] == "de"
    assert candidates[1]["lang"] == "en"
    assert candidates[0]["source_url"] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_sources.py -v`
Expected: FAIL with `AttributeError: module 'sources' has no attribute 'fetch_wikidata'`

- [ ] **Step 3: Add `fetch_wikidata` to `sources.py`**

```python
WIKIDATA_ENDPOINT = "https://query.wikidata.org/sparql"

WIKIDATA_QUERY_TEMPLATE = """
SELECT ?eventLabel ?date WHERE {{
  ?event wdt:P31/wdt:P279* wd:Q1190554 .
  ?event wdt:P585 ?date .
  FILTER(MONTH(?date) = {month} && DAY(?date) = {day})
  ?event wikibase:sitelinks ?sitelinks .
  FILTER(?sitelinks > 30)
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "de,en". }}
}}
ORDER BY DESC(?sitelinks)
LIMIT 10
"""


def fetch_wikidata(month: int, day: int) -> list[dict]:
    query = WIKIDATA_QUERY_TEMPLATE.format(month=month, day=day)
    resp = get_with_retry(
        WIKIDATA_ENDPOINT,
        params={"query": query, "format": "json"},
        headers=USER_AGENT,
        timeout=30,
    )
    bindings = resp.json()["results"]["bindings"]
    candidates = []
    for i, b in enumerate(bindings):
        candidates.append({
            "id": f"wd-{i}",
            "source": "wikidata",
            "lang": b["eventLabel"].get("xml:lang", "en"),
            "year": int(b["date"]["value"][:4]),
            "text": b["eventLabel"]["value"],
            "text_de": None,
            "source_url": None,
        })
    return candidates
```

Hinweis: Die Wikidata-Query scannt ohne Jahres-Eingrenzung nach `MONTH`/`DAY` —
das ist auf dem öffentlichen Endpoint bekannt langsam und kann timeouten.
Das ist beabsichtigt und in `fetch_candidates.py` (Task 7) durch
try/except abgefangen: liefert die Quelle nichts, bekommt der Tag halt
weniger Kandidaten aus den anderen 3 Quellen.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_sources.py -v`
Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add sources.py tests/test_sources.py
git commit -m "feat: Wikidata-Quelle als Kandidaten-Fetcher"
```

---

### Task 5: Quelle muffinlabs (`sources.fetch_muffinlabs`)

**Files:**
- Modify: `sources.py`
- Modify: `tests/test_sources.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_sources.py`:

```python
MUFFINLABS_SAMPLE = {
    "data": {
        "Events": [
            {
                "year": "1976",
                "text": "The Games of the XXI Olympiad open in Montreal.",
                "links": [{"title": "1976 Summer Olympics", "link": "https://en.wikipedia.org/wiki/1976_Summer_Olympics"}],
            },
            {"year": "1941", "text": "Germany invades the Soviet Union.", "links": []},
        ]
    }
}


def test_fetch_muffinlabs_maps_candidates(monkeypatch):
    monkeypatch.setattr(sources, "get_with_retry", lambda url, **kw: FakeResponse(200, MUFFINLABS_SAMPLE))
    candidates = sources.fetch_muffinlabs(7, 17)
    assert len(candidates) == 2
    assert candidates[0]["id"] == "ml-0"
    assert candidates[0]["source"] == "muffinlabs"
    assert candidates[0]["lang"] == "en"
    assert candidates[0]["year"] == 1976
    assert candidates[0]["source_url"] == "https://en.wikipedia.org/wiki/1976_Summer_Olympics"
    assert candidates[1]["source_url"] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_sources.py -v`
Expected: FAIL with `AttributeError: module 'sources' has no attribute 'fetch_muffinlabs'`

- [ ] **Step 3: Add `fetch_muffinlabs` to `sources.py`**

```python
MUFFINLABS_API = "https://history.muffinlabs.com/date/{m}/{d}"


def fetch_muffinlabs(month: int, day: int) -> list[dict]:
    resp = get_with_retry(MUFFINLABS_API.format(m=month, d=day), headers=USER_AGENT)
    events = resp.json().get("data", {}).get("Events", [])
    candidates = []
    for i, ev in enumerate(events):
        links = ev.get("links") or []
        candidates.append({
            "id": f"ml-{i}",
            "source": "muffinlabs",
            "lang": "en",
            "year": int(ev["year"]) if ev.get("year") else None,
            "text": ev.get("text", ""),
            "text_de": None,
            "source_url": links[0]["link"] if links else None,
        })
    return candidates
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_sources.py -v`
Expected: `5 passed`

- [ ] **Step 5: Commit**

```bash
git add sources.py tests/test_sources.py
git commit -m "feat: muffinlabs-Quelle als Kandidaten-Fetcher"
```

---

### Task 6: Quelle numbersapi (`sources.fetch_numbersapi`)

**Files:**
- Modify: `sources.py`
- Modify: `tests/test_sources.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_sources.py`:

```python
def test_fetch_numbersapi_found(monkeypatch):
    sample = {"text": "July 17th is the day...", "year": 1976, "found": True}
    monkeypatch.setattr(sources, "get_with_retry", lambda url, **kw: FakeResponse(200, sample))
    candidates = sources.fetch_numbersapi(7, 17)
    assert len(candidates) == 1
    assert candidates[0]["id"] == "na-0"
    assert candidates[0]["source"] == "numbersapi"
    assert candidates[0]["lang"] == "en"
    assert candidates[0]["year"] == 1976


def test_fetch_numbersapi_not_found(monkeypatch):
    sample = {"found": False}
    monkeypatch.setattr(sources, "get_with_retry", lambda url, **kw: FakeResponse(200, sample))
    candidates = sources.fetch_numbersapi(7, 17)
    assert candidates == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_sources.py -v`
Expected: FAIL with `AttributeError: module 'sources' has no attribute 'fetch_numbersapi'`

- [ ] **Step 3: Add `fetch_numbersapi` to `sources.py`**

```python
NUMBERSAPI_API = "https://numbersapi.com/{m}/{d}/date"


def fetch_numbersapi(month: int, day: int) -> list[dict]:
    resp = get_with_retry(NUMBERSAPI_API.format(m=month, d=day), params={"json": "true"}, headers=USER_AGENT)
    body = resp.json()
    if not body.get("found"):
        return []
    return [{
        "id": "na-0",
        "source": "numbersapi",
        "lang": "en",
        "year": body.get("year"),
        "text": body.get("text", ""),
        "text_de": None,
        "source_url": None,
    }]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_sources.py -v`
Expected: `7 passed`

- [ ] **Step 5: Commit**

```bash
git add sources.py tests/test_sources.py
git commit -m "feat: numbersapi-Quelle als Kandidaten-Fetcher"
```

---

### Task 7: Orchestrator `fetch_candidates.py` + Entfernen von `fetch_month.py`

**Files:**
- Create: `fetch_candidates.py`
- Create: `tests/test_fetch_candidates.py`
- Delete: `fetch_month.py`
- Modify: `.gitignore`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_fetch_candidates.py
import json

import fetch_candidates
import sources


def _candidate(id_, lang="de", text="x"):
    return {"id": id_, "source": "test", "lang": lang, "year": 2000, "text": text, "text_de": None, "source_url": None}


def test_fetch_day_isolates_source_failure(monkeypatch):
    monkeypatch.setattr(sources, "fetch_wikipedia", lambda m, d: (_ for _ in ()).throw(RuntimeError("down")))
    monkeypatch.setattr(sources, "fetch_wikidata", lambda m, d: [_candidate("wd-0")])
    monkeypatch.setattr(sources, "fetch_muffinlabs", lambda m, d: [_candidate("ml-0", lang="en")])
    monkeypatch.setattr(sources, "fetch_numbersapi", lambda m, d: [])

    translated = []

    def fake_translate(text, lang, api_key):
        translated.append((text, lang))
        return "übersetzt"

    monkeypatch.setattr(fetch_candidates.translate, "translate", fake_translate)

    candidates = fetch_candidates.fetch_day(7, 17, api_key="fake-key")
    ids = [c["id"] for c in candidates]
    assert ids == ["wd-0", "ml-0"]
    assert translated == [("x", "en")]
    assert candidates[1]["text_de"] == "übersetzt"
    assert candidates[0]["text_de"] is None  # deutsch, keine Übersetzung nötig


def test_main_writes_candidates_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(fetch_candidates, "CANDIDATES_DIR", tmp_path / "candidates")
    monkeypatch.setattr(fetch_candidates, "fetch_day", lambda month, day, api_key: [_candidate(f"x-{day}")])
    monkeypatch.setattr(fetch_candidates.translate, "load_api_key", lambda: None)
    monkeypatch.setattr("sys.argv", ["fetch_candidates.py", "2026", "2"])

    fetch_candidates.main()

    out_file = tmp_path / "candidates" / "2026-02" / "01.json"
    assert out_file.exists()
    data = json.loads(out_file.read_text(encoding="utf-8"))
    assert data["date"] == "2026-02-01"
    assert data["candidates"][0]["id"] == "x-1"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_fetch_candidates.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'fetch_candidates'`

- [ ] **Step 3: Write `fetch_candidates.py`**

```python
#!/usr/bin/env python3
"""4 Quellen -> candidates/YYYY-MM/DD.json (roh, ungefiltert, Basis für curate_server.py).

Nutzung:
    python3 fetch_candidates.py 2026 8
    python3 fetch_candidates.py 2026 8 --force
"""
import argparse
import calendar
import json
import sys
from pathlib import Path

import sources
import translate

CANDIDATES_DIR = Path(__file__).parent / "candidates"

FETCHER_NAMES = ["fetch_wikipedia", "fetch_wikidata", "fetch_muffinlabs", "fetch_numbersapi"]


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


def main():
    p = argparse.ArgumentParser()
    p.add_argument("year", type=int)
    p.add_argument("month", type=int)
    p.add_argument("--force", action="store_true")
    args = p.parse_args()

    api_key = translate.load_api_key()
    if not api_key:
        print("Kein DEEPL_API_KEY in .env gefunden — englische Kandidaten bleiben unübersetzt.")

    out_dir = CANDIDATES_DIR / f"{args.year}-{args.month:02d}"
    out_dir.mkdir(parents=True, exist_ok=True)

    days_in_month = calendar.monthrange(args.year, args.month)[1]
    for day in range(1, days_in_month + 1):
        out_file = out_dir / f"{day:02d}.json"
        if out_file.exists() and not args.force:
            print(f"skip {out_file.name} (existiert schon)")
            continue
        candidates = fetch_day(args.month, day, api_key)
        out_file.write_text(json.dumps({
            "date": f"{args.year}-{args.month:02d}-{day:02d}",
            "candidates": candidates,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"geschrieben: {out_file.name} ({len(candidates)} Kandidaten)")


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_fetch_candidates.py -v`
Expected: `2 passed`

- [ ] **Step 5: Remove `fetch_month.py`, update `.gitignore`**

```bash
git rm fetch_month.py
```

`.gitignore` bekommt eine Zeile mehr (Kandidaten sind Rohdaten, regenerierbar):

```
output/
candidates/
__pycache__/
```

- [ ] **Step 6: Manueller Live-Smoke-Test (echte APIs, ein Tag)**

Run: `python3 -c "import fetch_candidates; print(len(fetch_candidates.fetch_day(7, 17, fetch_candidates.translate.load_api_key())))"`
Expected: eine Zahl > 0 (mind. Wikipedia liefert etwas), keine Exception. Wikidata darf 0 beitragen (bekannt langsam), das ist ok.

- [ ] **Step 7: Commit**

```bash
git add fetch_candidates.py tests/test_fetch_candidates.py .gitignore
git commit -m "feat: fetch_candidates.py ersetzt fetch_month.py (4 Quellen statt 1)"
```

---

### Task 8: Reine Kuratier-Logik (`curate_logic.py`)

**Files:**
- Create: `curate_logic.py`
- Create: `tests/test_curate_logic.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_curate_logic.py
import json

import curate_logic


def _write_candidates(base, date_str, candidates):
    path = base / date_str[:7] / f"{date_str[-2:]}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"date": date_str, "candidates": candidates}), encoding="utf-8")


def test_load_candidates_missing_returns_empty(tmp_path):
    assert curate_logic.load_candidates(tmp_path, "2026-07-17") == []


def test_load_candidates_reads_file(tmp_path):
    _write_candidates(tmp_path, "2026-07-17", [{"id": "wp-0"}])
    assert curate_logic.load_candidates(tmp_path, "2026-07-17") == [{"id": "wp-0"}]


def test_resolve_selection_preserves_order():
    candidates = [{"id": "a", "v": 1}, {"id": "b", "v": 2}, {"id": "c", "v": 3}]
    result = curate_logic.resolve_selection(candidates, ["c", "a"])
    assert [r["id"] for r in result] == ["c", "a"]


def test_resolve_selection_ignores_unknown_ids():
    candidates = [{"id": "a", "v": 1}]
    result = curate_logic.resolve_selection(candidates, ["a", "ghost"])
    assert [r["id"] for r in result] == ["a"]


def test_save_selection_writes_facts(tmp_path):
    candidates = [{"id": "a", "year": 2000, "text": "x"}, {"id": "b", "year": 1999, "text": "y"}]
    curate_logic.save_selection(tmp_path, "2026-07-17", candidates, ["b", "a"])
    out = tmp_path / "2026-07" / "17.json"
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["date"] == "2026-07-17"
    assert [f["id"] for f in data["facts"]] == ["b", "a"]


def test_save_selection_rejects_more_than_nine(tmp_path):
    candidates = [{"id": str(i)} for i in range(10)]
    try:
        curate_logic.save_selection(tmp_path, "2026-07-17", candidates, [str(i) for i in range(10)])
        assert False, "sollte ValueError werfen"
    except ValueError:
        pass


def test_load_selected_ids_missing_returns_empty(tmp_path):
    assert curate_logic.load_selected_ids(tmp_path, "2026-07-17") == []


def test_load_selected_ids_reads_existing_selection(tmp_path):
    candidates = [{"id": "a", "year": 2000, "text": "x"}]
    curate_logic.save_selection(tmp_path, "2026-07-17", candidates, ["a"])
    assert curate_logic.load_selected_ids(tmp_path, "2026-07-17") == ["a"]


def test_next_unfinished_day_skips_curated(tmp_path):
    candidates_dir = tmp_path / "candidates"
    curate_dir = tmp_path / "curate"
    _write_candidates(candidates_dir, "2026-07-01", [{"id": "a"}])
    _write_candidates(candidates_dir, "2026-07-02", [{"id": "b"}])
    curate_logic.save_selection(curate_dir, "2026-07-01", [{"id": "a", "year": 1, "text": "x"}], ["a"])
    assert curate_logic.next_unfinished_day(candidates_dir, curate_dir, "2026-07") == "2026-07-02"


def test_next_unfinished_day_all_done_returns_first(tmp_path):
    candidates_dir = tmp_path / "candidates"
    curate_dir = tmp_path / "curate"
    _write_candidates(candidates_dir, "2026-07-01", [{"id": "a"}])
    curate_logic.save_selection(curate_dir, "2026-07-01", [{"id": "a", "year": 1, "text": "x"}], ["a"])
    assert curate_logic.next_unfinished_day(candidates_dir, curate_dir, "2026-07") == "2026-07-01"


def test_next_unfinished_day_no_candidates_returns_none(tmp_path):
    assert curate_logic.next_unfinished_day(tmp_path / "candidates", tmp_path / "curate", "2026-07") is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_curate_logic.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'curate_logic'`

- [ ] **Step 3: Write `curate_logic.py`**

```python
"""Reine Datei-Logik fürs Kuratier-Tool, ohne HTTP — leicht testbar, curate_server.py verdrahtet das nur."""
import json
from pathlib import Path

MAX_SELECTED = 9  # Instagram-Carousel-Limit: 9 Events + 1 Cover-Slide


def _day_path(base: Path, date_str: str) -> Path:
    return base / date_str[:7] / f"{date_str[-2:]}.json"


def load_candidates(candidates_dir: Path, date_str: str) -> list[dict]:
    path = _day_path(candidates_dir, date_str)
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))["candidates"]


def load_selected_ids(curate_dir: Path, date_str: str) -> list[str]:
    path = _day_path(curate_dir, date_str)
    if not path.exists():
        return []
    facts = json.loads(path.read_text(encoding="utf-8"))["facts"]
    return [f["id"] for f in facts if "id" in f]


def resolve_selection(candidates: list[dict], selected_ids: list[str]) -> list[dict]:
    by_id = {c["id"]: c for c in candidates}
    return [by_id[i] for i in selected_ids if i in by_id]


def save_selection(curate_dir: Path, date_str: str, candidates: list[dict], selected_ids: list[str]) -> None:
    if len(selected_ids) > MAX_SELECTED:
        raise ValueError(f"maximal {MAX_SELECTED} Events pro Tag (Instagram-Carousel-Limit)")
    facts = resolve_selection(candidates, selected_ids)
    path = _day_path(curate_dir, date_str)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"date": date_str, "facts": facts}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def next_unfinished_day(candidates_dir: Path, curate_dir: Path, month: str) -> str | None:
    month_path = candidates_dir / month
    if not month_path.exists():
        return None
    days = sorted(p.stem for p in month_path.glob("*.json"))
    if not days:
        return None
    for day in days:
        date_str = f"{month}-{day}"
        if not _day_path(curate_dir, date_str).exists():
            return date_str
    return f"{month}-{days[0]}"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_curate_logic.py -v`
Expected: `10 passed`

- [ ] **Step 5: Commit**

```bash
git add curate_logic.py tests/test_curate_logic.py
git commit -m "feat: reine Kuratier-Logik (Auswahl laden/speichern, nächster Tag)"
```

---

### Task 9: HTTP-Server (`curate_server.py`)

**Files:**
- Create: `curate_server.py`
- Create: `tests/test_curate_server.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_curate_server.py
import json
import threading
import time
import urllib.request
import urllib.error

import curate_server
import curate_logic


def _start_server(tmp_path, monkeypatch, port):
    monkeypatch.setattr(curate_server, "UI_DIR", tmp_path / "ui")
    monkeypatch.setattr(curate_server, "CANDIDATES_DIR", tmp_path / "candidates")
    monkeypatch.setattr(curate_server, "CURATE_DIR", tmp_path / "curate")

    (tmp_path / "ui").mkdir()
    (tmp_path / "ui" / "index.html").write_text("<html>ok</html>", encoding="utf-8")
    (tmp_path / "ui" / "app.js").write_text("// ok", encoding="utf-8")
    (tmp_path / "ui" / "style.css").write_text("body{}", encoding="utf-8")

    day_dir = tmp_path / "candidates" / "2026-07"
    day_dir.mkdir(parents=True)
    (day_dir / "17.json").write_text(json.dumps({
        "date": "2026-07-17",
        "candidates": [
            {"id": "wp-0", "source": "wikipedia", "lang": "de", "year": 1976, "text": "x", "text_de": None, "source_url": None},
        ],
    }), encoding="utf-8")

    server = curate_server.ThreadingHTTPServer(("localhost", port), curate_server.CurateHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.1)
    return server


def test_get_index(tmp_path, monkeypatch):
    server = _start_server(tmp_path, monkeypatch, 8421)
    try:
        with urllib.request.urlopen("http://localhost:8421/") as resp:
            assert resp.status == 200
            assert b"ok" in resp.read()
    finally:
        server.shutdown()


def test_get_day_returns_candidates(tmp_path, monkeypatch):
    server = _start_server(tmp_path, monkeypatch, 8422)
    try:
        with urllib.request.urlopen("http://localhost:8422/api/day/2026-07-17") as resp:
            data = json.loads(resp.read())
            assert data["date"] == "2026-07-17"
            assert data["candidates"][0]["id"] == "wp-0"
            assert data["selected_ids"] == []
    finally:
        server.shutdown()


def test_get_day_unknown_date_404(tmp_path, monkeypatch):
    server = _start_server(tmp_path, monkeypatch, 8423)
    try:
        try:
            urllib.request.urlopen("http://localhost:8423/api/day/2026-07-01")
            assert False, "sollte 404 werfen"
        except urllib.error.HTTPError as e:
            assert e.code == 404
    finally:
        server.shutdown()


def test_post_day_saves_selection(tmp_path, monkeypatch):
    server = _start_server(tmp_path, monkeypatch, 8424)
    try:
        req = urllib.request.Request(
            "http://localhost:8424/api/day/2026-07-17",
            data=json.dumps({"selected_ids": ["wp-0"]}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 200
        saved = curate_logic.load_selected_ids(tmp_path / "curate", "2026-07-17")
        assert saved == ["wp-0"]
    finally:
        server.shutdown()


def test_post_day_too_many_selected_400(tmp_path, monkeypatch):
    server = _start_server(tmp_path, monkeypatch, 8425)
    try:
        req = urllib.request.Request(
            "http://localhost:8425/api/day/2026-07-17",
            data=json.dumps({"selected_ids": [f"x-{i}" for i in range(10)]}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            urllib.request.urlopen(req)
            assert False, "sollte 400 werfen"
        except urllib.error.HTTPError as e:
            assert e.code == 400
    finally:
        server.shutdown()


def test_get_next_returns_date(tmp_path, monkeypatch):
    server = _start_server(tmp_path, monkeypatch, 8426)
    try:
        with urllib.request.urlopen("http://localhost:8426/api/next?month=2026-07") as resp:
            data = json.loads(resp.read())
            assert data["date"] == "2026-07-17"
    finally:
        server.shutdown()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_curate_server.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'curate_server'`

- [ ] **Step 3: Write `curate_server.py`**

```python
#!/usr/bin/env python3
"""Browser-Kuratier-Tool. Nutzung: python3 curate_server.py [--port 8420]"""
import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import curate_logic

BASE_DIR = Path(__file__).parent
UI_DIR = BASE_DIR / "curate_ui"
CANDIDATES_DIR = BASE_DIR / "candidates"
CURATE_DIR = BASE_DIR / "curate"

STATIC_FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/app.js": ("app.js", "application/javascript; charset=utf-8"),
    "/style.css": ("style.css", "text/css; charset=utf-8"),
}


class CurateHandler(BaseHTTPRequestHandler):
    def _json(self, status: int, body: dict) -> None:
        payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path in STATIC_FILES:
            filename, content_type = STATIC_FILES[parsed.path]
            content = (UI_DIR / filename).read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
            return
        if parsed.path == "/api/next":
            month = parse_qs(parsed.query).get("month", [""])[0]
            date = curate_logic.next_unfinished_day(CANDIDATES_DIR, CURATE_DIR, month)
            if date is None:
                self._json(404, {"error": f"keine Kandidaten für Monat {month}"})
                return
            self._json(200, {"date": date})
            return
        if parsed.path.startswith("/api/day/"):
            date_str = parsed.path.removeprefix("/api/day/")
            candidates = curate_logic.load_candidates(CANDIDATES_DIR, date_str)
            if not candidates:
                self._json(404, {"error": f"keine Kandidaten für {date_str}"})
                return
            selected_ids = curate_logic.load_selected_ids(CURATE_DIR, date_str)
            self._json(200, {"date": date_str, "candidates": candidates, "selected_ids": selected_ids})
            return
        self._json(404, {"error": "not found"})

    def do_POST(self):
        parsed = urlparse(self.path)
        if not parsed.path.startswith("/api/day/"):
            self._json(404, {"error": "not found"})
            return
        date_str = parsed.path.removeprefix("/api/day/")
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")
        selected_ids = body.get("selected_ids", [])
        candidates = curate_logic.load_candidates(CANDIDATES_DIR, date_str)
        if not candidates:
            self._json(404, {"error": f"keine Kandidaten für {date_str}"})
            return
        try:
            curate_logic.save_selection(CURATE_DIR, date_str, candidates, selected_ids)
        except ValueError as e:
            self._json(400, {"error": str(e)})
            return
        self._json(200, {"ok": True})

    def log_message(self, format, *args):
        pass  # ponytail: kein Access-Log-Rauschen für ein lokales Ein-Personen-Tool


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--port", type=int, default=8420)
    args = p.parse_args()
    server = ThreadingHTTPServer(("localhost", args.port), CurateHandler)
    print(f"Kuratier-Tool läuft: http://localhost:{args.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_curate_server.py -v`
Expected: `6 passed`

- [ ] **Step 5: Commit**

```bash
git add curate_server.py tests/test_curate_server.py
git commit -m "feat: HTTP-Server fürs Kuratier-Tool (stdlib, kein Framework)"
```

---

### Task 10: Frontend (`curate_ui/`)

**Files:**
- Create: `curate_ui/index.html`
- Create: `curate_ui/style.css`
- Create: `curate_ui/app.js`

Kein automatisierter Test — reines UI, Verifikation manuell in Step 3.

- [ ] **Step 1: Write `curate_ui/index.html`**

```html
<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>heute.today – Kuratieren</title>
<link rel="stylesheet" href="/style.css">
</head>
<body>
<header>
  <h1 id="date">–</h1>
  <p id="progress"></p>
</header>
<main id="cards"></main>
<footer>
  <button id="save">Speichern &amp; weiter</button>
</footer>
<script src="/app.js"></script>
</body>
</html>
```

- [ ] **Step 2: Write `curate_ui/style.css`**

```css
:root {
  --bg: #12121a;
  --card: #1c1c28;
  --accent: #ffc83c;
  --text: #f0f0f0;
  --muted: #aaaab4;
}
* { box-sizing: border-box; }
body {
  background: var(--bg);
  color: var(--text);
  font-family: system-ui, sans-serif;
  max-width: 720px;
  margin: 0 auto;
  padding: 24px;
}
header h1 { color: var(--accent); margin-bottom: 4px; }
header p { color: var(--muted); margin-top: 0; }
.card {
  background: var(--card);
  border: 2px solid transparent;
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 12px;
  cursor: pointer;
  position: relative;
}
.card.selected { border-color: var(--accent); }
.card.disabled { opacity: 0.4; cursor: not-allowed; }
.badge {
  display: inline-block;
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 12px;
  background: var(--muted);
  color: var(--bg);
  margin-right: 6px;
}
.order {
  position: absolute;
  top: -10px;
  left: -10px;
  background: var(--accent);
  color: var(--bg);
  border-radius: 50%;
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: bold;
}
.year { color: var(--accent); font-weight: bold; }
.original { color: var(--muted); font-size: 14px; margin-top: 6px; }
footer { position: sticky; bottom: 0; padding: 16px 0; background: var(--bg); }
button {
  background: var(--accent);
  border: none;
  padding: 12px 24px;
  border-radius: 6px;
  font-size: 16px;
  cursor: pointer;
}
```

- [ ] **Step 3: Write `curate_ui/app.js`**

```javascript
const MAX_SELECTED = 9;
let state = { date: null, candidates: [], selectedIds: [] };

async function loadDay(date) {
  const res = await fetch(`/api/day/${date}`);
  if (!res.ok) {
    document.getElementById("cards").textContent = "Keine Kandidaten für diesen Tag.";
    return;
  }
  const data = await res.json();
  state = { date: data.date, candidates: data.candidates, selectedIds: [...data.selected_ids] };
  render();
}

function toggle(id) {
  const idx = state.selectedIds.indexOf(id);
  if (idx >= 0) {
    state.selectedIds.splice(idx, 1);
  } else if (state.selectedIds.length < MAX_SELECTED) {
    state.selectedIds.push(id);
  }
  render();
}

function render() {
  document.getElementById("date").textContent = state.date;
  document.getElementById("progress").textContent =
    `${state.selectedIds.length}/${MAX_SELECTED} ausgewählt`;
  const cards = document.getElementById("cards");
  cards.innerHTML = "";
  for (const c of state.candidates) {
    const order = state.selectedIds.indexOf(c.id);
    const div = document.createElement("div");
    div.className = "card" + (order >= 0 ? " selected" : "");
    if (order < 0 && state.selectedIds.length >= MAX_SELECTED) {
      div.classList.add("disabled");
    }
    div.innerHTML = `
      ${order >= 0 ? `<div class="order">${order + 1}</div>` : ""}
      <span class="badge">${c.source}</span>
      <span class="badge">${c.lang}</span>
      <span class="year">${c.year ?? ""}</span>
      <div>${c.text_de ?? c.text}</div>
      ${c.text_de ? `<div class="original">${c.text}</div>` : ""}
    `;
    div.addEventListener("click", () => toggle(c.id));
    cards.appendChild(div);
  }
}

async function save() {
  await fetch(`/api/day/${state.date}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ selected_ids: state.selectedIds }),
  });
  const month = state.date.slice(0, 7);
  const res = await fetch(`/api/next?month=${month}`);
  if (res.ok) {
    const { date } = await res.json();
    loadDay(date);
  }
}

document.getElementById("save").addEventListener("click", save);

const params = new URLSearchParams(location.search);
const startDate = params.get("date");
if (startDate) {
  loadDay(startDate);
} else {
  const currentMonth = new Date().toISOString().slice(0, 7);
  fetch(`/api/next?month=${currentMonth}`)
    .then((r) => r.json())
    .then(({ date }) => loadDay(date));
}
```

- [ ] **Step 4: Manuelle Verifikation**

Run: `python3 fetch_candidates.py 2026 7 --force` (falls `candidates/2026-07/` noch nicht existiert)
Run: `python3 curate_server.py`
Öffne `http://localhost:8420/?date=2026-07-17` im Browser.

Erwartet: Karten mit Quelle-Badges, Klick markiert mit Ordnungszahl, „Speichern & weiter" schreibt `curate/2026-07/17.json` und springt zum nächsten unkuratierten Tag. Mit `curl -s http://localhost:8420/api/day/2026-07-17 | python3 -m json.tool` die JSON-Antwort zusätzlich gegenchecken.

- [ ] **Step 5: Commit**

```bash
git add curate_ui/
git commit -m "feat: Browser-UI fürs Kuratier-Tool"
```

---

### Task 11: Migration, Doku, Aufräumen

**Files:**
- Modify: `README.md`
- Verify: `curate/2026-07/*.json` (bereits vorhandene Testdaten aus dem alten Flow)

- [ ] **Step 1: Bestehende `curate/2026-07/*.json` gegen neues Schema prüfen**

Run: `python3 -c "import json,glob; [json.load(open(f)) for f in glob.glob('curate/2026-07/*.json')]; print('alle 31 lesbar')"`
Expected: `alle 31 lesbar` — altes Schema (`facts` mit `year`/`text`/`source_url`, ohne `id`) bleibt gültig, `render.py` liest nur die Felder die es kennt. Kein Migrationsskript nötig (siehe Spec, Abschnitt „Migration").

- [ ] **Step 2: README aktualisieren**

In `README.md` den Abschnitt „## Workflow" ersetzen durch:

```markdown
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
   Ergebnis in `output/2026-08/`: `17.png` (1080×1080) + `17_caption.txt`.
   (Aktuell noch 1-Bild-Format; Carousel-Rendering mit einem Slide pro
   kuratiertem Event kommt als eigene Spec.)

4. **Posten**: manuell, oder mit einem Scheduler (Meta Business Suite, Buffer,
   Later …) — Instagram-Posting selbst ist hier nicht automatisiert.
```

- [ ] **Step 3: Kompletten Testlauf**

Run: `python3 -m pytest tests/ -v`
Expected: alle Tests grün (Summe aus allen vorherigen Tasks)

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: README auf neuen Fetch-Kuratier-Render-Workflow aktualisiert"
```

---

## Zusammenfassung nach Abschluss

Neue Dateien: `sources.py`, `translate.py`, `fetch_candidates.py`, `curate_logic.py`,
`curate_server.py`, `curate_ui/{index.html,style.css,app.js}`, `.env.example`,
`tests/test_*.py` (5 Dateien).
Entfernt: `fetch_month.py`.
Unverändert: `render.py` (nächste Spec: Carousel-Umbau).
