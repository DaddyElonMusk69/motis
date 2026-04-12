#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
export UV_CACHE_DIR="${UV_CACHE_DIR:-$ROOT/.uv-cache}"

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required to bootstrap the Motis workspace." >&2
  exit 1
fi

USER_BIN="$(python3 -c 'import site; print(site.USER_BASE)')/bin"
if [ -x "$USER_BIN/uv" ]; then
  export PATH="$USER_BIN:$PATH"
fi

if ! command -v uv >/dev/null 2>&1; then
  echo "uv not found; installing it with pip --user..."
  python3 -m pip install --user uv
  export PATH="$USER_BIN:$PATH"
fi

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is still unavailable after installation. Add your Python user bin directory to PATH and rerun." >&2
  exit 1
fi

sync_log="$(mktemp)"
if ! uv sync --locked "$@" 2>&1 | tee "$sync_log"; then
  if grep -q 'The lockfile at .* needs to be updated, but `--locked` was provided' "$sync_log"; then
    echo "uv.lock is out of date for the current workspace; retrying with an unlocked sync..."
    uv sync "$@"
  else
    rm -f "$sync_log"
    exit 1
  fi
fi
rm -f "$sync_log"

# Some macOS setups mark editable .pth files as hidden, which prevents Python
# from loading workspace packages from the synced virtualenv.
if command -v chflags >/dev/null 2>&1 && [ -d "$ROOT/.venv/lib" ]; then
  shopt -s nullglob
  for pth_file in "$ROOT"/.venv/lib/python*/site-packages/_motis*.pth; do
    chflags nohidden "$pth_file" 2>/dev/null || true
  done
fi
