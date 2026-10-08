#!/usr/bin/env sh
# Invoke the deployed group through its entry point, finance-fetcher, and save the answer.
#   sh scripts/run_group.sh [<arm-label>] [<repetitions>] [<quarter>]
# Each run is a fresh conversation and sandbox session for Fetcher (--new-session); the five
# callees are reached over A2A by Fetcher and RevenueAnalyst. Output:
# ../../runs/<date>_group/<arm>/<quarter>-r<k>.txt with the elapsed time and the final text
# (the trace id, when azd prints it, is in the saved output for App Insights).
set -u
ARM="${1:-group}"
REPS="${2:-1}"
QUARTER="${3:-2026-Q3}"
HERE="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$HERE/../../runs/$(date -u +%Y%m%d)_group/$ARM"
mkdir -p "$OUT"

PROMPT="Produce the quarterly finance report for $QUARTER. Follow the protocol: fetch the data, send the expense data to ExpenseAnalyst, then send the revenue data and the expense results to RevenueAnalyst, which obtains the TaxVerifier approval and has Writer deliver the report. Tell me which branch was taken, who approved, and show the report."

k=1
while [ "$k" -le "$REPS" ]; do
  f="$OUT/$QUARTER-r$k.txt"
  if [ -s "$f" ]; then k=$((k+1)); continue; fi
  start=$(date +%s)
  (cd "$HERE" && azd ai agent invoke finance-fetcher "$PROMPT" --new-session) > "$f.tmp" 2>&1
  end=$(date +%s)
  { echo "entry: finance-fetcher"; echo "arm: $ARM"; echo "quarter: $QUARTER"; echo "rep: $k";
    echo "elapsed_s: $((end-start))"; echo "prompt: $PROMPT"; echo "---"; cat "$f.tmp"; } > "$f"
  rm -f "$f.tmp"
  echo "done $QUARTER r$k ($((end-start))s) -> $f"
  k=$((k+1))
done
