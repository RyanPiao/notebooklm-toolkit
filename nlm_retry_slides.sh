#!/usr/bin/env bash
# nlm_retry_slides.sh — regenerate ONLY the Phase 3 slide decks for a chapter
# whose transcripts are already uploaded (source_ids present in nlm-state.json).
#
# Use after a RATE_LIMITED failure left slide_artifact_ids = ["FAILED",...].
# Avoids re-uploading transcripts (which would duplicate sources in the notebook).
# Spaces requests to respect Google's slide-generation quota.
#
# Usage: bash nlm_retry_slides.sh <folder> [gap_seconds]
set -uo pipefail
FOLDER="${1:?Usage: $0 <lecture-folder> [gap_seconds]}"
GAP="${2:-90}"
TOOLKIT='/Users/openclaw/Resilio Sync/documents/notebooklm-toolkit'
STATE="$FOLDER/nlm-state.json"
NB=$(python3 -c "import json;print(json.load(open('$STATE'))['notebook_id'])")

# bash 3.2 (macOS /bin/bash) has no readarray — read the ids with a while loop.
SRCS=()
while IFS= read -r _line; do
  [[ -n "$_line" ]] && SRCS+=("$_line")
done < <(python3 -c "
import json;print('\n'.join(json.load(open('$STATE'))['source_ids']))")
[[ ${#SRCS[@]} -eq 3 ]] || { echo "❌ expected 3 transcript source_ids, got ${#SRCS[@]}"; exit 1; }

# Preserve decks that already succeeded: a partial failure like
# ["abc123","FAILED","FAILED"] should cost 2 requests, not 3. Quota is scarce.
EXISTING=()
while IFS= read -r _e; do EXISTING+=("$_e"); done < <(python3 -c "
import json
v=json.load(open('$STATE')).get('slide_artifact_ids') or ['FAILED']*3
print('\n'.join(v))")

IDS=()
for i in 1 2 3; do
  PREV="${EXISTING[$((i-1))]:-FAILED}"
  if [[ -n "$PREV" && "$PREV" != "FAILED" ]]; then
    echo "  part $i: keeping existing deck ${PREV:0:8}"
    IDS+=("$PREV")
    continue
  fi
  PART="$FOLDER/media/podcast_transcript_00${i}.txt"
  [[ -f "$PART" ]] || { echo "❌ missing $PART"; exit 1; }
  PROMPT=$(python3 "$TOOLKIT/build_slide_prompt.py" "$PART" "$FOLDER" "$i" 2>/dev/null) \
    || { echo "❌ build_slide_prompt.py failed for part $i"; exit 1; }
  echo "  part $i: requesting deck (source ${SRCS[$((i-1))]:0:8})"
  OUT=$(notebooklm generate slide-deck "$PROMPT" -s "${SRCS[$((i-1))]}" --json -n "$NB" 2>/dev/null)
  ID=$(echo "$OUT" | python3 -c "
import sys,json
try:
    d=json.load(sys.stdin)
    print('RATE_LIMITED' if d.get('code')=='RATE_LIMITED' else d.get('task_id',d.get('artifact_id','')))
except Exception: print('')")
  if [[ "$ID" == "RATE_LIMITED" ]]; then
    echo "  ❌ still rate limited on part $i — stopping, nothing written"
    exit 2
  fi
  if [[ -z "$ID" ]]; then
    echo "  ❌ no artifact id returned for part $i (not a rate limit) — stopping, nothing written"
    echo "     raw: $(echo "$OUT" | head -3)"
    exit 3
  fi
  echo "     -> $ID"
  IDS+=("$ID")
  [[ $i -lt 3 ]] && sleep "$GAP"
  true
done

python3 - "$STATE" "${IDS[@]}" <<'PY'
import json,sys
p, ids = sys.argv[1], sys.argv[2:]
d=json.load(open(p)); d["slide_artifact_ids"]=ids; d["phase_complete"]=3
json.dump(d,open(p,"w"),indent=2)
print(f"  ✓ state updated -> phase 3 with {len(ids)} deck ids; run nlm_auto_chain.sh to finish Phase 4")
PY
