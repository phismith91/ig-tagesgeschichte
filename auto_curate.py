#!/usr/bin/env python3
"""Tägliche Vorkuratierung aufrufen — für systemd oder manuelle Nutzung.

Nutung:
    python3 auto_curate.py              # heute
    python3 auto_curate.py 2026 7 25    # bestimmter Tag
"""
import argparse
import sys
from datetime import datetime
from pathlib import Path

import curate_agent

CANDIDATES_DIR = Path(__file__).parent / "candidates"
CURATE_DIR = Path(__file__).parent / "curate"


def curate_today(year: int, month: int, day: int, force: bool = False) -> None:
    month_key = f"{year}-{month:02d}"
    day_key = f"{day:02d}"
    src = CANDIDATES_DIR / month_key / f"{day_key}.json"
    dst = CURATE_DIR / month_key / f"{day_key}.json"

    if not src.exists():
        print(f"skip {src}: keine Kandidaten")
        return

    if dst.exists() and not force:
        print(f"skip {dst}: bereits kuratiert (use --force zum Überschreiben)")
        return

    curate_agent.curate(src, dst)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("year", type=int, nargs="?")
    p.add_argument("month", type=int, nargs="?")
    p.add_argument("day", type=int, nargs="?")
    p.add_argument("--force", action="store_true", help="Vorhandene Kuratierung überschreiben")
    args = p.parse_args()

    if args.year is None:
        now = datetime.now()
        args.year, args.month, args.day = now.year, now.month, now.day

    curate_today(args.year, args.month, args.day, force=args.force)
    return 0


if __name__ == "__main__":
    sys.exit(main())
