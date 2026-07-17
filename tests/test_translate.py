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
