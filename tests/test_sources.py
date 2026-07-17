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


def test_fetch_wikidata_handles_bce_year(monkeypatch):
    sample = {
        "results": {
            "bindings": [
                {
                    "date": {"value": "-0044-03-15T00:00:00Z"},
                    "eventLabel": {"value": "Ermordung Caesars", "xml:lang": "de"},
                },
            ]
        }
    }
    monkeypatch.setattr(sources, "get_with_retry", lambda url, **kw: FakeResponse(200, sample))
    candidates = sources.fetch_wikidata(3, 15)
    assert candidates[0]["year"] == -44


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
