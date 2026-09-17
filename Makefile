# Financial Intelligence System - common tasks.
# On Windows, run these under Git Bash, or use scripts/dev_up.ps1 for the stack.

.DEFAULT_GOAL := help
.PHONY: help setup lint format test gate up up-core up-data down clean tree

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
	 awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

setup: ## Install dev tooling + shared libs (editable)
	python -m pip install -r requirements-dev.txt
	python -m pip install -e libs/fin_common -e libs/fin_schemas -e libs/fin_telemetry

lint: ## Lint everything with ruff
	ruff check .

format: ## Auto-format with black + ruff
	black .
	ruff check --fix .

test: ## Run the test suite
	pytest

gate: ## Run the blocking eval gate (R4/R6)
	python scripts/run_eval_gate.py

up: ## Start the FULL stack (all services + datastores)
	docker compose --profile full up --build

up-core: ## Start the core serving path only
	docker compose --profile core up --build

up-data: ## Start datastores only (postgres/redis/qdrant/minio/redpanda)
	docker compose --profile data up

down: ## Stop the stack
	docker compose down

clean: ## Remove caches and build artifacts
	find . -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache .ruff_cache

tree: ## Show the service tree
	@find services -maxdepth 2 -type d | sort
