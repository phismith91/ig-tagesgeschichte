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
import time
from pathlib import Path

import env
import sources
import translate

CANDIDATES_DIR = Path(__file__).parent / "candidates"


def fetch_day(month: int, day: int, api_key: str | None) -> list[dict]:
    candidates = []
    # ponytail: Funktionsreferenzen HIER innerhalb der Funktion aufgebaut (nicht als
    # Modul-Konstante) — sonst würde monkeypatch.setattr(sources, "fetch_wikipedia", ...)
    # in Tests wirkungslos, weil eine Modul-Konstante die alte Referenz schon beim Import
    # fest einfrieren würde. So wird sources.fetch_wikipedia bei jedem Aufruf live nachgeschlagen.
    fetchers = (sources.fetch_wikipedia, sources.fetch_wikidata, sources.fetch_muffinlabs, sources.fetch_numbersapi)
    for fetcher in fetchers:
        try:
            candidates.extend(fetcher(month, day))
        except Exception as e:
            print(f"  {fetcher.__name__} fehlgeschlagen: {e}")
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

    api_key = env.load_env_var("DEEPL_API_KEY")
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
        time.sleep(1.5)  # ponytail: Schonfrist für die öffentlichen APIs zwischen Tagen


if __name__ == "__main__":
    sys.exit(main())
