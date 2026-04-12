.PHONY: bootstrap setup chat doctor test build

VENV_BIN := venv/bin
PYTEST := $(VENV_BIN)/pytest

bootstrap:
	./setup-motis.sh

setup:
	./motis setup

chat:
	./motis

doctor:
	./motis doctor

test:
	@[ -x "$(PYTEST)" ] || (echo "Run ./setup-motis.sh first." && exit 1)
	$(PYTEST) -c pyproject.toml tests --tb=short -q

build:
	python3 -m pip wheel . --no-deps --no-build-isolation -w dist
