#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  scripts/smoke-agent-chat.sh --message "Hello"

Options:
  --message TEXT             User message to send to the agent
  --provider NAME           Preset: anthropic | openai | openrouter | custom
  --model NAME              Model name passed through X-Model-Name
  --base-url URL            Base URL passed through X-Model-Base-Url
  --api-key KEY             API key passed through X-Model-Api-Key
  --reference-models CSV    Optional comma-separated reference models
  --conversation-id UUID    Reuse an existing conversation for resumed-session testing
  --user-id UUID            Stable user ID for smoke testing
  --user-email EMAIL        Stable user email for smoke testing
  --agent-url URL           Agent chat endpoint
  --help                    Show this help text

Environment fallbacks:
  AGENT_URL
  SMOKE_PROVIDER
  SMOKE_MODEL_NAME
  SMOKE_MODEL_BASE_URL
  SMOKE_MODEL_API_KEY
  SMOKE_REFERENCE_MODELS
  SMOKE_CONVERSATION_ID
  SMOKE_USER_ID
  SMOKE_USER_EMAIL
  ANTHROPIC_API_KEY
  OPENAI_API_KEY
  OPENROUTER_API_KEY

Examples:
  scripts/smoke-agent-chat.sh \
    --provider anthropic \
    --model claude-sonnet-4-5 \
    --message "What is today's date?"

  scripts/smoke-agent-chat.sh \
    --provider openai \
    --model gpt-5 \
    --conversation-id 11111111-1111-4111-8111-111111111111 \
    --message "What did I just ask you?"
EOF
}

provider="${SMOKE_PROVIDER:-custom}"
message=""
model="${SMOKE_MODEL_NAME:-}"
base_url="${SMOKE_MODEL_BASE_URL:-}"
api_key="${SMOKE_MODEL_API_KEY:-}"
reference_models="${SMOKE_REFERENCE_MODELS:-}"
conversation_id="${SMOKE_CONVERSATION_ID:-}"
user_id="${SMOKE_USER_ID:-00000000-0000-4000-8000-000000000001}"
user_email="${SMOKE_USER_EMAIL:-smoke@motis.dev}"
agent_url="${AGENT_URL:-http://localhost:8001/chat}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --message)
      message="${2:-}"
      shift 2
      ;;
    --provider)
      provider="${2:-}"
      shift 2
      ;;
    --model)
      model="${2:-}"
      shift 2
      ;;
    --base-url)
      base_url="${2:-}"
      shift 2
      ;;
    --api-key)
      api_key="${2:-}"
      shift 2
      ;;
    --reference-models)
      reference_models="${2:-}"
      shift 2
      ;;
    --conversation-id)
      conversation_id="${2:-}"
      shift 2
      ;;
    --user-id)
      user_id="${2:-}"
      shift 2
      ;;
    --user-email)
      user_email="${2:-}"
      shift 2
      ;;
    --agent-url)
      agent_url="${2:-}"
      shift 2
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

case "$provider" in
  anthropic)
    : "${base_url:=https://api.anthropic.com}"
    : "${api_key:=${ANTHROPIC_API_KEY:-}}"
    ;;
  openai)
    : "${base_url:=https://api.openai.com/v1}"
    : "${api_key:=${OPENAI_API_KEY:-}}"
    ;;
  openrouter)
    : "${base_url:=https://openrouter.ai/api/v1}"
    : "${api_key:=${OPENROUTER_API_KEY:-${OPENAI_API_KEY:-}}}"
    ;;
  custom|"")
    ;;
  *)
    echo "Unknown provider preset: $provider" >&2
    exit 1
    ;;
esac

if [[ -z "$message" ]]; then
  echo "--message is required" >&2
  exit 1
fi

if [[ -z "$model" ]]; then
  echo "Model is required. Set --model or SMOKE_MODEL_NAME." >&2
  exit 1
fi

if [[ -z "$base_url" ]]; then
  echo "Base URL is required. Set --base-url or SMOKE_MODEL_BASE_URL." >&2
  exit 1
fi

if [[ -z "$api_key" ]]; then
  echo "API key is required. Set --api-key or SMOKE_MODEL_API_KEY." >&2
  exit 1
fi

if [[ -z "$conversation_id" ]]; then
  conversation_id="$(python3 -c 'import uuid; print(uuid.uuid4())')"
fi

json_body="$(python3 -c 'import json,sys; print(json.dumps({"message": sys.argv[1]}))' "$message")"

echo "Agent URL: $agent_url" >&2
echo "Provider preset: $provider" >&2
echo "Model: $model" >&2
echo "Conversation ID: $conversation_id" >&2
echo >&2

curl -N -sS \
  -X POST \
  -H "Content-Type: application/json" \
  -H "X-User-Id: $user_id" \
  -H "X-User-Email: $user_email" \
  -H "X-Model-Base-Url: $base_url" \
  -H "X-Model-Api-Key: $api_key" \
  -H "X-Model-Name: $model" \
  -H "X-Model-Reference-Models: $reference_models" \
  -H "X-Conversation-Id: $conversation_id" \
  -H "X-Conversation-Source: chat" \
  "$agent_url" \
  --data "$json_body"
