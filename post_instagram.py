#!/usr/bin/env python3
"""Postet ein Bild+Caption auf Instagram via graph.instagram.com (2-Schritt-Flow)."""
import sys
from pathlib import Path

import requests

GRAPH_API_BASE = "https://graph.instagram.com/v21.0"
TIMEOUT_SECONDS = 15


def load_env_var(key: str, env_path: str = ".env") -> str | None:
    """Liest einen einzelnen Wert aus einer .env-Datei (kein python-dotenv nötig)."""
    path = Path(env_path)
    if not path.exists():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith(f"{key}="):
            value = line.split("=", 1)[1].strip()
            return value or None
    return None


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


def _create_carousel_item(image_url: str, ig_user_id: str, access_token: str) -> str:
    res = requests.post(
        f"{GRAPH_API_BASE}/{ig_user_id}/media",
        data={"image_url": image_url, "is_carousel_item": "true", "access_token": access_token},
        timeout=TIMEOUT_SECONDS,
    )
    if res.status_code != 200:
        raise RuntimeError(f"Carousel-Kind-Container fehlgeschlagen: {_extract_error(res)}")
    return res.json()["id"]


def _create_carousel_container(children: list[str], caption: str, ig_user_id: str, access_token: str) -> str:
    res = requests.post(
        f"{GRAPH_API_BASE}/{ig_user_id}/media",
        data={
            "media_type": "CAROUSEL",
            "children": ",".join(children),
            "caption": caption,
            "access_token": access_token,
        },
        timeout=TIMEOUT_SECONDS,
    )
    if res.status_code != 200:
        raise RuntimeError(f"Carousel-Container fehlgeschlagen: {_extract_error(res)}")
    return res.json()["id"]


def post_carousel_to_instagram(image_urls: list[str], caption: str, ig_user_id: str, access_token: str) -> str:
    children = []
    for image_url in image_urls:
        try:
            children.append(_create_carousel_item(image_url, ig_user_id, access_token))
        except RuntimeError as e:
            print(f"Slide übersprungen ({image_url}): {e}", file=sys.stderr)

    if len(children) == 0:
        raise RuntimeError("Carousel-Post abgebrochen: 0 von {} Slides erfolgreich".format(len(image_urls)))

    if len(children) == 1:
        # ponytail: der schon erstellte Kind-Container hat kein caption (Slides tragen nie
        # eine eigene Caption) und kann nicht direkt publiziert werden — daher normaler
        # Einzelbild-Flow von Grund auf, mit dem Bild, das als einziges durchkam.
        return post_to_instagram(image_urls[0], caption, ig_user_id, access_token)

    carousel_id = _create_carousel_container(children, caption, ig_user_id, access_token)
    return _publish_media(carousel_id, ig_user_id, access_token)


def main():
    if len(sys.argv) < 3:
        print("Nutzung: python3 post_instagram.py <caption_datei> <url1> [<url2> ...]", file=sys.stderr)
        sys.exit(1)

    with open(sys.argv[1], encoding="utf-8") as f:
        caption = f.read()
    image_urls = sys.argv[2:]

    ig_user_id = load_env_var("IG_USER_ID")
    if not ig_user_id:
        raise RuntimeError("IG_USER_ID fehlt in .env")

    access_token = load_env_var("META_ACCESS_TOKEN")
    if not access_token:
        raise RuntimeError("META_ACCESS_TOKEN fehlt in .env")

    if len(image_urls) == 1:
        media_id = post_to_instagram(image_urls[0], caption, ig_user_id, access_token)
    else:
        media_id = post_carousel_to_instagram(image_urls, caption, ig_user_id, access_token)
    print(f"gepostet: {media_id}")


if __name__ == "__main__":
    main()
