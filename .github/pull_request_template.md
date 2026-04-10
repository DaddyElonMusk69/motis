## What does this PR do?

<!-- Concise description of the change and why -->

## Type of change

- [ ] New feature
- [ ] Bug fix
- [ ] Refactor (no behavior change)
- [ ] Infrastructure / configuration
- [ ] Documentation

## Checklist

- [ ] Code is lint-clean (`uv run ruff check .`)
- [ ] Types pass (`uv run mypy` on affected packages)
- [ ] Tests added or updated for any new behavior
- [ ] PRD / architecture docs updated if a design decision changed
- [ ] `.env.example` updated if new env vars were added
- [ ] No API keys, secrets, or credentials in the diff

## For operator runtime changes

- [ ] `OperatorBase.tick()` interface is unchanged (backend-agnostic)
- [ ] Risk guard is not bypassed at any point
- [ ] Exchange keys are never logged or stored outside the Exchange Gateway

## For marketplace / arena changes

- [ ] Trade log entries are written by Exchange Gateway only (never by operator code)
- [ ] Performance stats are computed from `trade_log`, not self-reported
