#!/bin/bash
# Wakes the coordinator on either outcome: a push, or a builder that has stalled.
# Usage: watch_builder.sh <pane-id> <gui-sock> [idle_checks] [max_minutes]
set -u
PANE="$1"
export WEZTERM_UNIX_SOCKET="$2"
IDLE_LIMIT="${3:-4}"
MAX_MIN="${4:-180}"
W=/Applications/WezTerm.app/Contents/MacOS/wezterm

cd "$(dirname "$0")/.." || exit 1
base=$(git rev-parse HEAD)
prev=""
same=0

for ((i = 0; i < MAX_MIN * 2; i++)); do
  sleep 30
  cur=$(git rev-parse HEAD)
  if [ "$cur" != "$base" ]; then
    echo "PUSHED: $(git log --oneline -1)"
    exit 0
  fi
  text=$("$W" cli get-text --pane-id "$PANE" 2>/dev/null | tail -40)
  [ -z "$text" ] && { echo "STALLED: pane $PANE is gone"; exit 0; }
  hash=$(printf '%s' "$text" | shasum | cut -d' ' -f1)
  if [ "$hash" = "$prev" ]; then
    same=$((same + 1))
    if [ "$same" -ge "$IDLE_LIMIT" ]; then
      echo "STALLED: pane $PANE unchanged for $((same * 30))s with no push"
      printf '%s\n' "$text" | tail -12
      exit 0
    fi
  else
    same=0
  fi
  prev="$hash"
done
echo "TIMEOUT: no push and no stall detected in ${MAX_MIN}m"
