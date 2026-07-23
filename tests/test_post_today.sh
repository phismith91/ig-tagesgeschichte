#!/bin/bash
# tests/test_post_today.sh
# ponytail: Bash-Test mit Stub-PATH statt echtem git/python3 — testet nur Orchestrierung.
set -e
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$DIR"

TMP=$(mktemp -d)
trap 'rm -rf "$TMP" "$DIR/output/2099-01" "$DIR/output/2099-02" "$DIR/output/2099-03"' EXIT

cat > "$TMP/git" <<'EOF'
#!/bin/bash
echo "git $*" >> "$GIT_CALLS_LOG"
exit 0
EOF
chmod +x "$TMP/git"

cat > "$TMP/python3" <<'EOF'
#!/bin/bash
echo "python3 $*" >> "$PYTHON_CALLS_LOG"
exit 0
EOF
chmod +x "$TMP/python3"

export PATH="$TMP:$PATH"
export GIT_CALLS_LOG="$TMP/git_calls.log"
export PYTHON_CALLS_LOG="$TMP/python_calls.log"
touch "$GIT_CALLS_LOG" "$PYTHON_CALLS_LOG"

# Testfall 1: Tag hat 3 gerenderte Slides -> alle 3 + Caption werden committet/gepusht,
# post_instagram.py bekommt Caption-Pfad zuerst, dann alle 3 URLs.
mkdir -p "output/2099-01/15"
echo "fake1" > "output/2099-01/15/01.png"
echo "fake2" > "output/2099-01/15/02.png"
echo "fake3" > "output/2099-01/15/03.png"
echo "Testcaption" > "output/2099-01/15/caption.txt"

REFERENCE_DATE="2099-01-15" ./post_today.sh

if ! grep -q "add output/2099-01/15/01.png output/2099-01/15/02.png output/2099-01/15/03.png output/2099-01/15/caption.txt" "$GIT_CALLS_LOG"; then
  echo "FAIL: git add wurde nicht mit allen 3 PNGs + Caption aufgerufen"
  cat "$GIT_CALLS_LOG"
  exit 1
fi
if ! grep -q "^git push$" "$GIT_CALLS_LOG"; then
  echo "FAIL: git push wurde nicht aufgerufen"
  exit 1
fi
PYCALL="$(cat "$PYTHON_CALLS_LOG")"
if [[ "$PYCALL" != *post_instagram.py\ output/2099-01/15/caption.txt\ *2099-01/15/01.png*2099-01/15/02.png*2099-01/15/03.png ]]; then
  echo "FAIL: post_instagram.py wurde nicht mit caption zuerst + allen 3 URLs aufgerufen"
  echo "GOT: $PYCALL"
  exit 1
fi
rm -rf "output/2099-01"

# Testfall 2: Tag ist NICHT gerendert -> Skript beendet sich still, ruft nichts auf
: > "$GIT_CALLS_LOG"
: > "$PYTHON_CALLS_LOG"
REFERENCE_DATE="2099-02-28" ./post_today.sh
if [ -s "$GIT_CALLS_LOG" ] || [ -s "$PYTHON_CALLS_LOG" ]; then
  echo "FAIL: bei fehlendem Bild dürfen weder git noch python3 aufgerufen werden"
  exit 1
fi

# Testfall 3: "nichts zu committen" darf das Skript NICHT abbrechen (Diff-Guard, siehe
# Commit 47547c1 aus Phase 1 — Regression-Test bleibt relevant, jetzt mit 2 Slides).
cat > "$TMP/git" <<'EOF'
#!/bin/bash
echo "git $*" >> "$GIT_CALLS_LOG"
case "$1" in
  commit) exit 1 ;;
  *) exit 0 ;;
esac
EOF
chmod +x "$TMP/git"

mkdir -p "output/2099-03/01"
echo "fake1" > "output/2099-03/01/01.png"
echo "fake2" > "output/2099-03/01/02.png"
echo "Testcaption" > "output/2099-03/01/caption.txt"
: > "$GIT_CALLS_LOG"
: > "$PYTHON_CALLS_LOG"

RC=0
REFERENCE_DATE="2099-03-01" ./post_today.sh || RC=$?
rm -rf "output/2099-03"

if [ "$RC" -ne 0 ]; then
  echo "FAIL: post_today.sh ist abgebrochen, obwohl 'nichts zu committen' nur den commit betrifft"
  exit 1
fi
if ! grep -q "^git push$" "$GIT_CALLS_LOG"; then
  echo "FAIL: git push wurde trotz No-Op-Commit nicht aufgerufen"
  exit 1
fi
if [ ! -s "$PYTHON_CALLS_LOG" ]; then
  echo "FAIL: post_instagram.py wurde trotz No-Op-Commit nicht aufgerufen"
  exit 1
fi

echo "PASS"
