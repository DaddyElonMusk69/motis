#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PYTHON_VERSION="${MOTIS_PYTHON_VERSION:-3.11}"
VENV_DIR="${MOTIS_VENV_DIR:-$SCRIPT_DIR/venv}"
MOTIS_EXTRAS="${MOTIS_EXTRAS:-cli,dev,messaging,cron,pty,honcho,mcp,homeassistant,sms,dingtalk,feishu,mistral}"

log_info() {
  printf -- '-> %s\n' "$1"
}

log_success() {
  printf -- 'OK %s\n' "$1"
}

log_warn() {
  printf -- 'WARN %s\n' "$1"
}

resolve_python_bin() {
  local candidates=(
    "python${PYTHON_VERSION}"
    "python${PYTHON_VERSION%.*}"
    "python3"
    "python"
  )

  local candidate=""
  for candidate in "${candidates[@]}"; do
    if command -v "$candidate" >/dev/null 2>&1; then
      command -v "$candidate"
      return 0
    fi
  done

  return 1
}

build_uv_sync_args() {
  if [ -z "${MOTIS_EXTRAS:-}" ]; then
    return 0
  fi

  local old_ifs="$IFS"
  IFS=','
  # shellcheck disable=SC2206
  local extras=( $MOTIS_EXTRAS )
  IFS="$old_ifs"

  local extra=""
  for extra in "${extras[@]}"; do
    extra="${extra#"${extra%%[![:space:]]*}"}"
    extra="${extra%"${extra##*[![:space:]]}"}"
    if [ -n "$extra" ]; then
      UV_SYNC_ARGS+=(--extra "$extra")
    fi
  done
}

USER_BIN="$(python3 -c 'import site; print(site.USER_BASE)' 2>/dev/null || true)/bin"
if [ -n "${USER_BIN:-}" ] && [ -x "$USER_BIN/uv" ]; then
  export PATH="$USER_BIN:$PATH"
fi

export UV_CACHE_DIR="${MOTIS_UV_CACHE_DIR:-$SCRIPT_DIR/.uv-cache}"
mkdir -p "$UV_CACHE_DIR"

PYTHON_BIN="$(resolve_python_bin || true)"
if [ -z "${PYTHON_BIN:-}" ]; then
  printf 'A local Python 3 interpreter is required. Install Python 3.11+ and rerun this script.\n' >&2
  exit 1
fi

if [ "$(basename "$PYTHON_BIN")" != "python${PYTHON_VERSION}" ]; then
  log_warn "Preferred Python ${PYTHON_VERSION} not found; using $(basename "$PYTHON_BIN")"
fi

if ! command -v uv >/dev/null 2>&1; then
  log_info "Installing uv..."
  python3 -m pip install --user uv
  export PATH="$USER_BIN:$PATH"
fi

if ! command -v uv >/dev/null 2>&1; then
  printf 'uv is required. Install it and rerun this script.\n' >&2
  exit 1
fi

if [ ! -d "$VENV_DIR" ]; then
  log_info "Creating local virtualenv at ${VENV_DIR#$SCRIPT_DIR/}"
  "$PYTHON_BIN" -m venv "$VENV_DIR"
else
  log_success "Using existing virtualenv at ${VENV_DIR#$SCRIPT_DIR/}"
fi

log_info "Installing Motis dependencies into the local virtualenv..."
declare -a UV_SYNC_ARGS=()
build_uv_sync_args
sync_log="$(mktemp)"
if ! UV_PROJECT_ENVIRONMENT="$VENV_DIR" uv sync "${UV_SYNC_ARGS[@]}" --locked 2>&1 | tee "$sync_log"; then
  if grep -q "The lockfile at .* needs to be updated, but \`--locked\` was provided" "$sync_log"; then
    log_warn "uv.lock is out of date; retrying without --locked"
    UV_PROJECT_ENVIRONMENT="$VENV_DIR" uv sync "${UV_SYNC_ARGS[@]}"
  else
    rm -f "$sync_log"
    exit 1
  fi
fi
rm -f "$sync_log"

if [ ! -f ".env" ] && [ -f ".env.example" ]; then
  cp .env.example .env
  log_success "Created local .env from .env.example"
fi

log_success "Standalone Motis environment is ready."
printf '\nNext steps:\n'
printf '  1. Run ./motis setup\n'
printf '  2. Start the agent with ./motis\n'
printf '  3. Or use make chat / make test from this directory\n'
