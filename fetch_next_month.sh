#!/bin/bash
# ponytail: date -d "+1 month" statt eigener Jahr/Monat-Rechnung.
# REFERENCE_DATE nur für Tests — im echten Betrieb ungesetzt, dann rechnet date ab "now".
set -e
cd "$(dirname "$0")"
REF=${REFERENCE_DATE:-now}
YEAR=$(date -d "$REF +1 month" +%Y)
MONTH=$(date -d "$REF +1 month" +%-m)
python3 fetch_candidates.py "$YEAR" "$MONTH"
