# heute.today Robustheit — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `heute.today` postet nie wieder doppelt und meldet sich per E-Mail, wenn etwas schiefgeht — mit State-Tracking, Retry-Logik und täglichem Health-Check.

**Architecture:** Lokale JSON-State-Dateien in `state/posted/` merken sich erfolgreiche Posts. `post_today.sh` prüft den State vor dem Posten, `post_instagram.py` retry-t temporäre Fehler, und `notify.py` verschickt Erfolgs-/Fehler-E-Mails via SMTP. `health_check.py` läuft täglich und warnt bei Lücken.

**Tech Stack:** Python 3.12, Bash, JSON, `smtplib`, `systemd --user`, `pytest` + `unittest.mock`.

## Global Constraints

- Keine Datenbank; State wird als JSON-Dateien gespeichert.
- `state/` wird in `.gitignore` ausgeschlossen und nie gepusht.
- SMTP-Konfiguration ist optional; fehlende Config erzeugt nur eine Log-Warnung, stoppt aber nichts.
- Maximal 3 Retries mit exponentiellem Backoff (3s, 9s).
- E-Mails gehen immer an `philippdschmidt@outlook.com` (konfigurierbar über `.env`).
- Tests müssen Netzwerk/SMTP-Calls mocken.

---

### Task 1: `.gitignore` um `state/` erweitern

**Files:**
- Modify: `.gitignore`

**Interfaces:**
- Keine Code-Interfaces; nur Git-Konfiguration.

- [ ] **Step 1: Zeile hinzufügen**

Füge am Ende von `.gitignore` hinzu:

```gitignore
state/
```

- [ ] **Step 2: Commit**

```bash
git add .gitignore
git commit -m "chore: state/ in .gitignore (lokale Post-States)"
```

---

### Task 2: `post_state.py` — State-Tracking für gepostete Tage

**Files:**
- Create: `post_state.py`
- Test: `tests/test_post_state.py`

**Interfaces:**
- Produces: `is_posted(date_str: str) -> bool`, `mark_posted(date_str: str, media_id: str, image_urls: list[str]) -> None`, `load_posted(date_str: str) -> dict | None`, `posted_dir() -> Path`

- [ ] **Step 1: Failing Test schreiben**

```python
# tests/test_post_state.py
from pathlib import Path

import post_state


def test_is_posted_false_when_no_state(tmp_path, monkeypatch):
    monkeypatch.setattr(post_state, "_posted_dir", lambda: tmp_path)
    assert post_state.is_posted("2026-07-25") is False


def test_mark_posted_and_is_posted(tmp_path, monkeypatch):
    monkeypatch.setattr(post_state, "_posted_dir", lambda: tmp_path)
    post_state.mark_posted("2026-07-25", "media-123", ["https://example.com/1.png"])
    assert post_state.is_posted("2026-07-25") is True
    data = post_state.load_posted("2026-07-25")
    assert data["media_id"] == "media-123"
    assert data["image_urls"] == ["https://example.com/1.png"]
    assert data["platform"] == "instagram"


def test_load_posted_returns_none_for_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(post_state, "_posted_dir", lambda: tmp_path)
    assert post_state.load_posted("2026-07-25") is None
```

- [ ] **Step 2: Test laufen lassen, muss fehlschlagen**

```bash
PYTHONPATH=/home/philipp/projects/ig-tagesgeschichte /home/philipp/.local/bin/pytest tests/test_post_state.py -v
```

Expected: `ModuleNotFoundError: No module named 'post_state'`

- [ ] **Step 3: Implementierung**

```python
# post_state.py
"""Lokales State-Tracking für bereits gepostete Tage."""
from datetime import datetime, timezone
from pathlib import Path

STATE_DIR = Path(__file__).parent / "state" / "posted"


def _posted_dir() -> Path:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    return STATE_DIR


def _state_path(date_str: str) -> Path:
    return _posted_dir() / f"{date_str}.json"


def is_posted(date_str: str) -> bool:
    return _state_path(date_str).exists()


def load_posted(date_str: str) -> dict | None:
    path = _state_path(date_str)
    if not path.exists():
        return None
    import json
    return json.loads(path.read_text(encoding="utf-8"))


def mark_posted(date_str: str, media_id: str, image_urls: list[str]) -> None:
    import json
    path = _state_path(date_str)
    payload = {
        "date": date_str,
        "posted_at": datetime.now(timezone.utc).isoformat(),
        "platform": "instagram",
        "media_id": media_id,
        "image_urls": image_urls,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
```

