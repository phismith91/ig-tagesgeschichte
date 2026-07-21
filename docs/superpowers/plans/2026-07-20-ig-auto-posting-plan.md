# Instagram Auto-Posting (Phase 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ein täglicher `post_today.sh`, der das für heute gerenderte Bild + Caption automatisch auf Instagram postet — via GitHub-gehostetem Bild und der Instagram Graph API (`graph.instagram.com`), ohne manuellen Eingriff.

**Architecture:** `post_today.sh` (bash) prüft `output/<Monat>/<Tag>/01.png` fürs heutige Datum, committed+pusht `output/` nach GitHub (`origin/master`), baut die `raw.githubusercontent.com`-URL, und ruft ein neues `post_instagram.py` auf, das den 2-Schritt Graph-API-Flow (`/media` → `/media_publish`) macht. Ein neues `ig-post.timer`/`.service`-Paar triggert das täglich um 06:10, 10 Minuten nach `ig-render.timer`.

**Tech Stack:** Bash (Wrapper, wie `fetch_next_month.sh`/`render_today.sh`), Python 3 + `requests` (bereits in `requirements.txt`? — wird in Task 1 geprüft) für den API-Call, systemd `--user` Timer/Service.

---

## Vorbedingung (bereits erledigt, nicht Teil dieses Plans)

- GitHub-Repo `phismith91/ig-tagesgeschichte` existiert, ist public, Remote `origin` gesetzt, Default-Branch **`master`** (nicht `main` — wichtig für die raw-URL).
- `.env` enthält bereits `META_ACCESS_TOKEN` (long-lived, ~60 Tage gültig) und `IG_USER_ID=28194940543437064` (App-Scoped ID aus `graph.instagram.com`-Flow, **nicht** die klassische Business-Account-ID).
- `.env` ist `.gitignore`d und `chmod 600`.

## Wichtige Korrektur ggü. Spec

Die Spec (`docs/superpowers/specs/2026-07-20-auto-posting-design.md`) geht von Branch `main` aus — real ist es `master`. Alle raw-URLs in diesem Plan nutzen `master`.

`output/` steht aktuell in `.gitignore` (Zeile 1) — das muss raus, sonst landet nie ein Bild auf GitHub. Task 1 entfernt die Zeile.

---

### Task 1: `.gitignore` — `output/` nicht mehr ignorieren

**Files:**
- Modify: `.gitignore`

- [ ] **Step 1: Zeile entfernen**

Aktueller Inhalt:
```
output/
__pycache__/
.worktrees/
.env
candidates/
.superpowers/
```

Neuer Inhalt (Zeile 1 gestrichen):
```
__pycache__/
.worktrees/
.env
candidates/
.superpowers/
```

- [ ] **Step 2: Bereits vorhandene Renders sichtbar machen**

```bash
git status --short output/ | head -5
```

Erwartet: mehrere `??`-Zeilen (untracked PNGs/Captions) — das ist ok, die werden erst in Task 4 gepusht, nicht hier.

- [ ] **Step 3: Commit**

```bash
git add .gitignore
git commit -m "chore: output/ nicht mehr ignorieren (wird für IG-Posting auf GitHub gehostet)"
```

---

### Task 2: `.env` um `.env.example`-Dokumentation ergänzen

**Files:**
- Create: `.env.example`

Aktuell gibt es keine `.env.example` — neue Variablen sollten dokumentiert sein, ohne echte Werte preiszugeben.

- [ ] **Step 1: Datei anlegen**

```
DEEPL_API_KEY=
META_ACCESS_TOKEN=
IG_USER_ID=
```

- [ ] **Step 2: Commit**

```bash
git add .env.example
git commit -m "docs: .env.example mit benötigten Variablen"
```

---

### Task 3: `post_instagram.py` — Graph-API 2-Schritt-Post

**Files:**
- Create: `post_instagram.py`
- Test: `tests/test_post_instagram.py`

Dieses Skript macht ausschließlich den API-Teil: nimmt Bild-URL + Caption, postet auf Instagram. Kein Git, kein Dateisystem-Scan (das macht `post_today.sh` in Task 5). So bleibt es isoliert testbar (Netzwerk-Calls gemockt).

- [ ] **Step 1: `requests` prüfen**

```bash
grep -q requests requirements.txt && echo "vorhanden" || echo "requests" >> requirements.txt
pip show requests >/dev/null 2>&1 && echo "installiert" || pip install requests
```

- [ ] **Step 2: Failing Test schreiben**

