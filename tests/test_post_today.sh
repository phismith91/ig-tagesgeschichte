#!/bin/bash
# tests/test_post_today.sh
# ponytail: Bash-Test mit Stub-PATH statt echtem git/python3 — testet nur Orchestrierung.
set -e
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$DIR"

TMP=$(mktemp -d)
trap 'rm -rf "$TMP" "$DIR/output/2099-01" "$DIR/output/2099-02"' EXIT

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

# Testfall 1: Tag ist gerendert -> Skript ruft git + python3 auf
mkdir -p "output/2099-01/15"
echo "fake" > "output/2099-01/15/01.png"
echo "Testcaption" > "output/2099-01/15/caption.txt"

REFERENCE_DATE="2099-01-15" ./post_today.sh

if ! grep -q "add output/2099-01/15/01.png output/2099-01/15/caption.txt" "$GIT_CALLS_LOG"; then
  echo "FAIL: git add wurde nicht mit den erwarteten Pfaden aufgerufen"
  cat "$GIT_CALLS_LOG"
  exit 1
fi
if ! grep -q "^git push$" "$GIT_CALLS_LOG"; then
  echo "FAIL: git push wurde nicht aufgerufen"
  cat "$GIT_CALLS_LOG"
  exit 1
fi
if ! grep -qE "post_instagram\.py .*2099-01/15/01\.png.*2099-01/15/caption\.txt" "$PYTHON_CALLS_LOG"; then
  echo "FAIL: post_instagram.py wurde nicht mit erwarteten Pfaden aufgerufen"
  cat "$PYTHON_CALLS_LOG"
  exit 1
fi
if ! grep -q "raw.githubusercontent.com/phismith91/ig-tagesgeschichte/master/output/2099-01/15/01.png" "$PYTHON_CALLS_LOG"; then
  echo "FAIL: raw-URL fehlt oder falsch aufgebaut"
  cat "$PYTHON_CALLS_LOG"
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

echo "PASS"
