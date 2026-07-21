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

# ponytail: set -e sorgt dafür, dass ein fehlgeschlagener push hier abbricht —
# kein Post ohne öffentlich erreichbare Bild-URL.
IMAGE_URL="https://raw.githubusercontent.com/phismith91/ig-tagesgeschichte/master/$IMG"
python3 post_instagram.py "$IMAGE_URL" "$CAPTION"
