#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UPSTREAM_REPO="${HERMES_UPSTREAM_REPO:-https://github.com/NousResearch/hermes-agent.git}"
UPSTREAM_REF="${HERMES_UPSTREAM_REF:-b87d00288d68b7e63df86eb0f11134e8f1304ec9}"
DEST="${ROOT}/services/upstream/hermes_agent"

if [[ -e "${DEST}" ]]; then
  echo "Destination already exists: ${DEST}" >&2
  echo "Remove it manually before re-importing." >&2
  exit 1
fi

WORKDIR="$(mktemp -d)"
trap 'rm -rf "${WORKDIR}"' EXIT

git clone --depth 1 "${UPSTREAM_REPO}" "${WORKDIR}/src"
git -C "${WORKDIR}/src" fetch --depth 1 origin "${UPSTREAM_REF}"
git -C "${WORKDIR}/src" checkout "${UPSTREAM_REF}"

mkdir -p "${DEST}"

rsync -a \
  --exclude '.git' \
  --exclude '.github' \
  --exclude '.plans' \
  --exclude 'plans' \
  --exclude 'assets' \
  --exclude 'landingpage' \
  --exclude 'website' \
  --exclude 'tests' \
  --exclude 'docs' \
  --exclude 'docker' \
  --exclude 'nix' \
  --exclude 'packaging' \
  --exclude 'datagen-config-examples' \
  --exclude 'tinker-atropos' \
  --exclude 'RELEASE_*.md' \
  "${WORKDIR}/src/" "${DEST}/"

printf '%s\n' "${UPSTREAM_REF}" > "${ROOT}/services/upstream/HERMES_UPSTREAM_COMMIT"

echo "Imported Hermes upstream snapshot at ${UPSTREAM_REF}"
echo "Destination: ${DEST}"
