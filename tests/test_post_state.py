from pathlib import Path

import post_state


def test_is_posted_false_when_no_state(tmp_path, monkeypatch):
    monkeypatch.setattr(post_state, "_posted_dir", lambda: tmp_path)
    assert post_state.is_posted("2026-07-25") is False


def test_mark_posted_and_is_posted(tmp_path, monkeypatch):
    monkeypatch.setattr(post_state, "_posted_dir", lambda: tmp_path)
    post_state.mark_posted("2026-07-25", "media-123", ["https://example.com/1.png"])
    assert post_state.is_posted("2026-07-25") is True
    data = post_state.load_posted("2026-07-25")
    assert data["media_id"] == "media-123"
    assert data["image_urls"] == ["https://example.com/1.png"]
    assert data["platform"] == "instagram"


def test_load_posted_returns_none_for_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(post_state, "_posted_dir", lambda: tmp_path)
    assert post_state.load_posted("2026-07-25") is None
