#!/usr/bin/env python3
"""Agentische Vorkuratierung: candidates/ -> curate/ mit LLM oder Fallback.

Nutung:
    python3 curate_agent.py candidates/2026-07/25.json curate/2026-07/25.json
    python3 curate_agent.py --month candidates/2026-07 curate/2026-07

Steuerung über .env:
    LLM_API_KEY=...           # leer/missing -> regelbasierte Fallback-Kuratierung
    LLM_BASE_URL=https://...  # OpenAI-kompatibler Endpunkt
    LLM_MODEL=gpt-4.1-mini    # günstiges Modell
"""
import argparse
import json
import sys
from pathlib import Path

import requests

from env import load_env_var

MAX_FACTS = 9
TIMEOUT_SECONDS = 60


def _load_candidates(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _facts_with_year(candidates: list[dict]) -> list[dict]:
    return [c for c in candidates if c.get("year")]


def _fallback_curation(candidates: list[dict]) -> tuple[list[dict], str]:
    """Regelbasierte Auswahl: absteigend nach Jahr (neuestes zuerst), max. 9 Fakten."""
    facts = sorted(_facts_with_year(candidates), key=lambda c: c["year"], reverse=True)
    selected = facts[:MAX_FACTS]

    if not selected:
        return [], ""

    if len(selected) == 1:
        intro = f"Am diesem Tag im Jahr {selected[0]['year']} geschah etwas, das man sich merken sollte."
    else:
        year_range = f"{selected[-1]['year']} bis {selected[0]['year']}"
        intro = (
            f"Vom Jahr {year_range}: Dieser Tag hat Geschichte geschrieben — "
            f"{len(selected)} Ereignisse, die man kennen sollte."
        )
    return selected, intro


def _build_prompt(candidates: list[dict]) -> str:
    candidate_texts = []
    for i, c in enumerate(candidates):
        text = c.get("text_de") or c.get("text", "")
        candidate_texts.append(
            f"[{i}] Jahr {c.get('year', 'unbekannt')} | Quelle {c.get('source')} | {text}"
        )

    return (
        "Du bist Redakteur für einen deutschen Instagram-History-Channel. "
        "Wähle aus den folgenden Kandidaten die besten Ereignisse für einen Post aus.\n\n"
        "Regeln:\n"
        "- Maximal 9 Ereignisse.\n"
        "- Sortiere sie abschließend aufsteigend nach Jahr (ältestes zuerst).\n"
        "- Wähle eine inhaltlich abwechslungsreiche Mischung (Politik, Kultur, Technik, Gesellschaft).\n"
        "- Bevorzuge Ereignisse mit gut verständlichem deutschen Text.\n"
        "- Vermeide zu grausame oder politisch hochsensible Themen.\n\n"
        "Gib das Ergebnis als JSON zurück:\n"
        "{\n"
        '  "selected_indices": [0, 3, 7, ...],\n'
        '  "intro": "Kurze, eingängige Einleitung auf Deutsch (2-3 Sätze)."\n'
        "}\n\n"
        "Kandidaten:\n" + "\n".join(candidate_texts)
    )


def _llm_curation(candidates: list[dict]) -> tuple[list[dict], str]:
    api_key = load_env_var("LLM_API_KEY")
    base_url = load_env_var("LLM_BASE_URL") or "https://api.openai.com/v1"
    model = load_env_var("LLM_MODEL") or "gpt-4.1-mini"

    if not api_key:
        raise RuntimeError("LLM_API_KEY nicht gesetzt")

    url = f"{base_url.rstrip('/')}/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": _build_prompt(candidates)}],
        "temperature": 0.5,
        "max_tokens": 800,
    }

    resp = requests.post(url, headers=headers, json=payload, timeout=TIMEOUT_SECONDS)
    if resp.status_code != 200:
        raise RuntimeError(f"LLM-Anfrage fehlgeschlagen: {resp.status_code} {resp.text}")

    content = resp.json()["choices"][0]["message"]["content"]
    # ponytail: einfache JSON-Extraktion aus Markdown-Codeblock oder Roh-JSON
    if "```json" in content:
        content = content.split("```json")[1].split("```")[0].strip()
    elif "```" in content:
        content = content.split("```")[1].split("```")[0].strip()
    content = content.strip()

    result = json.loads(content)
    indices = result.get("selected_indices", [])
    intro = result.get("intro", "").strip()

    selected = [candidates[i] for i in indices if 0 <= i < len(candidates)]
    selected = sorted(selected, key=lambda c: c.get("year", 0))
    return selected, intro


def curate(candidates_path: Path, output_path: Path) -> None:
    data = _load_candidates(candidates_path)
    candidates = data.get("candidates", [])

    api_key = load_env_var("LLM_API_KEY")
    if api_key:
        try:
            selected, intro = _llm_curation(candidates)
            print(f"LLM-Kuratierung: {candidates_path.name} -> {len(selected)} Fakten")
        except Exception as e:
            print(f"LLM-Kuratierung fehlgeschlagen, Fallback: {e}", file=sys.stderr)
            selected, intro = _fallback_curation(candidates)
    else:
        selected, intro = _fallback_curation(candidates)
        print(f"Fallback-Kuratierung: {candidates_path.name} -> {len(selected)} Fakten")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(
            {"date": data["date"], "facts": selected, "caption_intro": intro},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("source")
    p.add_argument("destination")
    p.add_argument("--month", action="store_true", help="Ganzen Monat auf einmal kuratieren")
    args = p.parse_args()

    src = Path(args.source)
    dst = Path(args.destination)

    if args.month:
        if not src.is_dir():
            print(f"Source muss ein Verzeichnis sein: {src}", file=sys.stderr)
            return 1
        dst.mkdir(parents=True, exist_ok=True)
        for day_file in sorted(src.glob("*.json")):
            curate(day_file, dst / day_file.name)
    else:
        curate(src, dst)

    return 0


if __name__ == "__main__":
    sys.exit(main())
