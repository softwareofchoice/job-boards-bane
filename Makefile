.DEFAULT_GOAL := help
SHELL := /bin/bash

LLM_MODEL ?= llama3.1:8b

.PHONY: help
help: ## List the available commands
	@grep -E '^[a-z0-9-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

.PHONY: install
install: ## Install backend and frontend dependencies
	cd backend && uv sync
	cd frontend && npm install

.PHONY: db-up
db-up: ## Start Postgres in Docker and wait until it's ready
	docker compose up -d --wait postgres

.PHONY: db-down
db-down: ## Stop Postgres (data is kept in a Docker volume)
	docker compose stop postgres

.PHONY: llm-up
llm-up: ## Start Ollama in Docker and pull the configured model
	docker compose --profile llm up -d --wait ollama
	docker compose exec ollama ollama pull $(LLM_MODEL)

.PHONY: migrate
migrate: ## Apply database migrations
	cd backend && uv run alembic upgrade head

.PHONY: dev
dev: db-up migrate ## Start Postgres, the backend (:8000) and the frontend (:5173)
	@trap 'kill 0' EXIT; \
	(cd backend && uv run uvicorn app.main:app --reload --port 8000) & \
	(cd frontend && npm run dev) & \
	wait

.PHONY: lint
lint: ## Lint and check formatting
	cd backend && uv run ruff check . && uv run ruff format --check .
	cd frontend && npm run lint

.PHONY: typecheck
typecheck: ## Run type checks
	cd backend && uv run mypy app
	cd frontend && npm run typecheck

.PHONY: test
test: ## Run backend and frontend unit/integration tests (needs Postgres)
	cd backend && uv run pytest
	cd frontend && npm test

.PHONY: e2e
e2e: migrate ## Run the end-to-end browser tests (starts its own servers)
	cd frontend && npx playwright test

.PHONY: format
format: ## Format all code
	cd backend && uv run ruff check --fix . && uv run ruff format .
	cd frontend && npm run format

.PHONY: check
check: lint typecheck test ## Everything CI runs except E2E
