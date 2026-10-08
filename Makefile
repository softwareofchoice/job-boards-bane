.DEFAULT_GOAL := help
SHELL := /bin/bash

LLM_MODEL ?= llama3.1:8b

.PHONY: help
help: ## List the available commands
	@grep -E '^[a-z0-9-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

# Dependencies are installed on demand: every command below that needs them depends on these
# marker files, which are rebuilt whenever the lockfiles change.
BACKEND_DEPS := backend/.venv/.make-installed
FRONTEND_DEPS := frontend/node_modules/.make-installed

$(BACKEND_DEPS): backend/pyproject.toml backend/uv.lock
	cd backend && uv sync --locked
	@touch $@

$(FRONTEND_DEPS): frontend/package.json frontend/package-lock.json
	cd frontend && npm ci
	@touch $@

.PHONY: install
install: ## Install (or reinstall) backend and frontend dependencies
	@rm -f $(BACKEND_DEPS) $(FRONTEND_DEPS)
	@$(MAKE) --no-print-directory $(BACKEND_DEPS) $(FRONTEND_DEPS)

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

.PHONY: llm-check
llm-check: $(BACKEND_DEPS) ## Score a sample posting with the local LLM (MODEL=... to compare models)
	cd backend && uv run python -m app.llm_check $(if $(MODEL),--model $(MODEL),)

.PHONY: migrate
migrate: $(BACKEND_DEPS) ## Apply database migrations
	cd backend && uv run alembic upgrade head

.PHONY: dev
dev: $(FRONTEND_DEPS) db-up migrate ## Start Postgres, the backend (:8000) and the frontend (:5173)
	@trap 'kill 0' EXIT; \
	(cd backend && uv run uvicorn app.main:app --reload --port 8000) & \
	(cd frontend && npm run dev) & \
	wait

.PHONY: lint
lint: $(BACKEND_DEPS) $(FRONTEND_DEPS) ## Lint and check formatting
	cd backend && uv run ruff check . && uv run ruff format --check .
	cd frontend && npm run lint

.PHONY: typecheck
typecheck: $(BACKEND_DEPS) $(FRONTEND_DEPS) ## Run type checks
	cd backend && uv run mypy app
	cd frontend && npm run typecheck

.PHONY: test
test: $(BACKEND_DEPS) $(FRONTEND_DEPS) ## Run backend and frontend unit/integration tests (needs Postgres)
	cd backend && uv run pytest
	cd frontend && npm test

.PHONY: e2e
e2e: $(FRONTEND_DEPS) migrate ## Run the end-to-end browser tests (starts its own servers)
	cd frontend && npx playwright test

.PHONY: scraper-browser
scraper-browser: $(BACKEND_DEPS) ## Download the Chromium the job scraper drives
	cd backend && uv run playwright install chromium

.PHONY: scraper-canary
scraper-canary: $(BACKEND_DEPS) ## Live check that the scraper still reads Google (SAVE=1 saves the page)
	cd backend && uv run python -m app.scraper.canary $(if $(SAVE),--save,)

.PHONY: format
format: $(BACKEND_DEPS) $(FRONTEND_DEPS) ## Format all code
	cd backend && uv run ruff check --fix . && uv run ruff format .
	cd frontend && npm run format

.PHONY: check
check: lint typecheck test ## Everything CI runs except E2E
