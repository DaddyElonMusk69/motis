#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$SCRIPT_DIR"

PYTHON_VERSION="${MOTIS_PYTHON_VERSION:-3.11}"
VENV_DIR="${MOTIS_MCP_VENV_DIR:-$SCRIPT_DIR/venv}"

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

if [ ! -f "$REPO_ROOT/pyproject.toml" ]; then
  printf 'Expected Motis workspace root at %s\n' "$REPO_ROOT" >&2
  exit 1
fi

USER_BIN="$(python3 -c 'import site; print(site.USER_BASE)' 2>/dev/null || true)/bin"
if [ -n "${USER_BIN:-}" ] && [ -x "$USER_BIN/uv" ]; then
  export PATH="$USER_BIN:$PATH"
fi

export UV_CACHE_DIR="${MOTIS_MCP_UV_CACHE_DIR:-$SCRIPT_DIR/.uv-cache}"
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

log_info "Installing Motis MCP dependencies into the local virtualenv..."
sync_log="$(mktemp)"
sync_args=(
  --project "$REPO_ROOT"
  --package motis-mcp
)

if ! UV_PROJECT_ENVIRONMENT="$VENV_DIR" uv sync "${sync_args[@]}" --locked 2>&1 | tee "$sync_log"; then
  if grep -q "The lockfile at .* needs to be updated, but \`--locked\` was provided" "$sync_log"; then
    log_warn "uv.lock is out of date; retrying without --locked"
    UV_PROJECT_ENVIRONMENT="$VENV_DIR" uv sync "${sync_args[@]}"
  else
    rm -f "$sync_log"
    exit 1
  fi
fi
rm -f "$sync_log"

log_success "Standalone Motis MCP environment is ready."
printf '\nNext steps:\n'
printf '  1. Run ./motis-mcp data-http\n'
printf '  2. Or use make data-http / make execution-http / make operator-http\n'
