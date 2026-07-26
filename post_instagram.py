#!/usr/bin/env python3
"""Postet ein Bild (Einzelbild) oder mehrere Bilder (Carousel) auf Instagram via graph.instagram.com."""
import sys
import time

import requests

from env import load_env_var

GRAPH_API_BASE = "https://graph.instagram.com/v21.0"
TIMEOUT_SECONDS = 15
MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = [3, 9]
# ponytail: Instagram braucht eine kurze Verarbeitungszeit, bis ein Container
# publiziert werden kann. Wir pollen den Status, statt sofort zu publish.
STATUS_POLL_INTERVAL_SECONDS = 2
STATUS_POLL_MAX_WAIT_SECONDS = 60


def _is_retryable(exc_or_res) -> bool:
    """Entscheidet, ob ein Fehler retry-fähig ist."""
    if isinstance(exc_or_res, requests.Response):
        return exc_or_res.status_code >= 500
    if isinstance(exc_or_res, requests.exceptions.RequestException):
        return True
    return False


def _request_with_retry(method: str, url: str, **kwargs):
    """Führt einen HTTP-Call mit Retry-Logik aus."""
    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            res = getattr(requests, method)(url, **kwargs)
            if res.status_code < 500:
                return res
            last_error = res
        except requests.exceptions.RequestException as e:
            last_error = e

        if attempt < len(RETRY_BACKOFF_SECONDS):
            time.sleep(RETRY_BACKOFF_SECONDS[attempt])

    if isinstance(last_error, requests.exceptions.RequestException):
        raise last_error
    return last_error


def post_to_instagram(image_url: str, caption: str, ig_user_id: str, access_token: str) -> str:
    creation_id = _create_media_container(image_url, caption, ig_user_id, access_token)
    _wait_for_media_container(creation_id, ig_user_id, access_token)
    return _publish_media(creation_id, ig_user_id, access_token)


def _create_media_container(image_url: str, caption: str, ig_user_id: str, access_token: str) -> str:
    res = _request_with_retry(
        "post",
        f"{GRAPH_API_BASE}/{ig_user_id}/media",
        data={"image_url": image_url, "caption": caption, "access_token": access_token},
        timeout=TIMEOUT_SECONDS,
    )
    if res.status_code != 200:
        raise RuntimeError(f"Instagram-Media-Container fehlgeschlagen: {_extract_error(res)}")
    return res.json()["id"]


def _wait_for_media_container(creation_id: str, ig_user_id: str, access_token: str) -> None:
    """Pollt den Container-Status, bis Instagram die Verarbeitung abgeschlossen hat."""
    url = f"{GRAPH_API_BASE}/{creation_id}"
    params = {
        "fields": "status_code",
        "access_token": access_token,
    }
    deadline = time.time() + STATUS_POLL_MAX_WAIT_SECONDS
    while time.time() < deadline:
        res = _request_with_retry(
            "get",
            url,
            params=params,
            timeout=TIMEOUT_SECONDS,
        )
        if res.status_code == 200:
            data = res.json()
            status = data.get("status_code")
            if status == "FINISHED":
                return
            if status in ("ERROR", "EXPIRED"):
                raise RuntimeError(f"Instagram-Container fehlgeschlagen (Status: {status})")
        time.sleep(STATUS_POLL_INTERVAL_SECONDS)
    raise RuntimeError("Timeout: Instagram-Container wurde nicht fertig")


def _publish_media(creation_id: str, ig_user_id: str, access_token: str) -> str:
    res = _request_with_retry(
        "post",
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
    res = _request_with_retry(
        "post",
        f"{GRAPH_API_BASE}/{ig_user_id}/media",
        data={"image_url": image_url, "is_carousel_item": "true", "access_token": access_token},
        timeout=TIMEOUT_SECONDS,
    )
    if res.status_code != 200:
        raise RuntimeError(f"Carousel-Kind-Container fehlgeschlagen: {_extract_error(res)}")
    return res.json()["id"]


def _create_carousel_container(children: list[str], caption: str, ig_user_id: str, access_token: str) -> str:
    res = _request_with_retry(
        "post",
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
    successful_urls = []
    errors = []
    for image_url in image_urls:
        try:
            child_id = _create_carousel_item(image_url, ig_user_id, access_token)
            _wait_for_media_container(child_id, ig_user_id, access_token)
            children.append(child_id)
            successful_urls.append(image_url)
        except (RuntimeError, requests.exceptions.RequestException) as e:
            print(f"Slide übersprungen ({image_url}): {e}", file=sys.stderr)
            errors.append(str(e))

    if len(children) == 0:
        last_error = errors[-1] if errors else "unbekannter Fehler"
        raise RuntimeError(f"Carousel-Post abgebrochen: 0 von {len(image_urls)} Slides erfolgreich ({last_error})")

    if len(children) == 1:
        # ponytail: der schon erstellte Kind-Container hat kein caption (Slides tragen nie
        # eine eigene Caption) und kann nicht direkt publiziert werden — daher normaler
        # Einzelbild-Flow von Grund auf, mit dem Bild, das als einziges durchkam
        # (successful_urls[0], NICHT image_urls[0] — der Überlebende muss nicht der erste sein).
        return post_to_instagram(successful_urls[0], caption, ig_user_id, access_token)

    carousel_id = _create_carousel_container(children, caption, ig_user_id, access_token)
    _wait_for_media_container(carousel_id, ig_user_id, access_token)
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
