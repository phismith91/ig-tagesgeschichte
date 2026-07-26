from pathlib import Path
from unittest.mock import patch

import health_check


def test_check_candidates_exist_returns_error_when_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(health_check, "CANDIDATES_DIR", tmp_path / "candidates")
    monkeypatch.setattr(health_check, "CURATE_DIR", tmp_path / "curate")
    monkeypatch.setattr(health_check, "TODAY_STR", lambda: "2099-01-15")

    errors = health_check.check_candidates_exist(days=3)
    assert len(errors) == 3
    assert "2099-01-15" in errors[0]


def test_check_curated_exists_returns_error_when_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(health_check, "CURATE_DIR", tmp_path / "curate")
    monkeypatch.setattr(health_check, "TODAY_STR", lambda: "2099-01-15")

    errors = health_check.check_curated_exists(days=2)
    assert len(errors) == 2
    assert "2099-01-15" in errors[0]


def test_check_curated_passes_when_files_exist(tmp_path, monkeypatch):
    curate_dir = tmp_path / "curate" / "2099-01"
    curate_dir.mkdir(parents=True)
    (curate_dir / "15.json").write_text("{}")
    (curate_dir / "16.json").write_text("{}")

    monkeypatch.setattr(health_check, "CURATE_DIR", tmp_path / "curate")
    monkeypatch.setattr(health_check, "TODAY_STR", lambda: "2099-01-15")

    errors = health_check.check_curated_exists(days=2)
    assert errors == []
