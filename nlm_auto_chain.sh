#!/usr/bin/env bash
# nlm_auto_chain.sh — Full NLM auto-chain from Phase 1 state
#
# Usage: bash nlm_auto_chain.sh <folder>
#
# Reads nlm-state.json (phase_complete: 1), then automatically:
#   Phase 2: Wait for audio → download podcast.m4a → Whisper transcription
#   Phase 3: Upload 3 transcript parts → trigger 3 slide deck generations
#   Phase 4: Wait for slides → download PDFs → remove watermarks → export 4K PNGs
#   → macOS notification when done
#
# Safe to re-run: skips already-completed phases, skips already-downloaded files.

set -euo pipefail

FOLDER="${1:?Usage: $0 <lecture-folder>}"
STATE_FILE="$FOLDER/nlm-state.json"
TOOLKIT='/Users/openclaw/Resilio Sync/Documents/notebooklm-toolkit'

# ── Dependency check ─────────────────────────────────────────────────────────
# Installs only what is actually missing. Older pip builds reject
# --break-system-packages, so try a plain install first and only fall back to
# the flag when pip refuses an externally-managed environment.
ensure_module() {
  local module="$1" package="$2"
  python3 -c "import $module" 2>/dev/null && return 0
  echo "  • installing $package (python3 -c 'import $module' failed)"
  pip3 install "$package" -q 2>/dev/null \
    || pip3 install "$package" --break-system-packages -q 2>/dev/null \
    || true
  python3 -c "import $module" 2>/dev/null && return 0
  echo "❌ $package is required but could not be installed for $(python3 -c 'import sys; print(sys.executable)')"
  echo "   Install it manually, then re-run: bash $0 $FOLDER"
  return 1
}

ensure_module fitz pymupdf
ensure_module cv2  opencv-python

# ── Read state ───────────────────────────────────────────────────────────────
[[ -f "$STATE_FILE" ]] || { echo "❌ nlm-state.json not found in $FOLDER"; exit 1; }

NB=$(python3    -c "import json; print(json.load(open('$STATE_FILE'))['notebook_id'])")
TOPIC=$(python3 -c "import json; print(json.load(open('$STATE_FILE'))['topic_title'])")
PHASE=$(python3 -c "import json; print(json.load(open('$STATE_FILE'))['phase_complete'])")
AUD=$(python3   -c "import json; print(json.load(open('$STATE_FILE'))['audio_artifact_id'])")
SLUG=$(python3  -c "import json; print(json.load(open('$STATE_FILE'))['slug'])")

# `grep -q` exits on first match and closes the pipe, so the notebooklm writer
# dies of SIGPIPE (141); under `set -o pipefail` that non-zero status made the
# poll loops read a COMPLETED artifact as "not ready". Capture first, then match
# with a here-string so no pipeline status is involved.
artifact_ready() {
  local out
  out=$(notebooklm artifact wait "$1" --timeout "${2:-10}" -n "$NB" 2>&1 || true)
  grep -q "✓" <<< "$out"
}

mkdir -p "$FOLDER/media"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔗 NLM Auto-Chain — $TOPIC"
echo "   Starting from phase_complete: $PHASE"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ════════════════════════════════════════════════
# PHASE 2: Download audio + transcribe
# ════════════════════════════════════════════════
if [[ "$PHASE" -lt 2 ]]; then
  echo ""
  echo "⏳ Phase 2: Waiting for audio artifact $AUD ..."

  # Poll until audio is ready (up to 30 min)
  ATTEMPTS=0
  while ! artifact_ready "$AUD" 10; do
    ATTEMPTS=$((ATTEMPTS + 1))
    [[ $ATTEMPTS -ge 36 ]] && { echo "❌ Audio timed out after 30 min"; exit 1; }
    echo "  [$(date '+%H:%M:%S')] Not ready yet — waiting 50s (attempt $ATTEMPTS/36)"
    sleep 50
  done

  echo "  ✓ Audio ready — downloading..."
  PODCAST="$FOLDER/media/${SLUG}-podcast.m4a"
  if [[ ! -f "$PODCAST" ]]; then
    notebooklm download audio "$PODCAST" -a "$AUD" -n "$NB" 2>&1
  else
    echo "  Skipping download — podcast.m4a already exists"
  fi

  echo "  🎙️  Transcribing with Whisper (model: small)..."
  python3 "$TOOLKIT/audio_transcriber.py" \
    "$PODCAST" \
    -o "$FOLDER/media/podcast_transcript.txt" \
    --split-parts 3 \
    --overlap 1000 \
    --model small \
    --language en 2>&1

  # Update state
  python3 -c "
