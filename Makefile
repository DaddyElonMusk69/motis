# Motis — Dev Makefile
# Usage: make <target>
# Requires: docker compose, python 3.11+, uv

.PHONY: up down db-migrate db-reset db-shell db-logs \
        agent platform test lint type-check help

# ── Infrastructure ────────────────────────────────────────────────────────────

up:
	@echo "Starting Motis dev infrastructure (Postgres + Redis)..."
	docker compose up -d
	@echo "✓ Postgres on localhost:5432  (user: motis / pass: motis)"
	@echo "✓ Redis    on localhost:6379"
	@echo ""
	@echo "Next: make db-migrate   (run migrations)"

up-storage:
	@echo "Starting full stack including MinIO..."
	docker compose --profile storage up -d

down:
	docker compose down

down-clean:
	@echo "⚠️  This will delete all DB data and Redis cache."
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
	@echo "⚠️  Dropping and recreating Motis DB..."
	docker exec -it motis_postgres psql -U motis -c "DROP DATABASE IF EXISTS motis;"
	docker exec -it motis_postgres psql -U motis -c "CREATE DATABASE motis OWNER motis;"
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
	@echo "Starting agent service with hot-reload..."
	cd services/agent && uv run uvicorn motis_agent.server:app \
		--host 0.0.0.0 --port 8001 --reload --log-level info

chat:
	@echo "Starting Motis CLI (no platform required)..."
	@[ "$$MOTIS_API_KEY" ] || [ "$$OPENAI_API_KEY" ] || \
		(echo "Error: set MOTIS_API_KEY or OPENAI_API_KEY first" && exit 1)
	cd services/agent && uv run python -m motis_agent.cli

ask:
	@[ "$(Q)" ] || (echo "Usage: make ask Q='your question here'" && exit 1)
	@[ "$$MOTIS_API_KEY" ] || [ "$$OPENAI_API_KEY" ] || \
		(echo "Error: set MOTIS_API_KEY or OPENAI_API_KEY first" && exit 1)
	cd services/agent && uv run python -m motis_agent.cli --one-shot "$(Q)"

platform:
	@echo "Starting platform service with hot-reload..."
	cd services/platform && uv run uvicorn motis_platform.api.app:app \
		--host 0.0.0.0 --port 8000 --reload --log-level info

worker:
	@echo "Starting Celery operator runtime worker..."
	cd services/platform && uv run celery -A motis_platform.operator_runtime.worker worker \
		--loglevel=info --concurrency=4 -Q operators

# ── Testing ───────────────────────────────────────────────────────────────────

test:
	@echo "Running test suite..."
	DATABASE_URL=postgresql+asyncpg://motis:motis@localhost:5432/motis_test \
	uv run pytest tests/ -v --tb=short

test-agent:
	DATABASE_URL=postgresql+asyncpg://motis:motis@localhost:5432/motis_test \
	uv run pytest tests/agent/ -v --tb=short

test-platform:
	DATABASE_URL=postgresql+asyncpg://motis:motis@localhost:5432/motis_test \
	uv run pytest tests/platform/ -v --tb=short

test-fast:
	uv run pytest tests/ -v --tb=short -m "not integration"

# ── Code Quality ──────────────────────────────────────────────────────────────

lint:
	uv run ruff check . --fix
	uv run ruff format .

type-check:
	uv run mypy services/ packages/ --ignore-missing-imports

ci-check:
	$(MAKE) lint
	$(MAKE) type-check
	$(MAKE) test

# ── Help ──────────────────────────────────────────────────────────────────────

help:
	@echo ""
	@echo "Motis Dev Commands"
	@echo "=================="
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
	@echo "  make agent           Run agent service (hot-reload)"
	@echo "  make chat            Run Motis CLI REPL (no platform needed)"
	@echo "  make ask Q='...'     One-shot agent query (no platform needed)"
	@echo "  make platform        Run platform service (hot-reload)"
	@echo "  make worker          Run Celery operator worker"
	@echo ""
	@echo "Testing:"
	@echo "  make test            Run all tests"
	@echo "  make test-fast       Run unit tests only (no integration)"
	@echo ""
	@echo "Code Quality:"
	@echo "  make lint            Run ruff lint + format"
	@echo "  make type-check      Run mypy"
	@echo "  make ci-check        lint + type-check + test (mirrors CI)"
	@echo ""
