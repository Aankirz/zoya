#!/usr/bin/env bash
# One command to set up and run Zoya on a Mac: ./start.sh
# Installs everything, asks only for keys that are missing, downloads the local models, then starts Zoya.
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
ask_secret() {  # key, label, url, required(yes/no)
  local key="$1" label="$2" url="$3" required="$4" value=""
  [[ -n "$(env_value "$key")" ]] && return 0
  while true; do
    if [[ "$required" == "yes" ]]; then
      printf '%s%s%s (required) %s%s%s\n  paste key: ' "$BOLD" "$label" "$RESET" "$DIM" "$url" "$RESET"
    else
      printf '%s%s%s (optional, press Enter to skip) %s%s%s\n  paste key: ' "$BOLD" "$label" "$RESET" "$DIM" "$url" "$RESET"
    fi
    read -rs value; echo
    [[ -n "$value" || "$required" == "no" ]] && break
    echo "  This one is needed to run Zoya."
  done
  [[ -n "$value" ]] && set_env "$key" "$value"
  return 0
}

say_step "Keys (saved only in .env on this Mac; nothing you type is shown)"
default_env MODEL_PROVIDER openai
default_env BRAIN_MODEL gpt-5.6-terra
default_env VISION_MODEL gpt-5.6-terra
default_env ROUTER_MODEL gpt-5.6-luna
default_env ELEVENLABS_VOICE_ID Be3X8pg7kLN4vyyMC3QN
default_env AWS_REGION ap-south-1

ask_secret OPENAI_API_KEY "OpenAI API key: Zoya's brain" "https://platform.openai.com/api-keys" yes
ask_secret TINYFISH_API_KEY "TinyFish key: web search (free)" "https://tinyfish.ai" no
ask_secret ELEVENLABS_API_KEY "ElevenLabs key: backup voice" "https://elevenlabs.io/app/settings/api-keys" no
ask_secret SUPERMEMORY_API_KEY "Supermemory key: remembers your preferences" "https://console.supermemory.ai" no

if [[ -z "$(env_value AWS_PROFILE)" ]]; then
  printf '%sAWS profile name%s (optional: Amazon Polly voice, Translate, DynamoDB…; Enter to skip) %s`aws configure --profile <name>` first%s\n  profile: ' "$BOLD" "$RESET" "$DIM" "$RESET"
  read -r profile
  [[ -n "$profile" ]] && set_env AWS_PROFILE "$profile"
fi

say_step "Checking the OpenAI key"
key="$(env_value OPENAI_API_KEY)"
status="$(curl -s -o /dev/null -w '%{http_code}' --max-time 15 https://api.openai.com/v1/models -H "Authorization: Bearer $key" || echo 000)"
unset key
if [[ "$status" != "200" ]]; then
  set_env OPENAI_API_KEY ""
  fail "OpenAI rejected that key (HTTP $status). Run ./start.sh again and paste a valid key."
fi
echo "  OpenAI key works."

say_step "Downloading Zoya's on-device speech models (once)"
uv run python -m zoya.setup_models

say_step "One-time macOS permissions"
cat <<'EOF'
  In System Settings → Privacy & Security, allow the terminal app you're using for:
    • Microphone        (to hear you)
    • Accessibility     (to click, type and press media keys)
    • Screen Recording  (to see the screen)
  macOS will prompt the first time. After allowing, quit and reopen the terminal, then run ./start.sh again.
EOF

[[ "${1:-}" == "--setup-only" ]] && { echo; echo "Setup done. Run ./start.sh to start Zoya."; exit 0; }

say_step "Starting Zoya"
echo "  Say \"Hey Zoya\", or hold fn + Shift to talk. Quit: Control + Shift + Esc, or say \"Zoya, quit\"."
exec uv run python -m zoya.main --overlay "$@"