import json
d = json.load(open('$STATE_FILE'))
d['phase_complete'] = 2
d['transcript_parts'] = [
    'media/podcast_transcript_001.txt',
    'media/podcast_transcript_002.txt',
    'media/podcast_transcript_003.txt'
]
json.dump(d, open('$STATE_FILE', 'w'), indent=2)
print('  ✓ Phase 2 complete — nlm-state.json updated')
"
  PHASE=2
fi

# ════════════════════════════════════════════════
# PHASE 3: Upload transcripts + trigger slide decks
# ════════════════════════════════════════════════
if [[ "$PHASE" -lt 3 ]]; then
  echo ""
  echo "📤 Phase 3: Uploading transcripts + triggering slide decks..."

  SRC_IDS=()
  SLD_IDS=()

  for i in 1 2 3; do
    PART_FILE="$FOLDER/media/podcast_transcript_00${i}.txt"
    echo "  Uploading Part $i → $(basename $PART_FILE)"
    SRC_ID=$(notebooklm source add "$PART_FILE" --json -n "$NB" 2>&1 \
      | python3 -c "import sys,json; print(json.load(sys.stdin)['source']['id'])")
    SRC_IDS+=("$SRC_ID")

    echo "  Waiting for indexing..."
    notebooklm source wait "$SRC_ID" -n "$NB" 2>&1

    # Build structured slide prompt from lecture pipeline files (with transcript fallback)
    echo "  Building slide prompt for Part $i..."
    SLIDE_PROMPT=$(python3 "$TOOLKIT/build_slide_prompt.py" "$PART_FILE" "$FOLDER" "$i" 2>/dev/null \
      || echo "Academic style, clean white background, Font: Open Sans. One concept per slide with clear headings.")
    echo "  Prompt: ${SLIDE_PROMPT:0:120}..."

    # Trigger slide deck with retry on rate limit (up to 5 attempts, escalating backoff)
    echo "  Triggering slide deck for Part $i..."
    SLD_ID=""
    for RETRY in 1 2 3 4 5; do
      # Capture stdout only (errors go to stderr which we discard for parsing)
      RAW_OUTPUT=$(notebooklm generate slide-deck -s "$SRC_ID" \
        "$SLIDE_PROMPT" \
        --json -n "$NB" 2>/dev/null || true)

      # Parse the JSON — check for rate limit OR extract task_id
      SLD_ID=$(echo "$RAW_OUTPUT" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    if d.get('error') and d.get('code') == 'RATE_LIMITED':
        print('RATE_LIMITED')
    else:
        print(d.get('task_id', d.get('artifact_id', '')))
except:
    print('')
" 2>/dev/null)

      if [[ "$SLD_ID" == "RATE_LIMITED" ]]; then
        SLD_ID=""
        WAIT=$((60 * RETRY))
        echo "  ⚠️  Rate limited (attempt $RETRY/5) — waiting ${WAIT}s..."
        sleep "$WAIT"
        continue
      elif [[ -n "$SLD_ID" ]]; then
        break
      else
        echo "  ⚠️  Empty/unparseable response (attempt $RETRY/5) — retrying in 30s..."
        sleep 30
      fi
    done

    if [[ -z "$SLD_ID" ]]; then
      echo "  ❌ Failed to generate slide deck for Part $i after 5 attempts"
      SLD_IDS+=("FAILED")
    else
      SLD_IDS+=("$SLD_ID")
      echo "  Slide artifact: $SLD_ID"
    fi

    # Brief pause between requests to avoid rate limiting
    [[ $i -lt 3 ]] && sleep 15
  done

  # Update state
  python3 -c "
import json
d = json.load(open('$STATE_FILE'))
d['phase_complete'] = 3
d['source_ids'] = $(python3 -c "import json; print(json.dumps(['${SRC_IDS[0]}','${SRC_IDS[1]}','${SRC_IDS[2]}']))")
d['slide_artifact_ids'] = $(python3 -c "import json; print(json.dumps(['${SLD_IDS[0]}','${SLD_IDS[1]}','${SLD_IDS[2]}']))")
json.dump(d, open('$STATE_FILE', 'w'), indent=2)
print('  ✓ Phase 3 complete — slide decks generating')
"
  PHASE=3
fi

# ════════════════════════════════════════════════
# PHASE 4: Wait for slides → download → clean → PNGs
# ════════════════════════════════════════════════
if [[ "$PHASE" -lt 4 ]]; then
  echo ""
  echo "⏳ Phase 4: Waiting for slide decks..."

  SLD_IDS=($(python3 -c "
import json
d = json.load(open('$STATE_FILE'))
ids = d.get('slide_artifact_ids', [])
print('\n'.join(ids))
"))

  # Poll until all 3 are ready (up to 30 min)
  ATTEMPTS=0
  while true; do
    READY=0
    for id in "${SLD_IDS[@]}"; do
      artifact_ready "$id" 5 && READY=$((READY+1)) || true
    done
    echo "  [$(date '+%H:%M:%S')] $READY/3 slide decks ready (attempt $((ATTEMPTS+1))/30)"
    [[ $READY -ge 3 ]] && break
    ATTEMPTS=$((ATTEMPTS+1))
    [[ $ATTEMPTS -ge 30 ]] && { echo "⚠️  Timeout — only $READY/3 ready; downloading what's available"; break; }
    sleep 60
  done

  echo ""
  echo "⬇️  Downloading slide PDFs..."
  DOWNLOADED=()
  PART=1
  for id in "${SLD_IDS[@]}"; do
    OUT="$FOLDER/media/slides_part${PART}.pdf"
    if [[ -f "$OUT" ]]; then
      echo "  Part $PART — skipping, already exists: $OUT"
    else
      echo "  Part $PART → $OUT"
      notebooklm download slide-deck "$OUT" -a "$id" -n "$NB" 2>&1
    fi
    DOWNLOADED+=("$OUT")
    PART=$((PART+1))
  done

  echo ""
  echo "🧹  Removing watermarks + exporting 4K PNGs..."
  for pdf in "${DOWNLOADED[@]}"; do
    echo "  Processing: $(basename $pdf)"
    python3 "$TOOLKIT/pdf_cleaner_core.py" \
      "$pdf" \
      -o "$FOLDER/media" \
      --resolution 3840 --supersample 3 --sharpness 1.5 2>&1
  done

  # Update state
  python3 -c "
import json
d = json.load(open('$STATE_FILE'))
d['phase_complete'] = 4
json.dump(d, open('$STATE_FILE', 'w'), indent=2)
print('  ✓ Phase 4 complete — nlm-state.json updated')
"
fi

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo "✅ NLM Auto-Chain complete — $TOPIC"
echo "   $(ls "$FOLDER/media/"*.pdf 2>/dev/null | wc -l | tr -d ' ') PDFs · $(ls -d "$FOLDER/media/slides_part"*/ 2>/dev/null | wc -l | tr -d ' ') PNG folders"
echo "   Media: $FOLDER/media/"

osascript -e "display notification \"podcast + transcripts + slide decks (4K PNGs) — all done\" with title \"✅ NLM Complete: $TOPIC\" sound name \"Glass\"" 2>/dev/null || true