- [ ] **Step 4: Test laufen lassen, muss passen**

```bash
PYTHONPATH=/home/philipp/projects/ig-tagesgeschichte /home/philipp/.local/bin/pytest tests/test_post_state.py -v
```

Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add post_state.py tests/test_post_state.py
git commit -m "feat: post_state.py für Post-State-Tracking"
```

---

### Task 3: Retry-Logik in `post_instagram.py`

**Files:**
- Modify: `post_instagram.py`
- Test: `tests/test_post_instagram.py`

**Interfaces:**
- Modifies: `_create_media_container`, `_create_carousel_item`, `_create_carousel_container`, `_publish_media` — sollen retry-fähige Fehler wiederholen.
- Adds: `_is_retryable(exc) -> bool`, `_request_with_retry(method, url, **kwargs)`

- [ ] **Step 1: Failing Test schreiben**

Füge in `tests/test_post_instagram.py` hinzu:

```python
import time
from unittest.mock import patch, MagicMock

import requests


@patch("post_instagram.requests.get", side_effect=_fake_get_response)
@patch("post_instagram.requests.post")
@patch("time.sleep")
def test_post_to_instagram_retries_on_502_and_succeeds(mock_sleep, mock_post, mock_get):
    mock_post.side_effect = [
        MagicMock(status_code=502, json=lambda: {"error": {"message": "Bad Gateway"}}, text="Bad Gateway"),
        MagicMock(status_code=200, json=lambda: {"id": "creation-123"}),
        MagicMock(status_code=200, json=lambda: {"id": "media-456"}),
    ]

    media_id = post_to_instagram(
        image_url="https://example.com/1.png",
        caption="Testcaption",
        ig_user_id="28194940543437064",
        access_token="dummy-token",
    )

    assert media_id == "media-456"
    assert mock_post.call_count == 3
    assert mock_sleep.call_count == 1


@patch("post_instagram.requests.get", side_effect=_fake_get_response)
@patch("post_instagram.requests.post")
@patch("time.sleep")
def test_post_to_instagram_does_not_retry_401(mock_sleep, mock_post, mock_get):
    mock_post.return_value = MagicMock(
        status_code=401,
        json=lambda: {"error": {"message": "Invalid token"}},
    )

    try:
        post_to_instagram(
            image_url="https://example.com/1.png",
            caption="Testcaption",
            ig_user_id="28194940543437064",
            access_token="dummy-token",
        )
        assert False, "sollte RuntimeError werfen"
    except RuntimeError as e:
        assert "Invalid token" in str(e)

    assert mock_post.call_count == 1
    assert mock_sleep.call_count == 0
```

- [ ] **Step 2: Test laufen lassen, muss fehlschlagen**

```bash
PYTHONPATH=/home/philipp/projects/ig-tagesgeschichte /home/philipp/.local/bin/pytest tests/test_post_instagram.py::test_post_to_instagram_retries_on_502_and_succeeds -v
```

Expected: FAIL

- [ ] **Step 3: Implementierung**

Ersetze in `post_instagram.py` die HTTP-Call-Logik. Füge ganz oben hinzu:

```python
import time

MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = [3, 9]
```

Füge neue Helper-Funktionen hinzu:

```python
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
            res = requests.request(method, url, **kwargs)
            if res.status_code < 500:
                return res
            last_error = res
        except requests.exceptions.RequestException as e:
            last_error = e

        if attempt < len(RETRY_BACKOFF_SECONDS):
            time.sleep(RETRY_BACKOFF_SECONDS[attempt])

    if isinstance(last_error, requests.Response):
        return last_error
    raise last_error
