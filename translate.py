"""DeepL-Übersetzung für nicht-deutsche Kandidaten. Key kommt aus .env (Free-Tier, kein python-dotenv nötig).

ponytail: Auth per Header (Authorization: DeepL-Auth-Key ...) statt Body-Parameter —
DeepL hat den Body-Parameter "auth_key" im Nov. 2025 als Legacy-Methode abgeschafft
(https://developers.deepl.com/docs/resources/breaking-changes-change-notices/november-2025-deprecation-of-legacy-auth-methods).
"""
import requests


def deepl_endpoint(api_key: str) -> str:
    host = "api-free.deepl.com" if api_key.endswith(":fx") else "api.deepl.com"
    return f"https://{host}/v2/translate"


def translate(text: str, source_lang: str, api_key: str | None) -> str | None:
    if not api_key:
        return None
    try:
        resp = requests.post(
            deepl_endpoint(api_key),
            headers={"Authorization": f"DeepL-Auth-Key {api_key}"},
            data={
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