```python
# tests/test_post_instagram.py
from unittest.mock import patch, MagicMock

from post_instagram import post_to_instagram


@patch("post_instagram.requests.post")
def test_post_to_instagram_two_step_flow(mock_post):
    # Schritt 1: /media -> creation_id, Schritt 2: /media_publish -> media_id
    mock_post.side_effect = [
        MagicMock(status_code=200, json=lambda: {"id": "creation-123"}),
        MagicMock(status_code=200, json=lambda: {"id": "media-456"}),
    ]

    media_id = post_to_instagram(
        image_url="https://raw.githubusercontent.com/phismith91/ig-tagesgeschichte/master/output/2026-07/20/01.png",
        caption="Testcaption",
        ig_user_id="28194940543437064",
        access_token="dummy-token",
    )

    assert media_id == "media-456"
    assert mock_post.call_count == 2

    first_call = mock_post.call_args_list[0]
    assert first_call.args[0] == "https://graph.instagram.com/v21.0/28194940543437064/media"
    assert first_call.kwargs["data"]["image_url"] == "https://raw.githubusercontent.com/phismith91/ig-tagesgeschichte/master/output/2026-07/20/01.png"
    assert first_call.kwargs["data"]["caption"] == "Testcaption"
    assert first_call.kwargs["data"]["access_token"] == "dummy-token"

    second_call = mock_post.call_args_list[1]
    assert second_call.args[0] == "https://graph.instagram.com/v21.0/28194940543437064/media_publish"
    assert second_call.kwargs["data"]["creation_id"] == "creation-123"
    assert second_call.kwargs["data"]["access_token"] == "dummy-token"


@patch("post_instagram.requests.post")
def test_post_to_instagram_raises_on_api_error(mock_post):
    mock_post.return_value = MagicMock(
        status_code=400,
        json=lambda: {"error": {"message": "Invalid token"}},
    )

    try:
        post_to_instagram(
            image_url="https://raw.githubusercontent.com/phismith91/ig-tagesgeschichte/master/output/2026-07/20/01.png",
            caption="Testcaption",
            ig_user_id="28194940543437064",
            access_token="dummy-token",
        )
        assert False, "sollte RuntimeError werfen"
    except RuntimeError as e:
        assert "Invalid token" in str(e)
```

- [ ] **Step 3: Test laufen lassen, muss fehlschlagen**

Run: `cd .worktrees/feature-ig-auto-posting && python3 -m pytest tests/test_post_instagram.py -v`
Expected: FAIL mit `ModuleNotFoundError: No module named 'post_instagram'`

- [ ] **Step 4: Implementierung**

```python
# post_instagram.py
"""Postet ein Bild+Caption auf Instagram via graph.instagram.com (2-Schritt-Flow)."""
import sys

import requests

GRAPH_API_BASE = "https://graph.instagram.com/v21.0"


def post_to_instagram(image_url: str, caption: str, ig_user_id: str, access_token: str) -> str:
    creation_id = _create_media_container(image_url, caption, ig_user_id, access_token)
    return _publish_media(creation_id, ig_user_id, access_token)


def _create_media_container(image_url: str, caption: str, ig_user_id: str, access_token: str) -> str:
    res = requests.post(
        f"{GRAPH_API_BASE}/{ig_user_id}/media",
        data={"image_url": image_url, "caption": caption, "access_token": access_token},
    )
    data = res.json()
    if res.status_code != 200:
        raise RuntimeError(f"Instagram-Media-Container fehlgeschlagen: {data.get('error', {}).get('message', data)}")
    return data["id"]


def _publish_media(creation_id: str, ig_user_id: str, access_token: str) -> str:
    res = requests.post(
        f"{GRAPH_API_BASE}/{ig_user_id}/media_publish",
        data={"creation_id": creation_id, "access_token": access_token},
    )
    data = res.json()
    if res.status_code != 200:
        raise RuntimeError(f"Instagram-Publish fehlgeschlagen: {data.get('error', {}).get('message', data)}")
    return data["id"]


def main():
    import os

    if len(sys.argv) != 3:
        print("Nutzung: python3 post_instagram.py <image_url> <caption_datei>", file=sys.stderr)
        sys.exit(1)

    image_url = sys.argv[1]
    caption = open(sys.argv[2], encoding="utf-8").read()

    ig_user_id = os.environ["IG_USER_ID"]
    access_token = os.environ["META_ACCESS_TOKEN"]

    media_id = post_to_instagram(image_url, caption, ig_user_id, access_token)
    print(f"gepostet: {media_id}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Test laufen lassen, muss passen**

Run: `cd .worktrees/feature-ig-auto-posting && python3 -m pytest tests/test_post_instagram.py -v`
Expected: PASS (2 tests)

- [ ] **Step 6: Commit**

```bash
git add post_instagram.py tests/test_post_instagram.py requirements.txt
git commit -m "feat: post_instagram.py — 2-Schritt Graph-API-Post (media + media_publish)"
```

---

### Task 4: `post_today.sh` — Datei-Check, Git-Push, URL-Bau, Aufruf

**Files:**
- Create: `post_today.sh`
- Test: `tests/test_post_today.sh`

Folgt dem Muster von `render_today.sh`/`fetch_next_month.sh`: bash-Wrapper mit `REFERENCE_DATE`-Override für Tests, stubbed `python3`/`git` in `test_post_today.sh` (siehe `tests/test_fetch_next_month.sh` als Vorlage für den Stub-Mechanismus).

- [ ] **Step 1: Existierenden Test-Stub-Mechanismus ansehen**

```bash
cat tests/test_fetch_next_month.sh
```

(Nur lesen — dient als Vorlage für Step 2, kein eigener Schritt zum Ausführen.)

- [ ] **Step 2: Failing Test schreiben**

```bash
#!/bin/bash
# tests/test_post_today.sh
set -e
cd "$(dirname "$0")/.."

