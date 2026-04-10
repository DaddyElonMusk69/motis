# Contributing

## Branching

Motis uses a trunk-based workflow by default:

- Create a short-lived feature branch from `main`
- Open a pull request back into `main`
- Merge only after CI passes and the required review lands

We are not using a long-lived `dev` branch for everyday development right now. If we later need a stabilization or release branch, we can add one deliberately.

Suggested branch names:

- `feature/<topic>`
- `fix/<topic>`
- `chore/<topic>`

## Pull Requests

Before opening a PR, run the checks that apply to your change:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy packages/shared/motis_shared
uv run mypy services/agent/motis_agent/operators
uv run pytest --tb=short -q
cd web && npm ci && npm run type-check && npm run lint
```

Also update docs when behavior, architecture, or operator safety assumptions change.

## GitHub Settings

The expected `main` branch protection policy is:

- Require a pull request before merging
- Require status checks to pass before merging
- Require CODEOWNERS review

The repository already includes CI, CODEOWNERS, and a PR template under `.github/`.

If you have a GitHub token with repository administration access, you can apply the expected protection rule with:

```bash
GITHUB_TOKEN=... ./scripts/set_github_branch_protection.sh main
```
