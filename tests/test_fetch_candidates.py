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
    monkeypatch.setattr(fetch_candidates.env, "load_env_var", lambda key: None)
    monkeypatch.setattr(fetch_candidates.time, "sleep", lambda s: None)
    monkeypatch.setattr("sys.argv", ["fetch_candidates.py", "2026", "2"])

    fetch_candidates.main()

    out_file = tmp_path / "candidates" / "2026-02" / "01.json"
    assert out_file.exists()
    data = json.loads(out_file.read_text(encoding="utf-8"))
    assert data["date"] == "2026-02-01"
    assert data["candidates"][0]["id"] == "x-1"
