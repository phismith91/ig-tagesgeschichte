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
