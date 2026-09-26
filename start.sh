#!/usr/bin/env bash
# One command to set up and run Zoya on a Mac: ./start.sh
# Installs everything, downloads the local models, then starts Zoya. Zoya then talks the user through
# the macOS permissions and the Zoya key herself.
# Extra arguments go to Zoya, e.g. ./start.sh --no-wake. ./start.sh --setup-only stops before starting.
set -euo pipefail
cd "$(dirname "$0")"

BOLD=$'\033[1m'; DIM=$'\033[2m'; RESET=$'\033[0m'
say_step() { printf '\n%s▸ %s%s\n' "$BOLD" "$1" "$RESET"; }
fail() { printf '\n✗ %s\n' "$1" >&2; exit 1; }

say_step "Checking this Mac"
[[ "$(uname -s)" == "Darwin" ]] || fail "Zoya runs on macOS only."
[[ "$(uname -m)" == "arm64" ]] || fail "Zoya needs an Apple Silicon Mac (M1 or later) for on-device speech."
[[ -d "/Applications/Google Chrome.app" ]] || fail "Install Google Chrome first: https://www.google.com/chrome/"

if ! command -v uv >/dev/null 2>&1; then
  say_step "Installing uv (Python package manager)"
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi

say_step "Installing Zoya's dependencies (first run takes a few minutes)"
uv sync --quiet

ENV_FILE=".env"
[[ -f "$ENV_FILE" ]] || cp .env.example "$ENV_FILE"

env_value() { grep -E "^$1=" "$ENV_FILE" | head -1 | cut -d= -f2- || true; }
set_env() {
  local key="$1" value="$2" tmp
  tmp="$(mktemp)"
  if grep -qE "^$key=" "$ENV_FILE"; then
    awk -v k="$key" -v v="$value" 'BEGIN{FS=OFS="="} $1==k{print k"="v; next} {print}' "$ENV_FILE" >"$tmp"
  else
    cat "$ENV_FILE" >"$tmp"; printf '%s=%s\n' "$key" "$value" >>"$tmp"
  fi
  mv "$tmp" "$ENV_FILE"; chmod 600 "$ENV_FILE"
}
default_env() { [[ -n "$(env_value "$1")" ]] || set_env "$1" "$2"; }

say_step "Settings"
default_env MODEL_PROVIDER openai
default_env BRAIN_MODEL gpt-5.6-terra
default_env VISION_MODEL gpt-5.6-terra
default_env ROUTER_MODEL gpt-5.6-luna
default_env ELEVENLABS_VOICE_ID Be3X8pg7kLN4vyyMC3QN
default_env AWS_REGION ap-south-1

say_step "Downloading Zoya's on-device speech models (once)"
uv run python -m zoya.setup_models

[[ "${1:-}" == "--setup-only" ]] && { echo; echo "Setup done. Run ./start.sh to start Zoya."; exit 0; }

say_step "Starting Zoya"
echo "  Say \"Hey Zoya\", or hold fn + Shift to talk. Quit: Control + Shift + Esc, or say \"Zoya, quit\"."
exec uv run python -m zoya.supervisor --overlay "$@"
