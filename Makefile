# Motis — Repo-Root Dev Makefile
# Usage: make <target>
# Requires: docker compose, python 3.11+, uv

.PHONY: up down db-migrate db-reset db-shell db-logs \
        bootstrap up-storage down-clean db-migrate-test db-rollback \
        db-new-migration db-status agent chat ask smoke-agent build-motis \
        test lint format format-check type-check ci-check help

VENV_BIN := .venv/bin
VENV_PYTHON := $(VENV_BIN)/python
VENV_PYTEST := $(VENV_BIN)/pytest
VENV_RUFF := $(VENV_BIN)/ruff
VENV_MYPY := $(VENV_BIN)/mypy
MOTIS_SOURCE_DIR := services/motis_agent
MOTIS_BUILD_DIR := dist/motis-agent

bootstrap:
	./scripts/bootstrap-python.sh

# ── Infrastructure ────────────────────────────────────────────────────────────

up:
	@echo "Starting Motis development infrastructure (Postgres + Redis)..."
	docker compose up -d
	@echo "✓ Postgres on localhost:5432  (user: motis / pass: motis)"
	@echo "✓ Redis    on localhost:6379"
	@echo ""
	@echo "Next: make db-migrate"

up-storage:
	@echo "Starting development infrastructure plus MinIO..."
	docker compose --profile storage up -d

down:
	docker compose down

down-clean:
	@echo "This will delete all database and Redis state."
	docker compose down -v

# ── Database ──────────────────────────────────────────────────────────────────

db-migrate:
	@echo "Running Alembic migrations..."
	cd services/platform && DATABASE_URL=postgresql+asyncpg://motis:motis@localhost:5432/motis \
		uv run alembic -c ../../alembic.ini upgrade head
	@echo "✓ Migrations applied"

db-migrate-test:
	@echo "Running Alembic migrations on test DB..."
	cd services/platform && DATABASE_URL=postgresql+asyncpg://motis:motis@localhost:5432/motis_test \
		uv run alembic -c ../../alembic.ini upgrade head

db-rollback:
	@echo "Rolling back last migration..."
	cd services/platform && DATABASE_URL=postgresql+asyncpg://motis:motis@localhost:5432/motis \
		uv run alembic -c ../../alembic.ini downgrade -1

db-reset:
	@echo "Dropping and recreating the Motis development database..."
	docker exec motis_postgres psql -U motis -c "DROP DATABASE IF EXISTS motis;"
	docker exec motis_postgres psql -U motis -c "CREATE DATABASE motis OWNER motis;"
	$(MAKE) db-migrate
	@echo "✓ DB reset complete"

db-new-migration:
	@[ "$(NAME)" ] || (echo "Usage: make db-new-migration NAME=my_migration_name" && exit 1)
	cd services/platform && uv run alembic -c ../../alembic.ini revision \
		--autogenerate -m "$(NAME)"

db-shell:
	docker exec -it motis_postgres psql -U motis -d motis

db-logs:
	docker compose logs -f postgres

db-status:
	cd services/platform && DATABASE_URL=postgresql+asyncpg://motis:motis@localhost:5432/motis \
		uv run alembic -c ../../alembic.ini current

# ── Services ──────────────────────────────────────────────────────────────────

agent:
	@[ -x "$(VENV_PYTHON)" ] || (echo "Run 'make bootstrap' first." && exit 1)
	@echo "Starting the Motis agent service..."
	PYTHONPATH=services $(VENV_PYTHON) -m motis_agent.server --reload

chat:
	@[ -x "$(VENV_PYTHON)" ] || (echo "Run 'make bootstrap' first." && exit 1)
	@echo "Starting the Motis CLI..."
	PYTHONPATH=services $(VENV_PYTHON) -m motis_agent.cli

