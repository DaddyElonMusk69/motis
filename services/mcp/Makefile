.PHONY: bootstrap data data-http execution execution-http operator operator-http test help

VENV_BIN := venv/bin
PYTEST := $(VENV_BIN)/pytest

bootstrap:
	./setup-mcp.sh

data:
	./motis-mcp data

data-http:
	./motis-mcp data-http

execution:
	./motis-mcp execution

execution-http:
	./motis-mcp execution-http

operator:
	./motis-mcp operator

operator-http:
	./motis-mcp operator-http

test:
	@[ -x "$(PYTEST)" ] || (echo "Run ./setup-mcp.sh first." && exit 1)
	$(PYTEST) tests --tb=short -q

help:
	@echo ""
	@echo "Motis MCP Commands"
	@echo "=================="
	@echo ""
	@echo "  make bootstrap        Install or refresh the local MCP environment"
	@echo "  make data             Run the Data MCP stdio server"
	@echo "  make data-http        Run the Data MCP HTTP server"
	@echo "  make execution        Run the Execution MCP stdio server"
	@echo "  make execution-http   Run the Execution MCP HTTP server"
	@echo "  make operator         Run the Operator MCP stdio server"
	@echo "  make operator-http    Run the Operator MCP HTTP server"
	@echo "  make test             Run the MCP test suite"
	@echo ""
