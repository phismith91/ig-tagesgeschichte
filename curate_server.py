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
        if parsed.path.startswith("/api/day/"):
            date_str = parsed.path.removeprefix("/api/day/")
            try:
                candidates = curate_logic.load_candidates(CANDIDATES_DIR, date_str)
                if not candidates:
                    self._json(404, {"error": f"keine Kandidaten für {date_str}"})
                    return
                selected_ids = curate_logic.load_selected_ids(CURATE_DIR, date_str)
            except ValueError as e:
                self._json(400, {"error": str(e)})
                return
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
        try:
            candidates = curate_logic.load_candidates(CANDIDATES_DIR, date_str)
            if not candidates:
                self._json(404, {"error": f"keine Kandidaten für {date_str}"})
                return
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