ask:
	@[ "$(Q)" ] || (echo "Usage: make ask Q='your question here'" && exit 1)
	@[ -x "$(VENV_PYTHON)" ] || (echo "Run 'make bootstrap' first." && exit 1)
	PYTHONPATH=services $(VENV_PYTHON) -m motis_agent.cli --one-shot "$(Q)"

smoke-agent:
	@[ "$(MESSAGE)" ] || (echo "Usage: make smoke-agent MESSAGE='hello'" && exit 1)
	./scripts/smoke-agent-chat.sh --message "$(MESSAGE)" $(SMOKE_ARGS)

build-motis:
	@command -v python3 >/dev/null 2>&1 || (echo "python3 is required to build Motis." && exit 1)
	@mkdir -p "$(MOTIS_BUILD_DIR)"
	python3 -m pip wheel "$(MOTIS_SOURCE_DIR)" --no-deps --no-build-isolation -w "$(MOTIS_BUILD_DIR)"

# ── Testing ───────────────────────────────────────────────────────────────────

test:
	@echo "Running checked-in Motis tests..."
	@[ -x "$(VENV_PYTEST)" ] || (echo "Run 'make bootstrap' first." && exit 1)
	$(VENV_PYTEST) -c pyproject.toml --tb=short -q

# ── Code Quality ──────────────────────────────────────────────────────────────

lint:
	@[ -x "$(VENV_RUFF)" ] || (echo "Run 'make bootstrap' first." && exit 1)
	$(VENV_RUFF) check .

format:
	@[ -x "$(VENV_RUFF)" ] || (echo "Run 'make bootstrap' first." && exit 1)
	$(VENV_RUFF) format .

format-check:
	@[ -x "$(VENV_RUFF)" ] || (echo "Run 'make bootstrap' first." && exit 1)
	$(VENV_RUFF) format --check .

type-check:
	@[ -x "$(VENV_MYPY)" ] || (echo "Run 'make bootstrap' first." && exit 1)
	$(VENV_MYPY) packages/shared/motis_shared
	$(VENV_MYPY) services/motis_agent/operators

ci-check:
	$(MAKE) lint
	$(MAKE) format-check
	$(MAKE) type-check
	$(MAKE) test

# ── Help ──────────────────────────────────────────────────────────────────────

help:
	@echo ""
	@echo "Motis Dev Commands"
	@echo "=================="
	@echo ""
	@echo "Workspace:"
	@echo "  make bootstrap       Install or refresh the Python workspace"
	@echo ""
	@echo "Infrastructure:"
	@echo "  make up              Start Postgres + Redis"
	@echo "  make up-storage      Start everything including MinIO"
	@echo "  make down            Stop services"
	@echo "  make down-clean      Stop services + delete volumes"
	@echo ""
	@echo "Database:"
	@echo "  make db-migrate      Apply pending migrations"
	@echo "  make db-rollback     Roll back last migration"
	@echo "  make db-reset        Drop + recreate + migrate (clean slate)"
	@echo "  make db-shell        Open psql shell"
	@echo "  make db-status       Show current migration version"
	@echo "  make db-new-migration NAME=my_name   Auto-generate a new migration"
	@echo ""
	@echo "Services:"
	@echo "  make agent           Run the Motis agent service"
	@echo "  make chat            Run the Motis CLI"
	@echo "  make ask Q='...'     One-shot Motis query"
	@echo "  make smoke-agent MESSAGE='...'   Send a smoke-test message over HTTP"
	@echo "  make build-motis     Build the Motis wheel into dist/motis-agent"
	@echo ""
	@echo "Testing:"
	@echo "  make test            Run the checked-in test suite"
	@echo ""
	@echo "Code Quality:"
	@echo "  make lint            Run ruff lint checks"
	@echo "  make format          Format Python files with ruff"
	@echo "  make format-check    Check formatting without modifying files"
	@echo "  make type-check      Run the repo-root mypy targets"
	@echo "  make ci-check        lint + format-check + type-check + test"
	@echo ""
