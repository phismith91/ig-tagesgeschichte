"""Liest einzelne Werte aus einer .env-Datei (kein python-dotenv nötig)."""
from pathlib import Path


def load_env_var(key: str, env_path: str = ".env") -> str | None:
    path = Path(env_path)
    if not path.exists():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith(f"{key}="):
            value = line.split("=", 1)[1].strip()
            return value or None
    return None
