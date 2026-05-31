#!/bin/bash
# AEO Audit Runner — GV Skincare
# Runs queries against LLM platforms and stores results.
#
# Usage:
#   ./audit.sh                           # all platforms, all queries, today's date
#   ./audit.sh --platform perplexity     # one platform only
#   ./audit.sh --queries 1,2,25          # specific query IDs only
#   ./audit.sh --date 2026-04-04         # override date (for backfills)
#   ./audit.sh --analyze                 # run analyze.py after collection

set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Load API keys from multiple possible locations
ENV_LOADED=false
for envfile in "$SCRIPT_DIR/.env" "$SCRIPT_DIR/../.env" "$HOME/repos/gotomarket/.env"; do
  if [ -f "$envfile" ]; then
    set -a
    source "$envfile"
    set +a
    ENV_LOADED=true
    echo "Loaded env from: $envfile"
    break
  fi
done

if [ "$ENV_LOADED" = false ]; then
  echo "WARNING: No .env file found. API keys must be set in environment."
fi

# Default missing keys to empty (prevents unbound variable errors)
: "${PERPLEXITY_API_KEY:=}" "${OPENAI_API_KEY:=}" "${ANTHROPIC_API_KEY:=}" "${GEMINI_API_KEY:=}" "${XAI_API_KEY:=}"

# Pre-flight: report which keys are available
echo "API keys:"
for key in PERPLEXITY_API_KEY OPENAI_API_KEY ANTHROPIC_API_KEY GEMINI_API_KEY XAI_API_KEY; do
  if [ -n "${!key}" ]; then
    echo "  $key: set"
  else
    echo "  $key: MISSING"
  fi
done
echo ""

# Defaults
DATE=$(date +%Y-%m-%d)
PLATFORMS="perplexity openai anthropic gemini grok"
QUERY_FILTER=""
RUN_ANALYZE=false

# Parse args
while [[ $# -gt 0 ]]; do
  case $1 in
    --platform)  PLATFORMS="$2"; shift 2 ;;
    --queries)   QUERY_FILTER="$2"; shift 2 ;;
    --date)      DATE="$2"; shift 2 ;;
    --analyze)   RUN_ANALYZE=true; shift ;;
    -h|--help)
      echo "Usage: $0 [--platform NAME] [--queries 1,2,3] [--date YYYY-MM-DD] [--analyze]"
      echo "Platforms: perplexity, openai, anthropic, gemini, grok"
      exit 0
      ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

QUERIES_FILE="$SCRIPT_DIR/queries.json"
if [ ! -f "$QUERIES_FILE" ]; then
  echo "ERROR: $QUERIES_FILE not found"
  exit 1
fi

# Check jq
if ! command -v jq &>/dev/null; then
  echo "ERROR: jq is required. Install with: brew install jq"
  exit 1
fi

# Build query ID list
# Skip queries with status="retired"; missing status defaults to active.
if [ -n "$QUERY_FILTER" ]; then
  QUERY_IDS=$(echo "$QUERY_FILTER" | tr ',' '\n')
else
  QUERY_IDS=$(jq -r '.queries[] | select((.status // "active") != "retired") | .id' "$QUERIES_FILE")
fi

total_queries=$(echo "$QUERY_IDS" | wc -l | tr -d ' ')
echo "=== GV Skincare AEO Audit: $DATE ==="
echo "Platforms: $PLATFORMS"
echo "Queries: $total_queries"
echo ""

# --- Platform runners ---

run_perplexity() {
  local qid=$1 qtext=$2 outfile=$3
  if [ -z "$PERPLEXITY_API_KEY" ]; then
    echo "  SKIP (no PERPLEXITY_API_KEY)"
    return
  fi
  curl -s --max-time 60 https://api.perplexity.ai/chat/completions \
    -H "Authorization: Bearer $PERPLEXITY_API_KEY" \
    -H "Content-Type: application/json" \
    -d "$(jq -n --arg q "$qtext" '{model:"sonar",messages:[{role:"user",content:$q}]}')" \
    > "$outfile" || true
}

run_openai() {
  local qid=$1 qtext=$2 outfile=$3
  if [ -z "$OPENAI_API_KEY" ]; then
    echo "  SKIP (no OPENAI_API_KEY)"
    return
  fi
  curl -s --max-time 120 https://api.openai.com/v1/responses \
    -H "Authorization: Bearer $OPENAI_API_KEY" \
    -H "Content-Type: application/json" \
    -d "$(jq -n --arg q "$qtext" '{
      model: "gpt-4.1",
      tools: [{type: "web_search"}],
      tool_choice: "required",
      input: $q
    }')" \
    > "$outfile" || true
}

