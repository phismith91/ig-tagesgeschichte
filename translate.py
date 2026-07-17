"""DeepL-Übersetzung für nicht-deutsche Kandidaten. Key kommt aus .env (Free-Tier, kein python-dotenv nötig)."""
from pathlib import Path

import requests


def load_api_key(env_path: str = ".env") -> str | None:
    path = Path(env_path)
    if not path.exists():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("DEEPL_API_KEY="):
            value = line.split("=", 1)[1].strip()
            return value or None
    return None


def deepl_endpoint(api_key: str) -> str:
    host = "api-free.deepl.com" if api_key.endswith(":fx") else "api.deepl.com"
    return f"https://{host}/v2/translate"


def translate(text: str, source_lang: str, api_key: str | None) -> str | None:
    if not api_key:
        return None
    try:
        resp = requests.post(
            deepl_endpoint(api_key),
            data={
                "auth_key": api_key,
                "text": text,
                "source_lang": source_lang.upper(),
                "target_lang": "DE",
            },
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()["translations"][0]["text"]
    except Exception as e:
        print(f"  DeepL-Übersetzung fehlgeschlagen: {e}")
        return None