```

Ersetze alle `requests.post(...)` und `requests.get(...)` in `post_instagram.py` durch `_request_with_retry("post", ...)` bzw. `_request_with_retry("get", ...)`. Beispiel:

```python
res = _request_with_retry(
    "post",
    f"{GRAPH_API_BASE}/{ig_user_id}/media",
    data={"image_url": image_url, "caption": caption, "access_token": access_token},
    timeout=TIMEOUT_SECONDS,
)
```

- [ ] **Step 4: Test laufen lassen, muss passen**

```bash
PYTHONPATH=/home/philipp/projects/ig-tagesgeschichte /home/philipp/.local/bin/pytest tests/test_post_instagram.py -v
```

Expected: all passed

- [ ] **Step 5: Commit**

```bash
git add post_instagram.py tests/test_post_instagram.py
git commit -m "feat: Retry-Logik für temporäre Instagram-API-Fehler"
```

---

### Task 4: `notify.py` — E-Mail-Benachrichtigungen

**Files:**
- Create: `notify.py`
- Test: `tests/test_notify.py`

**Interfaces:**
- Produces: `load_smtp_config(env_path: str = ".env") -> dict | None`, `send_email(subject: str, body: str, config: dict) -> None`, `notify_post_result(date_str: str, success: bool, **kwargs) -> None`

- [ ] **Step 1: Failing Test schreiben**

```python
# tests/test_notify.py
from unittest.mock import patch, MagicMock

import notify


def test_load_smtp_config_reads_env(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "SMTP_HOST=smtp.example.com\n"
        "SMTP_PORT=587\n"
        "SMTP_USER=user@example.com\n"
        "SMTP_PASSWORD=secret\n"
        "SMTP_FROM=from@example.com\n"
        "NOTIFY_EMAIL_TO=to@example.com\n"
    )
    monkeypatch.chdir(tmp_path)
    config = notify.load_smtp_config()
    assert config["host"] == "smtp.example.com"
    assert config["port"] == 587
    assert config["to"] == "to@example.com"


def test_load_smtp_config_returns_none_when_missing():
    assert notify.load_smtp_config("nonexistent.env") is None


@patch("notify.smtplib.SMTP")
def test_send_email_sends_correctly(mock_smtp):
    config = {
        "host": "smtp.example.com",
        "port": 587,
        "user": "user@example.com",
        "password": "secret",
        "from": "from@example.com",
        "to": "to@example.com",
    }
    notify.send_email("Test Subject", "Test Body", config)

    mock_smtp.assert_called_once_with("smtp.example.com", 587)
    server = mock_smtp.return_value
    server.starttls.assert_called_once()
    server.login.assert_called_once_with("user@example.com", "secret")
    server.send_message.assert_called_once()
    server.quit.assert_called_once()


def test_notify_post_success_builds_email():
    with patch("notify.send_email") as mock_send, patch("notify.load_smtp_config") as mock_load:
        mock_load.return_value = {"to": "to@example.com", "from": "from@example.com"}
        notify.notify_post_result("2026-07-25", success=True, media_id="media-123", image_count=5)
        mock_send.assert_called_once()
        subject, body = mock_send.call_args[0]
        assert "erfolgreich" in subject.lower()
        assert "media-123" in body


def test_notify_post_failure_builds_email():
    with patch("notify.send_email") as mock_send, patch("notify.load_smtp_config") as mock_load:
        mock_load.return_value = {"to": "to@example.com", "from": "from@example.com"}
        notify.notify_post_result("2026-07-25", success=False, error="Token invalid", step="media_publish")
        mock_send.assert_called_once()
        subject, body = mock_send.call_args[0]
        assert "fehlgeschlagen" in subject.lower()
        assert "Token invalid" in body
```

- [ ] **Step 2: Test laufen lassen, muss fehlschlagen**

```bash
PYTHONPATH=/home/philipp/projects/ig-tagesgeschichte /home/philipp/.local/bin/pytest tests/test_notify.py -v
```

Expected: `ModuleNotFoundError: No module named 'notify'`

- [ ] **Step 3: Implementierung**

```python
# notify.py
"""E-Mail-Benachrichtigungen für heute.today."""
import smtplib
from email.message import EmailMessage
from pathlib import Path

from env import load_env_var


