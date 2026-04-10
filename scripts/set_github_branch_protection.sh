#!/usr/bin/env bash
set -euo pipefail

BRANCH="${1:-main}"

if [[ -z "${GITHUB_TOKEN:-}" ]]; then
  echo "GITHUB_TOKEN is required." >&2
  exit 1
fi

repo="${GITHUB_REPOSITORY:-}"

if [[ -z "$repo" ]]; then
  remote_url="$(git remote get-url origin 2>/dev/null || true)"
  case "$remote_url" in
    git@github.com:*.git)
      repo="${remote_url#git@github.com:}"
      repo="${repo%.git}"
      ;;
    https://github.com/*.git)
      repo="${remote_url#https://github.com/}"
      repo="${repo%.git}"
      ;;
    https://github.com/*)
      repo="${remote_url#https://github.com/}"
      ;;
  esac
fi

if [[ -z "$repo" ]]; then
  echo "Unable to determine owner/repo. Set GITHUB_REPOSITORY=owner/name." >&2
  exit 1
fi

payload="$(cat <<'JSON'
{
  "required_status_checks": {
    "strict": true,
    "contexts": [
      "Python lint (ruff + mypy)",
      "Python tests",
      "Web lint & type-check"
    ]
  },
  "enforce_admins": false,
  "required_pull_request_reviews": {
    "dismiss_stale_reviews": true,
    "require_code_owner_reviews": true,
    "required_approving_review_count": 1,
    "require_last_push_approval": false
  },
  "restrictions": null,
  "required_linear_history": true,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "block_creations": false,
  "required_conversation_resolution": true,
  "lock_branch": false,
  "allow_fork_syncing": true
}
JSON
)"

response_file="$(mktemp)"
status_code="$(
  curl -sS \
    -o "$response_file" \
    -w "%{http_code}" \
    -X PUT \
    -H "Accept: application/vnd.github+json" \
    -H "Authorization: Bearer ${GITHUB_TOKEN}" \
    -H "X-GitHub-Api-Version: 2022-11-28" \
    "https://api.github.com/repos/${repo}/branches/${BRANCH}/protection" \
    -d "$payload"
)"

if [[ "$status_code" != "200" ]]; then
  echo "GitHub API returned HTTP ${status_code}." >&2
  cat "$response_file" >&2
  rm -f "$response_file"
  exit 1
fi

echo "Applied branch protection to ${repo}:${BRANCH}."
rm -f "$response_file"
