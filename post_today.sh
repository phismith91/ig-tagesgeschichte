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
