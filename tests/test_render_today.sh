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
