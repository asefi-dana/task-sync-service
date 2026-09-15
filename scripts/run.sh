#!/usr/bin/env bash
set -euo pipefail

export HERMES_HOME="${HERMES_HOME:-/data/.service_state}"
export HOME="${HOME:-/data}"
export MESSAGING_CWD="${MESSAGING_CWD:-/data/workspace}"

mkdir -p "${HERMES_HOME}" "${HERMES_HOME}/logs" "${HERMES_HOME}/sessions" "${HERMES_HOME}/cron" "${HERMES_HOME}/pairing" "${MESSAGING_CWD}"

CONFIG_FILE="${HERMES_HOME}/config.yaml"
ENV_FILE="${HERMES_HOME}/.env"

echo "[task-runner] Initializing service environment..."

# Health check / status API server in background for Railway port probe
python3 /app/scripts/health_server.py &
HEALTH_PID=$!

# Ensure config.yaml
if [[ ! -f "$CONFIG_FILE" ]]; then
  echo "[task-runner] Creating default config..."
  cat > "$CONFIG_FILE" <<YAML_EOF
model: ${LLM_MODEL:-openrouter/anthropic/claude-3.5-sonnet}
YAML_EOF
fi

# Apply model override if given
if [[ -n "${LLM_MODEL:-}" ]]; then
  if grep -q "^model:" "$CONFIG_FILE" 2>/dev/null; then
    sed -i "s|^model:.*|model: ${LLM_MODEL}|" "$CONFIG_FILE"
  else
    sed -i "1s|^|model: ${LLM_MODEL}\n|" "$CONFIG_FILE"
  fi
fi

# Export Telegram / provider settings to .env
{
  echo "HERMES_HOME=${HERMES_HOME}"
  echo "MESSAGING_CWD=${MESSAGING_CWD}"
} > "$ENV_FILE"

for key in \
  OPENROUTER_API_KEY OPENAI_API_KEY OPENAI_BASE_URL ANTHROPIC_API_KEY LLM_MODEL \
  TELEGRAM_BOT_TOKEN TELEGRAM_ALLOWED_USERS TELEGRAM_ALLOW_ALL_USERS TELEGRAM_HOME_CHANNEL \
  DISCORD_BOT_TOKEN DISCORD_ALLOWED_USERS DISCORD_ALLOW_ALL_USERS \
  SLACK_BOT_TOKEN SLACK_APP_TOKEN SLACK_ALLOWED_USERS SLACK_ALLOW_ALL_USERS \
  GATEWAY_ALLOW_ALL_USERS GITHUB_TOKEN FIRECRAWL_API_KEY
do
  val="${!key:-}"
  if [[ -n "$val" ]]; then
    printf '%s=%s\n' "$key" "$val" >> "$ENV_FILE"
  fi
done

# Tail logs to stdout
touch "${HERMES_HOME}/logs/gateway.log"
tail -n 0 -F "${HERMES_HOME}/logs/gateway.log" 2>/dev/null &
TAIL_PID=$!

cleanup() {
  echo "[task-runner] Terminating services..."
  kill "$HEALTH_PID" 2>/dev/null || true
  kill "$TAIL_PID" 2>/dev/null || true
  if [[ -n "${GATEWAY_PID:-}" ]]; then
    kill "$GATEWAY_PID" 2>/dev/null || true
  fi
  exit 0
}
trap cleanup EXIT INT TERM

echo "[task-runner] Launching messaging gateway..."
hermes gateway &
GATEWAY_PID=$!

wait -n "$HEALTH_PID" "$GATEWAY_PID"
