#!/usr/bin/env python3
"""Tägliche Gesundheitsprüfung für heute.today."""
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

from env import load_env_var
from notify import load_smtp_config, send_email

BASE_DIR = Path(__file__).parent
CANDIDATES_DIR = BASE_DIR / "candidates"
CURATE_DIR = BASE_DIR / "curate"

REQUIRED_ENV_KEYS = ["META_ACCESS_TOKEN", "IG_USER_ID"]
TIMERS = ["ig-fetch.timer", "ig-curate.timer", "ig-render.timer", "ig-post.timer"]


def TODAY_STR() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _date_strs_from(base: str, days: int) -> list[str]:
    base_date = datetime.strptime(base, "%Y-%m-%d")
    return [(base_date + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days)]


def check_candidates_exist(days: int = 7) -> list[str]:
    errors = []
    for date_str in _date_strs_from(TODAY_STR(), days):
        path = CANDIDATES_DIR / date_str[:7] / f"{date_str[-2:]}.json"
        if not path.exists():
            errors.append(f"Keine Kandidaten für {date_str}")
    return errors


def check_curated_exists(days: int = 3) -> list[str]:
    errors = []
    for date_str in _date_strs_from(TODAY_STR(), days):
        path = CURATE_DIR / date_str[:7] / f"{date_str[-2:]}.json"
        if not path.exists():
            errors.append(f"Nicht kuratiert für {date_str}")
    return errors


def check_timers_active() -> list[str]:
    errors = []
    try:
        res = subprocess.run(
            ["systemctl", "--user", "list-timers", "--all", "--no-pager"],
            capture_output=True,
            text=True,
            check=True,
        )
        output = res.stdout
        for timer in TIMERS:
            if timer not in output:
                errors.append(f"Timer {timer} nicht aktiv")
    except Exception as e:
        errors.append(f"Konnte systemd-Timer nicht prüfen: {e}")
    return errors


def check_env() -> list[str]:
    errors = []
    for key in REQUIRED_ENV_KEYS:
        if not load_env_var(key):
            errors.append(f"Umgebungsvariable {key} fehlt in .env")
    return errors


def check_all() -> list[str]:
    return (
        check_env()
        + check_timers_active()
        + check_candidates_exist(days=7)
        + check_curated_exists(days=3)
    )


def main() -> int:
    errors = check_all()
    if not errors:
        print("health_check: alles ok")
        return 0

    body = "heute.today Health-Check hat Probleme gefunden:\n\n" + "\n".join(f"- {e}" for e in errors)
    print(body)

    config = load_smtp_config()
    if config:
        try:
            send_email("heute.today — Health-Check Warnung", body, config)
        except Exception as e:
            print(f"Konnte Health-Check-E-Mail nicht senden: {e}", file=sys.stderr)

    return 1


if __name__ == "__main__":
    sys.exit(main())