run_anthropic() {
  local qid=$1 qtext=$2 outfile=$3
  if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "  SKIP (no ANTHROPIC_API_KEY)"
    return
  fi
  curl -s --max-time 120 https://api.anthropic.com/v1/messages \
    -H "x-api-key: $ANTHROPIC_API_KEY" \
    -H "anthropic-version: 2023-06-01" \
    -H "Content-Type: application/json" \
    -d "$(jq -n --arg q "$qtext" '{
      model: "claude-sonnet-4-6",
      max_tokens: 4096,
      tools: [{type: "web_search_20250305", name: "web_search", max_uses: 3}],
      messages: [{role: "user", content: $q}]
    }')" \
    > "$outfile" || true
}

run_gemini() {
  local qid=$1 qtext=$2 outfile=$3
  if [ -z "$GEMINI_API_KEY" ]; then
    echo "  SKIP (no GEMINI_API_KEY)"
    return
  fi
  curl -s --max-time 120 "https://generativelanguage.googleapis.com/v1beta/models/gemini-3-flash-preview:generateContent?key=$GEMINI_API_KEY" \
    -H "Content-Type: application/json" \
    -d "$(jq -n --arg q "$qtext" '{
      contents: [{parts: [{text: $q}]}],
      tools: [{google_search: {}}]
    }')" \
    > "$outfile" || true
}

run_grok() {
  local qid=$1 qtext=$2 outfile=$3
  if [ -z "$XAI_API_KEY" ]; then
    echo "  SKIP (no XAI_API_KEY)"
    return
  fi
  curl -s --max-time 120 https://api.x.ai/v1/responses \
    -H "Authorization: Bearer $XAI_API_KEY" \
    -H "Content-Type: application/json" \
    -d "$(jq -n --arg q "$qtext" '{
      model: "grok-4-fast-reasoning",
      tools: [{type: "web_search"}],
      input: [{role: "user", content: $q}]
    }')" \
    > "$outfile" || true
}

# --- Main loop ---

for platform in $PLATFORMS; do
  echo "--- $platform ---"

  OUTDIR="$SCRIPT_DIR/runs/$DATE/$platform"
  mkdir -p "$OUTDIR"

  count=0
  for qid in $QUERY_IDS; do
    qtext=$(jq -r --argjson id "$qid" '.queries[] | select(.id == $id) | .text' "$QUERIES_FILE")
    if [ -z "$qtext" ] || [ "$qtext" = "null" ]; then
      echo "  Q$qid: SKIP (not found in queries.json)"
      continue
    fi

    outfile="$OUTDIR/q${qid}.json"

    # Skip if already collected
    if [ -s "$outfile" ]; then
      echo "  Q$qid: skip (exists)"
      count=$((count+1))
      continue
    fi

    echo -n "  Q$qid: $qtext ... "

    case $platform in
      perplexity) run_perplexity "$qid" "$qtext" "$outfile" ;;
      openai)     run_openai "$qid" "$qtext" "$outfile" ;;
      anthropic)  run_anthropic "$qid" "$qtext" "$outfile" ;;
      gemini)     run_gemini "$qid" "$qtext" "$outfile" ;;
      grok)       run_grok "$qid" "$qtext" "$outfile" ;;
      *) echo "Unknown platform: $platform"; continue ;;
    esac

    if [ -s "$outfile" ]; then
      # Validate response is valid JSON (catches partial writes from timeouts)
      if ! jq empty "$outfile" &>/dev/null; then
        echo "INVALID JSON (likely timeout / partial write)"
        rm -f "$outfile"
      # Check for API errors (handles both {"error":"str"} and {"error":{"message":"str"}})
      elif jq -e '.error' "$outfile" &>/dev/null; then
        error=$(jq -r 'if (.error | type) == "string" then .error else (.error.message // .error.type // "unknown") end' "$outfile")
        echo "ERROR: $error"
        rm -f "$outfile"
      else
        echo "OK"
      fi
    else
      echo "EMPTY (no response / timeout)"
      rm -f "$outfile"
    fi

    count=$((count+1))
    # Rate limiting
    case $platform in
      anthropic) sleep 3 ;;
      *) sleep 1 ;;
    esac
  done

  echo "  $platform: $count queries processed"
  echo ""
done

echo "=== Collection complete ==="
echo "Results: $SCRIPT_DIR/runs/$DATE/"

# Run analysis if requested
if [ "$RUN_ANALYZE" = true ]; then
  echo ""
  echo "=== Running analysis ==="
  python3 "$SCRIPT_DIR/analyze.py" --date "$DATE" --compare
  echo ""
  echo "=== Generating dashboard ==="
  python3 "$SCRIPT_DIR/dashboard.py"
fi
