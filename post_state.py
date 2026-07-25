"""Lokales State-Tracking für bereits gepostete Tage."""
from datetime import datetime, timezone
from pathlib import Path

STATE_DIR = Path(__file__).parent / "state" / "posted"


def _posted_dir() -> Path:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    return STATE_DIR


def _state_path(date_str: str) -> Path:
    return _posted_dir() / f"{date_str}.json"


def is_posted(date_str: str) -> bool:
    return _state_path(date_str).exists()


def load_posted(date_str: str) -> dict | None:
    path = _state_path(date_str)
    if not path.exists():
        return None
    import json

    return json.loads(path.read_text(encoding="utf-8"))


def mark_posted(date_str: str, media_id: str, image_urls: list[str]) -> None:
    import json

    path = _state_path(date_str)
    payload = {
        "date": date_str,
        "posted_at": datetime.now(timezone.utc).isoformat(),
        "platform": "instagram",
        "media_id": media_id,
        "image_urls": image_urls,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