TMPDIR=$(mktemp -d)
trap "rm -rf $TMPDIR" EXIT

mkdir -p "$TMPDIR/bin"
cat > "$TMPDIR/bin/git" <<'EOF'
#!/bin/bash
echo "git $*" >> "$GIT_CALLS_LOG"
exit 0
EOF
chmod +x "$TMPDIR/bin/git"

cat > "$TMPDIR/bin/python3" <<'EOF'
#!/bin/bash
echo "python3 $*" >> "$PYTHON_CALLS_LOG"
exit 0
EOF
chmod +x "$TMPDIR/bin/python3"

export GIT_CALLS_LOG="$TMPDIR/git_calls.log"
export PYTHON_CALLS_LOG="$TMPDIR/python_calls.log"
touch "$GIT_CALLS_LOG" "$PYTHON_CALLS_LOG"

# Testfall 1: Tag ist gerendert -> Skript ruft git + python3 auf
mkdir -p "output/2099-01/15"
echo "fake" > "output/2099-01/15/01.png"
echo "Testcaption" > "output/2099-01/15/caption.txt"

PATH="$TMPDIR/bin:$PATH" REFERENCE_DATE="2099-01-15" ./post_today.sh

if ! grep -q "add output/" "$GIT_CALLS_LOG"; then
  echo "FEHLER: git add output/ wurde nicht aufgerufen"
  rm -rf "output/2099-01"
  exit 1
fi
if ! grep -q "push" "$GIT_CALLS_LOG"; then
  echo "FEHLER: git push wurde nicht aufgerufen"
  rm -rf "output/2099-01"
  exit 1
fi
if ! grep -q "post_instagram.py.*2099-01/15/01.png.*2099-01/15/caption.txt" "$PYTHON_CALLS_LOG"; then
  echo "FEHLER: post_instagram.py wurde nicht mit erwarteten Pfaden aufgerufen"
  cat "$PYTHON_CALLS_LOG"
  rm -rf "output/2099-01"
  exit 1
fi
if ! grep -q "raw.githubusercontent.com/phismith91/ig-tagesgeschichte/master/output/2099-01/15/01.png" "$PYTHON_CALLS_LOG"; then
  echo "FEHLER: raw-URL fehlt oder falsch aufgebaut"
  cat "$PYTHON_CALLS_LOG"
  rm -rf "output/2099-01"
  exit 1
fi
rm -rf "output/2099-01"

# Testfall 2: Tag ist NICHT gerendert -> Skript beendet sich still, ruft nichts auf
> "$GIT_CALLS_LOG"
> "$PYTHON_CALLS_LOG"
PATH="$TMPDIR/bin:$PATH" REFERENCE_DATE="2099-02-28" ./post_today.sh
if [ -s "$GIT_CALLS_LOG" ] || [ -s "$PYTHON_CALLS_LOG" ]; then
  echo "FEHLER: bei fehlendem Bild dürfen weder git noch python3 aufgerufen werden"
  exit 1
fi

echo "alle Tests bestanden"
```

- [ ] **Step 3: Ausführbar machen + Test laufen lassen, muss fehlschlagen**

```bash
chmod +x tests/test_post_today.sh
./tests/test_post_today.sh
```

Expected: FAIL (`post_today.sh: No such file or directory`)

- [ ] **Step 4: Implementierung**

```bash
#!/bin/bash
# ponytail: gleiches REFERENCE_DATE-Override-Muster wie render_today.sh/fetch_next_month.sh.
set -e
cd "$(dirname "$0")"
REF=${REFERENCE_DATE:-now}

MONTH=$(date -d "$REF" +%Y-%m)
DAY=$(date -d "$REF" +%d)
IMG="output/$MONTH/$DAY/01.png"
CAPTION="output/$MONTH/$DAY/caption.txt"

# ponytail: gleiches silent-skip wie render_today.sh — Tag noch nicht kuratiert/gerendert.
if [ ! -f "$IMG" ]; then
  exit 0
