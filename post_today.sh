#!/bin/bash
# ponytail: gleiches REFERENCE_DATE-Override-Muster wie render_today.sh/fetch_next_month.sh.
set -e
cd "$(dirname "$0")"
REF=${REFERENCE_DATE:-now}

MONTH=$(date -d "$REF" +%Y-%m)
DAY=$(date -d "$REF" +%d)
DAY_DIR="output/$MONTH/$DAY"
CAPTION="$DAY_DIR/caption.txt"
DATE_STR="$MONTH-$DAY"

# ponytail: gleiches silent-skip wie render_today.sh — Tag noch nicht kuratiert/gerendert.
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
# ponytail: no-op commit ("nothing to commit") darf das Skript nicht abbrechen —
# sonst kann ein Operator nach fehlgeschlagenem Instagram-Post nicht neu
# anstoßen, wenn der Git-Teil beim ersten Versuch schon durchgelaufen war.
git diff --staged --quiet || git commit -m "post: $MONTH/$DAY"
# ponytail: set -e sorgt dafür, dass ein fehlgeschlagener push hier abbricht —
# kein Post ohne öffentlich erreichbare Bild-URLs.
git push

IMAGE_URLS=()
for img in "${IMAGES[@]}"; do
  IMAGE_URLS+=("https://raw.githubusercontent.com/phismith91/ig-tagesgeschichte/master/$img")
done

# Posten + Notification; bei Fehler trotzdem notify
set +e
MEDIA_ID=$(python3 post_instagram.py "$CAPTION" "${IMAGE_URLS[@]}" | sed 's/gepostet: //')
POST_STATUS=${PIPESTATUS[0]}
set -e
if [ "$POST_STATUS" -eq 0 ] && [ -n "$MEDIA_ID" ]; then
  python3 -c "import post_state, sys; post_state.mark_posted('$DATE_STR', '$MEDIA_ID', sys.argv[1:])" "${IMAGE_URLS[@]}"
  python3 -c "import notify; notify.notify_post_result('$DATE_STR', success=True, media_id='$MEDIA_ID', image_count=${#IMAGE_URLS[@]})"
else
  python3 -c "import notify; notify.notify_post_result('$DATE_STR', success=False, error='see log', step='post_instagram')"
  exit 1
fi
