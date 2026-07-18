#!/bin/bash
# ponytail: render.py läuft bei fehlendem Einzeltag-Pfad bereits still durch
# (leerer glob, exit 0) — kein Extra-Check nötig, falls Tag noch nicht kuratiert ist.
# REFERENCE_DATE nur für Tests.
set -e
cd "$(dirname "$0")"
REF=${REFERENCE_DATE:-now}
python3 render.py "curate/$(date -d "$REF" +%Y-%m)/$(date -d "$REF" +%d).json"
