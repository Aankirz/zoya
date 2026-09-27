#!/usr/bin/env bash
# One night of autotune: the proposing agent tries one guarded patch at a time until the
# budget or 07:00 local, then the report is written. See evals/autotune/program.md.
#
#   scripts/autotune-night.sh [--now] [--runs N] [--group "mac app"]
#
# --now starts outside 00:00-07:00. AUTOTUNE_BUDGET_CENTS caps the eval spend (the runner
# enforces it); AUTOTUNE_AGENT_MAX_USD, if set, caps the proposing agent's own API spend.
#
# claude flags, from https://code.claude.com/docs/en/cli-reference and .../permission-modes:
#   -p                            print mode, non-interactive
#   --permission-mode dontAsk     "Reads and pre-approved tools; anything that would prompt is
#                                 denied", the mode the docs give for "Locked-down CI and scripts"
#   --allowedTools                the only extra tools it may use, in permission-rule syntax
#                                 (Edit rules also cover Write; //path is an absolute path)
#   --append-system-prompt-file   program.md appended to the default system prompt
#   --max-budget-usd              print mode only
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKTREE="$(dirname "$ROOT")/zoya-autotune"
LOGS="$ROOT/logs/autotune"
PY="$ROOT/.venv/bin/python"
STOP_HOUR=7

NOW=0
RUNS=2
GROUP=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --now) NOW=1; shift ;;
    --runs) RUNS="$2"; shift 2 ;;
    --group) GROUP="$2"; shift 2 ;;
    *) echo "usage: $0 [--now] [--runs N] [--group GROUP]" >&2; exit 2 ;;
  esac
done

# Keep the Mac awake for the whole night: caffeinate -i holds an idle-sleep assertion for as
# long as the utility it runs (this script, re-executed once) is alive.
if [[ -z "${AUTOTUNE_CAFFEINATED:-}" ]]; then
  export AUTOTUNE_CAFFEINATED=1
  args=(--runs "$RUNS" --group "$GROUP")
  [[ $NOW -eq 1 ]] && args+=(--now)
  exec caffeinate -i "$0" "${args[@]}"
fi

hour=$((10#$(date +%H)))
if [[ $NOW -eq 0 && $hour -ge $STOP_HOUR ]]; then
  echo "autotune-night: it is $(date +%H:%M); runs only 00:00-07:00 local (or pass --now)" >&2
  exit 1
fi
command -v claude >/dev/null || { echo "autotune-night: claude is not on PATH" >&2; exit 1; }
[[ -x "$PY" ]] || { echo "autotune-night: no $PY (run ./start.sh --setup-only)" >&2; exit 1; }

cd "$ROOT" || exit 1
mkdir -p "$LOGS/patches"
tonight="$(date +%Y-%m-%d)"
agent_log="$LOGS/night-$tonight.log"

if [[ ! -d "$WORKTREE" ]]; then
  "$PY" -m evals.autotune init || exit 1
fi
if [[ ! -f "$LOGS/baseline.json" ]]; then
  "$PY" -m evals.autotune baseline --runs "$RUNS" --group "$GROUP" || {
    "$PY" -m evals.autotune report
    exit 1
  }
fi

# Seconds until the next 07:00 local; the agent is stopped then even mid-thought.
deadline_s="$("$PY" -c '
import datetime as d, sys
now = d.datetime.now().astimezone()
stop = now.replace(hour=int(sys.argv[1]), minute=0, second=0, microsecond=0)
print(int(((stop if stop > now else stop + d.timedelta(days=1)) - now).total_seconds()))
' "$STOP_HOUR")"

allowed=(
  "Read(/$WORKTREE/**)"  # //abs/path: $WORKTREE already starts with /
  "Edit(logs/autotune/patches/**)"
  "Bash(.venv/bin/python -m evals.autotune try *)"
  "Bash(date)"
  "Bash(date *)"
)
budget=()
[[ -n "${AUTOTUNE_AGENT_MAX_USD:-}" ]] && budget=(--max-budget-usd "$AUTOTUNE_AGENT_MAX_USD")

prompt="Run tonight's autotune program from your system prompt. Use --runs $RUNS and \
--group \"$GROUP\", the same as the baseline. Stop at 07:00 local or at the budget, \
whichever comes first."

echo "autotune-night: agent starts $(date +%H:%M), stops by $(printf '%02d' $STOP_HOUR):00" \
  | tee -a "$agent_log"
claude -p "$prompt" \
  --permission-mode dontAsk \
  --allowedTools "${allowed[@]}" \
  --append-system-prompt-file "$ROOT/evals/autotune/program.md" \
  ${budget[@]+"${budget[@]}"} \
  >>"$agent_log" 2>&1 &
agent=$!
# The watchdog takes its sleep down with it, so no stray sleep holds the output open.
(
  trap 'kill "$nap" 2>/dev/null; exit 0' TERM
  sleep "$deadline_s" &
  nap=$!
  wait "$nap" && kill -TERM "$agent" 2>/dev/null
) &
watchdog=$!
wait "$agent"
status=$?
kill "$watchdog" 2>/dev/null
echo "autotune-night: agent ended $(date +%H:%M) with status $status" | tee -a "$agent_log"

"$PY" -m evals.autotune report
exit "$status"
