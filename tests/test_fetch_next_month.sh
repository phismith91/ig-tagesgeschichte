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
