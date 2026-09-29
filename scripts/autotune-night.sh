#!/usr/bin/env bash
# One night of autotune (D158): sync, census, verify, triage, publish, report. No agent runs at
# night; cloud sessions read the published night by day (evals/autotune/day.md).
#
#   scripts/autotune-night.sh [--now]
#
# --now starts outside 00:00-07:00. AUTOTUNE_BUDGET_CENTS caps the night's eval spend (the runner
# enforces it), and no eval starts after 07:00 local.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOGS="$ROOT/logs/autotune"
PY="$ROOT/.venv/bin/python"
STOP_HOUR=7
KEEP_NIGHTS=7  # night logs kept as text; older ones are gzipped

# The newest KEEP_NIGHTS night logs stay as text; older ones are gzipped. Bash 3.2 safe.
rotate_night_logs() {
  local logs=() log i
  for log in "$LOGS"/night-*.log; do
    [[ -f "$log" ]] && logs+=("$log")
  done
  for ((i = 0; i + KEEP_NIGHTS < ${#logs[@]}; i++)); do
    gzip -f "${logs[i]}"
  done
}

NOW=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --now) NOW=1; shift ;;
    *) echo "usage: $0 [--now]" >&2; exit 2 ;;
  esac
done

# Keep the Mac awake for the whole night: caffeinate -i holds an idle-sleep assertion for as
# long as the utility it runs (this script, re-executed once) is alive.
if [[ -z "${AUTOTUNE_CAFFEINATED:-}" ]]; then
  export AUTOTUNE_CAFFEINATED=1
  args=()
  [[ $NOW -eq 1 ]] && args+=(--now)
  exec caffeinate -i "$0" ${args[@]+"${args[@]}"}
fi

hour=$((10#$(date +%H)))
if [[ $NOW -eq 0 && $hour -ge $STOP_HOUR ]]; then
  echo "autotune-night: it is $(date +%H:%M); runs only 00:00-07:00 local (or pass --now)" >&2
  exit 1
fi
[[ -x "$PY" ]] || { echo "autotune-night: no $PY (run ./start.sh --setup-only)" >&2; exit 1; }

cd "$ROOT" || exit 1
mkdir -p "$LOGS"
export AUTOTUNE_NIGHT="$(date +%Y-%m-%d)"
night_log="$LOGS/night-$AUTOTUNE_NIGHT.log"
: >>"$night_log"
rotate_night_logs

# Epoch seconds of the next 07:00 local: no eval starts after it.
AUTOTUNE_DEADLINE="$("$PY" -c '
import datetime as d, sys
now = d.datetime.now().astimezone()
stop = now.replace(hour=int(sys.argv[1]), minute=0, second=0, microsecond=0)
stop = stop if stop > now else stop + d.timedelta(days=1)
print(int(stop.timestamp()))
' "$STOP_HOUR")"
export AUTOTUNE_DEADLINE

step() {
  echo "autotune-night: $1 starts $(date +%H:%M)" | tee -a "$night_log"
  "$PY" -m evals.autotune "$@" >>"$night_log" 2>&1
  local code=$?
  echo "autotune-night: $1 ended $(date +%H:%M) with status $code" | tee -a "$night_log"
  return "$code"
}

# A failed sync (main does not pass make check) stops the night; the report says why.
status=0
if step sync; then
  step census || status=1
  step verify || status=1
  step triage || status=1
  step publish || status=1
else
  status=1
fi
step report || status=1
exit "$status"
