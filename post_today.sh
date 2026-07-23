#!/bin/bash
# ponytail: gleiches REFERENCE_DATE-Override-Muster wie render_today.sh/fetch_next_month.sh.
set -e
cd "$(dirname "$0")"
REF=${REFERENCE_DATE:-now}

MONTH=$(date -d "$REF" +%Y-%m)
DAY=$(date -d "$REF" +%d)
DAY_DIR="output/$MONTH/$DAY"
CAPTION="$DAY_DIR/caption.txt"

# ponytail: gleiches silent-skip wie render_today.sh — Tag noch nicht kuratiert/gerendert.
if [ ! -f "$CAPTION" ]; then
  exit 0
fi

IMAGES=("$DAY_DIR"/*.png)

git add "${IMAGES[@]}" "$CAPTION"
# ponytail: no-op commit ("nothing to commit") darf das Skript nicht abbrechen —
# sonst kann ein Operator nach fehlgeschlagenem Instagram-Post nicht neu
# anstoßen, wenn der Git-Teil beim ersten Versuch schon durchgelaufen war.
git diff --staged --quiet || git commit -m "post: $MONTH/$DAY"
git push

# ponytail: set -e sorgt dafür, dass ein fehlgeschlagener push hier abbricht —
# kein Post ohne öffentlich erreichbare Bild-URLs.
IMAGE_URLS=()
for img in "${IMAGES[@]}"; do
  IMAGE_URLS+=("https://raw.githubusercontent.com/phismith91/ig-tagesgeschichte/master/$img")
done

python3 post_instagram.py "$CAPTION" "${IMAGE_URLS[@]}"