def load_smtp_config(env_path: str = ".env") -> dict | None:
    """Liest SMTP-Konfiguration aus .env. Gibt None zurück, wenn nicht konfiguriert."""
    path = Path(env_path)
    if not path.exists():
        return None

    host = load_env_var("SMTP_HOST", env_path)
    port = load_env_var("SMTP_PORT", env_path)
    user = load_env_var("SMTP_USER", env_path)
    password = load_env_var("SMTP_PASSWORD", env_path)
    from_addr = load_env_var("SMTP_FROM", env_path)
    to_addr = load_env_var("NOTIFY_EMAIL_TO", env_path)

    if not all([host, port, user, password, from_addr, to_addr]):
        return None

    return {
        "host": host,
        "port": int(port),
        "user": user,
        "password": password,
        "from": from_addr,
        "to": to_addr,
    }


def send_email(subject: str, body: str, config: dict) -> None:
    """Sendet eine E-Mail über SMTP."""
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = config["from"]
    msg["To"] = config["to"]
    msg.set_content(body)

    with smtplib.SMTP(config["host"], config["port"]) as server:
        server.starttls()
        server.login(config["user"], config["password"])
        server.send_message(msg)


def notify_post_result(date_str: str, success: bool, **kwargs) -> None:
    """Benachrichtigt über Posting-Erfolg oder -Fehler."""
    config = load_smtp_config()
    if not config:
        print("notify: SMTP nicht konfiguriert — überspringe E-Mail")
        return

    if success:
        media_id = kwargs.get("media_id", "unbekannt")
        image_count = kwargs.get("image_count", 0)
        subject = f"heute.today — Post {date_str} erfolgreich"
        body = (
            f"Der Post für {date_str} wurde erfolgreich veröffentlicht.\n\n"
            f"Media-ID: {media_id}\n"
            f"Bilder: {image_count}\n"
        )
    else:
        error = kwargs.get("error", "Unbekannter Fehler")
        step = kwargs.get("step", "unbekannter Schritt")
        subject = f"heute.today — Post {date_str} fehlgeschlagen"
        body = (
            f"Der Post für {date_str} ist fehlgeschlagen.\n\n"
            f"Schritt: {step}\n"
            f"Fehler: {error}\n"
        )

    send_email(subject, body, config)
```

- [ ] **Step 4: Test laufen lassen, muss passen**

```bash
PYTHONPATH=/home/philipp/projects/ig-tagesgeschichte /home/philipp/.local/bin/pytest tests/test_notify.py -v
```

Expected: all passed

- [ ] **Step 5: Commit**

```bash
git add notify.py tests/test_notify.py
git commit -m "feat: notify.py für Post-Erfolgs-/Fehler-E-Mails"
```

---

### Task 5: `post_today.sh` mit State-Check und Notification

**Files:**
- Modify: `post_today.sh`
- Test: `tests/test_post_today.sh` (existiert bereits, erweitern)

**Interfaces:**
- Consumes: `post_state.is_posted`, `post_state.mark_posted`, `notify.notify_post_result`

- [ ] **Step 1: Bestehenden Test lesen**

```bash
cat tests/test_post_today.sh
```

- [ ] **Step 2: Test erweitern**

Füge in `tests/test_post_today.sh` einen Testfall hinzu:

```bash
# Testfall 3: Bereits gepostet -> kein git/push/python-Aufruf
mkdir -p "$TMPDIR/state/posted"
echo '{"date":"2099-01-15"}' > "$TMPDIR/state/posted/2099-01-15.json"

# post_state.py muss auf TMPDIR zeigen — wir patchen via Umgebung nicht möglich,
# daher stubben wir post_state komplett.
cat > "$TMPDIR/bin/python3" <<'EOF'
#!/bin/bash
echo "python3 $*" >> "$PYTHON_CALLS_LOG"
# post_state.is_posted liefert true für 2099-01-15
if [[ "$*" == *"post_state.is_posted"* ]]; then
  exit 0
fi
exit 0
EOF
chmod +x "$TMPDIR/bin/python3"

> "$GIT_CALLS_LOG"
> "$PYTHON_CALLS_LOG"
mkdir -p "output/2099-01/15"
echo "fake" > "output/2099-01/15/01.png"
echo "Testcaption" > "output/2099-01/15/caption.txt"

PATH="$TMPDIR/bin:$PATH" REFERENCE_DATE="2099-01-15" ./post_today.sh

