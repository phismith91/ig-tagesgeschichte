# Workflow-Automatisierung Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Kein manueller `python3 ...`-Aufruf mehr im Alltag — nur noch Kuratieren im Browser (Klicks) bleibt manuell.

**Architecture:** Zwei kleine Bash-Wrapper (`fetch_next_month.sh`, `render_today.sh`) plus fünf systemd-`--user`-Units (`systemd/`-Verzeichnis) für Dauerdienst (Kuratier-Server), Monats-Timer (Fetch) und Tages-Timer (Render). Siehe `docs/superpowers/specs/2026-07-18-workflow-automation-design.md` für Details und Fehlerverhalten.

**Tech Stack:** Bash, systemd `--user` units. Kein neues Python, keine neue Dependency.

**Wichtig — was dieser Plan NICHT tut:** Er installiert/aktiviert die Units NICHT auf dem echten System (kein `systemctl --user enable --now`, kein `loginctl enable-linger`). Das ist ein bewusster manueller Schritt für den Nutzer selbst (README dokumentiert ihn), weil er den Rechner dauerhaft verändert (persistenter Dienst, monatlicher automatischer Fetch der ggf. die DeepL-API nutzt). Dieser Plan erzeugt nur die Dateien + Tests + Doku.

---

### Task 1: `fetch_next_month.sh`

**Files:**
- Create: `fetch_next_month.sh`
- Test: `tests/test_fetch_next_month.sh`

- [ ] **Step 1: Write the failing test**

```bash
#!/bin/bash
# tests/test_fetch_next_month.sh
# ponytail: Bash-Test statt pytest — testet nur Datumsrechnung, kein Python involviert.
set -e
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

cat > "$TMP/python3" <<'EOF'
#!/bin/bash
echo "$@" > "$IG_TEST_CAPTURE"
EOF
chmod +x "$TMP/python3"
export PATH="$TMP:$PATH"
export IG_TEST_CAPTURE="$TMP/captured"

REFERENCE_DATE=2026-03-10 "$DIR/fetch_next_month.sh"
GOT="$(cat "$TMP/captured")"
[[ "$GOT" == "fetch_candidates.py 2026 4" ]] || { echo "FAIL normal: got '$GOT'"; exit 1; }

REFERENCE_DATE=2026-12-15 "$DIR/fetch_next_month.sh"
GOT="$(cat "$TMP/captured")"
[[ "$GOT" == "fetch_candidates.py 2027 1" ]] || { echo "FAIL rollover: got '$GOT'"; exit 1; }

REFERENCE_DATE=2026-01-31 "$DIR/fetch_next_month.sh"
GOT="$(cat "$TMP/captured")"
[[ "$GOT" == "fetch_candidates.py 2026 2" ]] || { echo "FAIL month-end overflow: got '$GOT'"; exit 1; }

echo "PASS"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `chmod +x tests/test_fetch_next_month.sh && ./tests/test_fetch_next_month.sh`
Expected: FAIL — `fetch_next_month.sh: No such file or directory`

- [ ] **Step 3: Write `fetch_next_month.sh`**

```bash
#!/bin/bash
# ponytail: date -d "+1 month" statt eigener Jahr/Monat-Rechnung.
# REFERENCE_DATE nur für Tests — im echten Betrieb ungesetzt, dann rechnet date ab "now".
set -e
cd "$(dirname "$0")"
REF=${REFERENCE_DATE:-now}
# ponytail: erst auf den 1. des Monats verankern, sonst rechnet "date -d +1 month"
# an Tagen 29-31 falsch (überläuft in den übernächsten Monat statt in den nächsten).
ANCHOR=$(date -d "$REF" +%Y-%m-01)
YEAR=$(date -d "$ANCHOR +1 month" +%Y)
MONTH=$(date -d "$ANCHOR +1 month" +%-m)
python3 fetch_candidates.py "$YEAR" "$MONTH"
```

```bash
chmod +x fetch_next_month.sh
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./tests/test_fetch_next_month.sh`
Expected: `PASS`

- [ ] **Step 5: Commit**

```bash
git add fetch_next_month.sh tests/test_fetch_next_month.sh
git commit -m "feat: fetch_next_month.sh Wrapper für monatlichen Fetch-Timer"
```

---

### Task 2: `render_today.sh`

**Files:**
- Create: `render_today.sh`
- Test: `tests/test_render_today.sh`

- [ ] **Step 1: Write the failing test**

```bash
#!/bin/bash
# tests/test_render_today.sh
set -e
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

cat > "$TMP/python3" <<'EOF'
#!/bin/bash
echo "$@" > "$IG_TEST_CAPTURE"
EOF
chmod +x "$TMP/python3"
export PATH="$TMP:$PATH"
export IG_TEST_CAPTURE="$TMP/captured"

REFERENCE_DATE=2026-08-07 "$DIR/render_today.sh"
GOT="$(cat "$TMP/captured")"
[[ "$GOT" == "render.py curate/2026-08/07.json" ]] || { echo "FAIL: got '$GOT'"; exit 1; }

echo "PASS"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `chmod +x tests/test_render_today.sh && ./tests/test_render_today.sh`
Expected: FAIL — `render_today.sh: No such file or directory`

- [ ] **Step 3: Write `render_today.sh`**

```bash
#!/bin/bash
# ponytail: render.py läuft bei fehlendem Einzeltag-Pfad bereits still durch
# (leerer glob, exit 0) — kein Extra-Check nötig, falls Tag noch nicht kuratiert ist.
# REFERENCE_DATE nur für Tests.
set -e
cd "$(dirname "$0")"
REF=${REFERENCE_DATE:-now}
python3 render.py "curate/$(date -d "$REF" +%Y-%m)/$(date -d "$REF" +%d).json"
```

