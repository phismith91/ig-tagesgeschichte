"""Reine Datei-Logik fürs Kuratier-Tool, ohne HTTP — leicht testbar, curate_server.py verdrahtet das nur."""
import json
import re
from pathlib import Path

MAX_SELECTED = 9  # Instagram-Carousel-Limit: 9 Events + 1 Cover-Slide

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_MONTH_RE = re.compile(r"^\d{4}-\d{2}$")


def _day_path(base: Path, date_str: str) -> Path:
    if not _DATE_RE.match(date_str):
        raise ValueError(f"ungültiges Datum: {date_str!r}")
    return base / date_str[:7] / f"{date_str[-2:]}.json"


def load_candidates(candidates_dir: Path, date_str: str) -> list[dict]:
    path = _day_path(candidates_dir, date_str)
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))["candidates"]


def load_selected_ids(curate_dir: Path, date_str: str) -> list[str]:
    path = _day_path(curate_dir, date_str)
    if not path.exists():
        return []
    facts = json.loads(path.read_text(encoding="utf-8"))["facts"]
    return [f["id"] for f in facts if "id" in f]


def resolve_selection(candidates: list[dict], selected_ids: list[str]) -> list[dict]:
    by_id = {c["id"]: c for c in candidates}
    return [by_id[i] for i in selected_ids if i in by_id]


def save_selection(curate_dir: Path, date_str: str, candidates: list[dict], selected_ids: list[str]) -> None:
    if len(selected_ids) > MAX_SELECTED:
        raise ValueError(f"maximal {MAX_SELECTED} Events pro Tag (Instagram-Carousel-Limit)")
    facts = [
        {**c, "text": c["text_de"]} if c.get("text_de") else c
        for c in resolve_selection(candidates, selected_ids)
    ]
    path = _day_path(curate_dir, date_str)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"date": date_str, "facts": facts}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def next_unfinished_day(candidates_dir: Path, curate_dir: Path, month: str) -> str | None:
    if not _MONTH_RE.match(month):
        raise ValueError(f"ungültiger Monat: {month!r}")
    month_path = candidates_dir / month
    if not month_path.exists():
        return None
    days = sorted(p.stem for p in month_path.glob("*.json"))
    if not days:
        return None
    for day in days:
        date_str = f"{month}-{day}"
        if not _day_path(curate_dir, date_str).exists():
            return date_str
    return f"{month}-{days[0]}"
