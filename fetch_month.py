#!/usr/bin/env python3
"""Wikipedia 'On this day' -> curate/YYYY-MM/DD.json (editierbar vor dem Rendern).

Nutzung:
    python3 fetch_month.py 2026 8       # August 2026, deutsche Wikipedia
    python3 fetch_month.py 2026 8 --lang en
    python3 fetch_month.py 2026 8 --force   # bestehende Dateien überschreiben
"""
import argparse
import calendar
import json
import sys
import time
from pathlib import Path

import requests

API = "https://{lang}.wikipedia.org/api/rest_v1/feed/onthisday/selected/{mm}/{dd}"
CURATE_DIR = Path(__file__).parent / "curate"
MAX_FACTS = 3  # mehr sprengt die 1080x1080-Bildhöhe im Template


def clean(text: str) -> str:
    return text.replace("\xad", "")  # Wikipedia-Trennzeichen, PIL-Default-Font rendert es als Kästchen


def fetch_day(lang: str, month: int, day: int) -> list[dict]:
    url = API.format(lang=lang, mm=f"{month:02d}", dd=f"{day:02d}")
    headers = {"User-Agent": "ig-tagesgeschichte/1 (privates Projekt)"}
    for attempt in range(5):
        resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code == 429:
            wait = int(resp.headers.get("Retry-After", 5)) * (attempt + 1)
            print(f"  429, warte {wait}s...")
            time.sleep(wait)
            continue
        resp.raise_for_status()
        break
    else:
        resp.raise_for_status()
    events = resp.json().get("selected", [])
    facts = []
    for ev in events[:MAX_FACTS]:
        page = (ev.get("pages") or [{}])[0]
        facts.append({
            "year": ev.get("year"),
            "text": clean(ev.get("text", "")),
            "source_url": page.get("content_urls", {}).get("desktop", {}).get("page", ""),
        })
    return facts


def main():
    p = argparse.ArgumentParser()
    p.add_argument("year", type=int)
    p.add_argument("month", type=int)
    p.add_argument("--lang", default="de")
    p.add_argument("--force", action="store_true")
    args = p.parse_args()

    out_dir = CURATE_DIR / f"{args.year}-{args.month:02d}"
    out_dir.mkdir(parents=True, exist_ok=True)

    days_in_month = calendar.monthrange(args.year, args.month)[1]
    for day in range(1, days_in_month + 1):
        out_file = out_dir / f"{day:02d}.json"
        if out_file.exists() and not args.force:
            print(f"skip {out_file.name} (existiert schon)")
            continue
        facts = fetch_day(args.lang, args.month, day)
        out_file.write_text(json.dumps({
            "date": f"{args.year}-{args.month:02d}-{day:02d}",
            "facts": facts,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"geschrieben: {out_file.name} ({len(facts)} Fakten)")
        time.sleep(1.5)  # höflich zur API-Rate-Limit


if __name__ == "__main__":
    sys.exit(main())
