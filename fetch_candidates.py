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
