#!/usr/bin/env python3
"""Postet ein Bild+Caption auf Instagram via graph.instagram.com (2-Schritt-Flow)."""
import os
import sys

import requests

GRAPH_API_BASE = "https://graph.instagram.com/v21.0"
TIMEOUT_SECONDS = 15


def post_to_instagram(image_url: str, caption: str, ig_user_id: str, access_token: str) -> str:
    creation_id = _create_media_container(image_url, caption, ig_user_id, access_token)
    return _publish_media(creation_id, ig_user_id, access_token)


def _create_media_container(image_url: str, caption: str, ig_user_id: str, access_token: str) -> str:
    res = requests.post(
        f"{GRAPH_API_BASE}/{ig_user_id}/media",
        data={"image_url": image_url, "caption": caption, "access_token": access_token},
        timeout=TIMEOUT_SECONDS,
    )
    if res.status_code != 200:
        raise RuntimeError(f"Instagram-Media-Container fehlgeschlagen: {_extract_error(res)}")
    return res.json()["id"]


def _publish_media(creation_id: str, ig_user_id: str, access_token: str) -> str:
    res = requests.post(
        f"{GRAPH_API_BASE}/{ig_user_id}/media_publish",
        data={"creation_id": creation_id, "access_token": access_token},
        timeout=TIMEOUT_SECONDS,
    )
    if res.status_code != 200:
        raise RuntimeError(f"Instagram-Publish fehlgeschlagen: {_extract_error(res)}")
    return res.json()["id"]


def _extract_error(res) -> str:
    """Liest die Fehlermeldung aus der API-Antwort, auch wenn der Body kein JSON ist."""
    try:
        return res.json().get("error", {}).get("message", res.text)
    except ValueError:
        return res.text


def main():
    if len(sys.argv) != 3:
        print("Nutzung: python3 post_instagram.py <image_url> <caption_datei>", file=sys.stderr)
        sys.exit(1)

    image_url = sys.argv[1]
    with open(sys.argv[2], encoding="utf-8") as f:
        caption = f.read()

    ig_user_id = os.environ["IG_USER_ID"]
    access_token = os.environ["META_ACCESS_TOKEN"]

    media_id = post_to_instagram(image_url, caption, ig_user_id, access_token)
    print(f"gepostet: {media_id}")


if __name__ == "__main__":
    main()