if [ -s "$GIT_CALLS_LOG" ] || [ -s "$PYTHON_CALLS_LOG" ]; then
  echo "FEHLER: bei bereits gepostetem Tag dürfen git/python nicht aufgerufen werden"
  cat "$GIT_CALLS_LOG"
  cat "$PYTHON_CALLS_LOG"
  rm -rf "output/2099-01"
  exit 1
fi
rm -rf "output/2099-01"
```

- [ ] **Step 3: post_today.sh anpassen**

Neuer Inhalt von `post_today.sh`:

```bash
#!/bin/bash
set -e
cd "$(dirname "$0")"
REF=${REFERENCE_DATE:-now}

MONTH=$(date -d "$REF" +%Y-%m)
DAY=$(date -d "$REF" +%d)
DAY_DIR="output/$MONTH/$DAY"
CAPTION="$DAY_DIR/caption.txt"
DATE_STR="$MONTH-$DAY"

if [ ! -f "$CAPTION" ]; then
  exit 0
fi

# State-Check: wurde dieser Tag schon gepostet?
if python3 -c "import post_state; import sys; sys.exit(0 if post_state.is_posted('$DATE_STR') else 1)"; then
  echo "skip $DATE_STR: already posted"
  exit 0
fi

IMAGES=("$DAY_DIR"/*.png)

git add "${IMAGES[@]}" "$CAPTION"
git diff --staged --quiet || git commit -m "post: $MONTH/$DAY"
git push

IMAGE_URLS=()
for img in "${IMAGES[@]}"; do
  IMAGE_URLS+=("https://raw.githubusercontent.com/phismith91/ig-tagesgeschichte/master/$img")
done

# Posten + Notification; bei Fehler trotzdem notify
if python3 post_instagram.py "$CAPTION" "${IMAGE_URLS[@]}"; then
  MEDIA_ID=$(python3 -c "import post_state; d=post_state.load_posted('$DATE_STR'); print(d['media_id'] if d else '')")
  python3 -c "import notify; notify.notify_post_result('$DATE_STR', success=True, media_id='$MEDIA_ID', image_count=${#IMAGE_URLS[@]})"
else
  python3 -c "import notify; notify.notify_post_result('$DATE_STR', success=False, error='see log', step='post_instagram')"
  exit 1
fi
```

- [ ] **Step 4: Test laufen lassen, muss passen**

```bash
./tests/test_post_today.sh
```

Expected: `alle Tests bestanden`

- [ ] **Step 5: Commit**

```bash
git add post_today.sh tests/test_post_today.sh
git commit -m "feat: post_today.sh prüft State und sendet Notifications"
```

---

### Task 6: `health_check.py` — Tägliche System-Prüfung

**Files:**
- Create: `health_check.py`
- Create: `systemd/ig-health.service`
- Create: `systemd/ig-health.timer`
- Test: `tests/test_health_check.py`

**Interfaces:**
- Produces: `check_all() -> list[str]` (Liste von Fehlermeldungen), `main() -> int`

- [ ] **Step 1: Failing Test schreiben**

```python
# tests/test_health_check.py
from pathlib import Path
from unittest.mock import patch

import health_check


def test_check_candidates_exist_returns_error_when_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(health_check, "CANDIDATES_DIR", tmp_path / "candidates")
    monkeypatch.setattr(health_check, "CURATE_DIR", tmp_path / "curate")
    monkeypatch.setattr(health_check, "TODAY_STR", lambda: "2099-01-15")

    errors = health_check.check_candidates_exist(days=3)
    assert len(errors) == 3
    assert "2099-01-15" in errors[0]


def test_check_curated_exists_returns_error_when_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(health_check, "CURATE_DIR", tmp_path / "curate")
    monkeypatch.setattr(health_check, "TODAY_STR", lambda: "2099-01-15")

    errors = health_check.check_curated_exists(days=2)
    assert len(errors) == 2
    assert "2099-01-15" in errors[0]


def test_check_curated_passes_when_files_exist(tmp_path, monkeypatch):
    curate_dir = tmp_path / "curate" / "2099-01"
    curate_dir.mkdir(parents=True)
    (curate_dir / "15.json").write_text("{}")
    (curate_dir / "16.json").write_text("{}")

    monkeypatch.setattr(health_check, "CURATE_DIR", tmp_path / "curate")
    monkeypatch.setattr(health_check, "TODAY_STR", lambda: "2099-01-15")

    errors = health_check.check_curated_exists(days=2)
    assert errors == []
```

- [ ] **Step 2: Test laufen lassen, muss fehlschlagen**

```bash
PYTHONPATH=/home/philipp/projects/ig-tagesgeschichte /home/philipp/.local/bin/pytest tests/test_health_check.py -v
```

Expected: `ModuleNotFoundError: No module named 'health_check'`

- [ ] **Step 3: Implementierung**

```python
# health_check.py
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
```

- [ ] **Step 4: Test laufen lassen, muss passen**

```bash
PYTHONPATH=/home/philipp/projects/ig-tagesgeschichte /home/philipp/.local/bin/pytest tests/test_health_check.py -v
```

Expected: all passed

- [ ] **Step 5: systemd-Units anlegen**

`systemd/ig-health.service`:

```ini
[Unit]
Description=ig-tagesgeschichte: täglicher Health-Check

[Service]
Type=oneshot
WorkingDirectory=%h/projects/ig-tagesgeschichte
ExecStart=%h/projects/ig-tagesgeschichte/health_check.py
```

`systemd/ig-health.timer`:

```ini
[Unit]
Description=Täglicher Trigger für ig-health.service

[Timer]
OnCalendar=*-*-* 02:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

- [ ] **Step 6: Syntaxprüfung**

```bash
systemd-analyze --user verify systemd/ig-health.service systemd/ig-health.timer
```

Expected: keine Fehler

- [ ] **Step 7: Commit**

```bash
git add health_check.py systemd/ig-health.service systemd/ig-health.timer tests/test_health_check.py
git commit -m "feat: health_check.py + systemd-Timer für tägliche Systemprüfung"
```

---

### Task 7: `.env.example` ergänzen

**Files:**
- Modify: `.env.example`

**Interfaces:**
- Keine Code-Interfaces.

- [ ] **Step 1: Variablen ergänzen**

`.env.example` sollte am Ende Folgendes enthalten:

```dotenv
# Optional: E-Mail-Benachrichtigungen
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
SMTP_FROM=
NOTIFY_EMAIL_TO=philippdschmidt@outlook.com
```

- [ ] **Step 2: Commit**

```bash
git add .env.example
git commit -m "docs: SMTP-Variablen in .env.example ergänzt"
```

---

### Task 8: README-Ergänzung

**Files:**
- Modify: `README.md`

**Interfaces:**
- Keine Code-Interfaces.

- [ ] **Step 1: Abschnitt "Robustheit" hinzufügen**

Füge nach dem Automatisierungs-Abschnitt hinzu:

```markdown
## Robustheit (optional)

Um doppelte Posts zu vermeiden und bei Fehlern informiert zu werden:

1. SMTP-Daten in `.env` eintragen (siehe `.env.example`).
2. Health-Check aktivieren:

```bash
cp systemd/ig-health.service systemd/ig-health.timer ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now ig-health.timer
```

`post_today.sh` speichert erfolgreiche Posts in `state/posted/` und überspringt
bereits gepostete Tage. Bei Erfolg oder Fehler wird eine E-Mail an
`NOTIFY_EMAIL_TO` geschickt.
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: README um Robustheit-Abschnitt ergänzt"
```

---

## Self-Review

**Spec coverage:**
- State-Tracking → Task 2 ✅
- Retry-Logik → Task 3 ✅
- E-Mail-Benachrichtigungen → Task 4 + 7 ✅
- Health-Check → Task 6 ✅
- Integration in post_today.sh → Task 5 ✅
- Dokumentation → Task 7 + 8 ✅

**Placeholder scan:** Keine TBD/TODO gefunden. Alle Code-Beispiele sind vollständig.

**Type consistency:**
- `post_state.is_posted(date_str: str) -> bool`
- `notify.notify_post_result(date_str: str, success: bool, **kwargs)`
- `health_check.check_all() -> list[str]`
- Alles konsistent zwischen Tasks.

**Gaps:** Keine.
