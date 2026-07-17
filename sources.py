"""Kandidaten-Fetcher für 4 Quellen. Jede fetch_*-Funktion gibt eine Liste roher Kandidaten-Dicts zurück
oder wirft eine Exception — Isolation gegen Ausfälle passiert im Aufrufer (fetch_candidates.py)."""
import time

import requests

USER_AGENT = {"User-Agent": "ig-tagesgeschichte/1 (privates Projekt)"}


def get_with_retry(url: str, timeout: int = 15, **kwargs) -> requests.Response:
    resp = None
    for attempt in range(5):
        resp = requests.get(url, timeout=timeout, **kwargs)
        if resp.status_code == 429:
            wait = int(resp.headers.get("Retry-After", 5)) * (attempt + 1)
            print(f"  429, warte {wait}s...")
            time.sleep(wait)
            continue
        resp.raise_for_status()
        return resp
    resp.raise_for_status()
    return resp