fi

git add "$IMG" "$CAPTION"
git diff --staged --quiet || git commit -m "render: $MONTH/$DAY"
git push

IMAGE_URL="https://raw.githubusercontent.com/phismith91/ig-tagesgeschichte/master/$IMG"
python3 post_instagram.py "$IMAGE_URL" "$CAPTION"
```

- [ ] **Step 5: Test laufen lassen, muss passen**

```bash
./tests/test_post_today.sh
```

Expected: `alle Tests bestanden`

- [ ] **Step 6: Commit**

```bash
git add post_today.sh tests/test_post_today.sh
git commit -m "feat: post_today.sh — täglicher Instagram-Post-Trigger"
```

---

### Task 5: systemd `ig-post.service` + `ig-post.timer`

**Files:**
- Create: `systemd/ig-post.service`
- Create: `systemd/ig-post.timer`

Folgt exakt dem Muster von `ig-render.service`/`ig-render.timer`.

- [ ] **Step 1: Referenz ansehen**

```bash
cat systemd/ig-render.service systemd/ig-render.timer
```

(Nur lesen, keine Ausführung nötig.)

- [ ] **Step 2: `ig-post.service` anlegen**

```ini
[Unit]
Description=ig-tagesgeschichte Instagram-Post

[Service]
Type=oneshot
WorkingDirectory=%h/projects/ig-tagesgeschichte
ExecStart=/bin/bash post_today.sh
```

- [ ] **Step 3: `ig-post.timer` anlegen**

```ini
[Unit]
Description=Täglicher Trigger für ig-post.service

[Timer]
OnCalendar=*-*-* 06:10:00
Persistent=true

[Install]
WantedBy=timers.target
```

- [ ] **Step 4: Statische Syntaxprüfung**

```bash
systemd-analyze --user verify systemd/ig-post.service systemd/ig-post.timer 2>&1 | grep -v "^$" || echo "keine Warnungen"
```

Expected: keine Fehlerzeilen (Pfad-Warnungen zu nicht-installierten Units sind ok, wie bei den bestehenden Units).

- [ ] **Step 5: Commit**

```bash
git add systemd/ig-post.service systemd/ig-post.timer
git commit -m "feat: ig-post Timer/Service (06:10, 10 Min nach Render)"
```

---

### Task 6: README-Ergänzung

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Abschnitt "Automatisierung (optional)" um Posting-Schritt ergänzen**

Im bestehenden Abschnitt "Automatisierung (optional)" (nach den `ig-render`-Install-Befehlen) ergänzen:

```markdown
### Instagram-Posting

Voraussetzung: `.env` enthält `META_ACCESS_TOKEN` (long-lived Access-Token) und `IG_USER_ID`
(App-Scoped Instagram-User-ID, siehe Meta-App-Dashboard → Instagram API → Generate access
tokens). Das Repo muss ein public GitHub-Repo mit Remote `origin` sein — Bilder werden über
`raw.githubusercontent.com` öffentlich gehostet, da die Instagram Graph API eine öffentliche
HTTPS-Bild-URL verlangt (kein Datei-Upload).

```bash
cp systemd/ig-post.service systemd/ig-post.timer ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now ig-post.timer
```

Läuft täglich um 06:10 (10 Minuten nach `ig-render.timer`) und postet automatisch, sofern
für den heutigen Tag ein gerendertes Bild existiert. Kein manueller Freigabe-Schritt —
die Kuratierung selbst ist die Freigabe.
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: README um Instagram-Posting-Setup ergänzt"
```

---

## Self-Review (durchgeführt)

**Spec-Abdeckung:**
- Datei-Check + silent skip → Task 4 ✅
- git add/commit/push → Task 4 ✅
- raw-URL-Bau → Task 4 ✅ (mit korrigiertem `master`-Branch)
- 2-Schritt Instagram-API → Task 3 ✅
- Neue `.env`-Variablen dokumentiert → Task 2 ✅
- `ig-post.timer` 06:10 → Task 5 ✅
- Fehlerverhalten (kein Retry, silent skip, klare Logs) → Task 4 (kein `|| true`, `set -e` sorgt für sichtbaren Fehler+Exit ungleich 0 bei git/API-Fehlern, landet in `journalctl`) ✅
- Facebook-Teil → bewusst nicht in diesem Plan (siehe Spec "Phasen-Entscheidung")

**Placeholder-Scan:** keine TBD/TODO gefunden.

**Typkonsistenz:** `post_to_instagram(image_url, caption, ig_user_id, access_token)` durchgängig in Test (Task 3) und `main()` (Task 3) gleich verwendet. `IMG`/`CAPTION`-Pfade in Task 4 konsistent mit `render.py`s Output-Struktur (`output/<Monat>/<Tag>/01.png` + `caption.txt`).
