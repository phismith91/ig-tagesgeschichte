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


def test_get_day_malformed_date_400(tmp_path, monkeypatch):
    server = _start_server(tmp_path, monkeypatch, 8427)
    try:
        try:
            urllib.request.urlopen("http://localhost:8427/api/day/not-a-date")
            assert False, "sollte 400 werfen"
        except urllib.error.HTTPError as e:
            assert e.code == 400
    finally:
        server.shutdown()


def test_get_next_malformed_month_400(tmp_path, monkeypatch):
    server = _start_server(tmp_path, monkeypatch, 8428)
    try:
        try:
            urllib.request.urlopen("http://localhost:8428/api/next?month=not-a-month")
            assert False, "sollte 400 werfen"
        except urllib.error.HTTPError as e:
            assert e.code == 400
    finally:
        server.shutdown()
