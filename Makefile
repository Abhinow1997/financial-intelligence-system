# Financial Intelligence System - common tasks.
# On Windows, run these under Git Bash, or use scripts/dev_up.ps1 for the stack.

.DEFAULT_GOAL := help
.PHONY: help setup lint format test gate up up-app up-core up-data down clean tree \
        airflow-up airflow-ps airflow-logs airflow-cli airflow-dag airflow-down airflow-reset

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
	 awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

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

up-app: ## Start just backend :8000 + frontend :8501 (Lab 01)
	docker compose up --build

up-core: ## Start the core serving path only
	docker compose --profile core up --build

up-data: ## Start datastores only (postgres/redis/qdrant/minio/redpanda)
	docker compose up postgres redis qdrant minio redpanda

# Airflow ships its own compose file. The -p flag is REQUIRED: without it Docker
# derives the project name from this directory, which is the same name the main
# stack uses, and the two files' `postgres`/`redis` services would clobber each
# other's containers. `fis-airflow` (not plain `airflow`) also keeps this stack
# clear of any unrelated Airflow you may already run on this machine.
AIRFLOW := docker compose -p fis-airflow -f docker-compose-airflow.yaml

airflow-up: ## Start Airflow (UI on :8088, login airflow/airflow)
	$(AIRFLOW) up -d

airflow-ps: ## Show Airflow container health
	$(AIRFLOW) ps

airflow-logs: ## Tail the Airflow scheduler + apiserver logs
	$(AIRFLOW) logs -f airflow-scheduler airflow-apiserver

airflow-cli: ## Run an Airflow CLI command, e.g. make airflow-cli CMD="dags list"
	$(AIRFLOW) run --rm airflow-cli airflow $(CMD)

airflow-dag: ## Trigger the market snapshot DAG once
	$(AIRFLOW) run --rm airflow-cli airflow dags trigger market_daily_snapshot

airflow-down: ## Stop Airflow (keeps its database volume)
	$(AIRFLOW) down

airflow-reset: ## Stop Airflow and DELETE its database volume
	$(AIRFLOW) down --volumes --remove-orphans

down: ## Stop the stack
	docker compose down

clean: ## Remove caches and build artifacts
	find . -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache .ruff_cache

tree: ## Show the service tree
	@find services -maxdepth 2 -type d | sort