```bash
chmod +x render_today.sh
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./tests/test_render_today.sh`
Expected: `PASS`

- [ ] **Step 5: Commit**

```bash
git add render_today.sh tests/test_render_today.sh
git commit -m "feat: render_today.sh Wrapper für täglichen Render-Timer"
```

---

### Task 3: systemd-Units

**Files:**
- Create: `systemd/ig-curate-server.service`
- Create: `systemd/ig-fetch.service`
- Create: `systemd/ig-fetch.timer`
- Create: `systemd/ig-render.service`
- Create: `systemd/ig-render.timer`

- [ ] **Step 1: Create `systemd/ig-curate-server.service`**

```ini
[Unit]
Description=ig-tagesgeschichte Kuratier-Server
StartLimitIntervalSec=0

[Service]
WorkingDirectory=%h/projects/ig-tagesgeschichte
ExecStart=/usr/bin/python3 curate_server.py
Restart=always
RestartSec=5

[Install]
WantedBy=default.target
```

`RestartSec=5` + `StartLimitIntervalSec=0`: verhindert, dass ein Crash-Loop
(z.B. kaputte venv nach Update) das systemd-Startlimit sprengt und den
Dienst dauerhaft im `failed`-Zustand stehen lässt (Code-Review-Fund).

- [ ] **Step 2: Create `systemd/ig-fetch.service`**

```ini
[Unit]
Description=ig-tagesgeschichte: Kandidaten für nächsten Monat holen

[Service]
Type=oneshot
WorkingDirectory=%h/projects/ig-tagesgeschichte
ExecStart=%h/projects/ig-tagesgeschichte/fetch_next_month.sh
```

- [ ] **Step 3: Create `systemd/ig-fetch.timer`**

```ini
[Unit]
Description=Monatlicher Trigger für ig-fetch.service

[Timer]
OnCalendar=*-*-25 03:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

- [ ] **Step 4: Create `systemd/ig-render.service`**

```ini
[Unit]
Description=ig-tagesgeschichte: heutigen Tag rendern

[Service]
Type=oneshot
WorkingDirectory=%h/projects/ig-tagesgeschichte
ExecStart=%h/projects/ig-tagesgeschichte/render_today.sh
```

- [ ] **Step 5: Create `systemd/ig-render.timer`**

```ini
[Unit]
Description=Täglicher Trigger für ig-render.service

[Timer]
OnCalendar=*-*-* 06:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

- [ ] **Step 6: Verify syntax (does not install/enable anything)**

Run for each of the 5 files:
```bash
systemd-analyze --user verify systemd/ig-curate-server.service
systemd-analyze --user verify systemd/ig-fetch.service
systemd-analyze --user verify systemd/ig-fetch.timer
systemd-analyze --user verify systemd/ig-render.service
systemd-analyze --user verify systemd/ig-render.timer
```
Expected: no output (no output = no errors). `systemd-analyze verify` only checks the file content statically — it does not install, copy, or enable anything.

- [ ] **Step 7: Commit**

```bash
git add systemd/
git commit -m "feat: systemd-Units für Kuratier-Server, Fetch- und Render-Timer"
```

---

### Task 4: README-Ergänzung

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add an "Automatisierung (optional)" section after the existing "## Workflow" section**

Insert this new section directly after the numbered 4-step workflow list and before "## Design ändern":

```markdown
## Automatisierung (optional)

Fetch, Render und der Kuratier-Server lassen sich als systemd-`--user`-Units
laufen lassen, dann bleibt als manueller Schritt nur noch das Kuratieren im
Browser (Schritt 2). Einmaliges Setup:

```bash
mkdir -p ~/.config/systemd/user
cp systemd/*.service systemd/*.timer ~/.config/systemd/user/
chmod +x fetch_next_month.sh render_today.sh
loginctl enable-linger $USER
systemctl --user daemon-reload
systemctl --user enable --now ig-curate-server.service
systemctl --user enable --now ig-fetch.timer
systemctl --user enable --now ig-render.timer
```

`loginctl enable-linger $USER` ist nötig, damit die Dienste auch ohne aktive
Login-Session weiterlaufen (z.B. nach Neustart ohne Einloggen).

Fetch läuft am 25. jeden Monats (holt den Folgemonat), Render täglich um
06:00 Uhr für den aktuellen Tag — überspringt still, falls der Tag noch
nicht kuratiert wurde.

Testen / nachschauen:
```bash
systemctl --user start ig-fetch.service      # manuell antriggern
journalctl --user -u ig-fetch -f             # Log verfolgen
systemctl --user list-timers                 # Timer-Übersicht
```
```

- [ ] **Step 2: Verify the file renders sensibly**

Run: `cat README.md` and confirm the new section sits between the workflow list and "## Design ändern", with no broken markdown fences.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: Automatisierungs-Setup (systemd) im README ergänzt"
```

---

## Nach Abschluss aller Tasks

Dispatch final code-reviewer subagent über den gesamten Diff (Task 1–4), dann `superpowers:finishing-a-development-branch`.

**Hinweis für den letzten Reviewer:** Es ist erwartet und korrekt, dass kein Task tatsächlich `systemctl --user enable --now` oder `loginctl enable-linger` auf dem echten System ausführt — das ist laut Spec bewusst ein manueller Schritt für den Nutzer (dauerhafte Systemänderung, monatlicher automatischer API-Verbrauch). Das Fehlen dieser Ausführung ist kein Findings-würdiges Problem.
