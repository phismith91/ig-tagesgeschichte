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
