# job-boards-bane

A web app of tools for the job search: a Job Application Tracker, a Web Job
Scraper and a Resume Rounder. See [`REQUIREMENTS.md`](REQUIREMENTS.md) for the
original requirements and [`specs/`](specs/README.md) for the specs to build from.

Everything runs on your machine: data is kept in a local Postgres database and
files under `data/`, and the LLM features use a local model through
[Ollama](https://ollama.com).

## Requirements

- [Docker](https://docs.docker.com/get-docker/) (for Postgres, and optionally Ollama)
- [uv](https://docs.astral.sh/uv/) (Python 3.12 is installed by uv if needed)
- Node.js 22+
- [Ollama](https://ollama.com) for the scraper and Resume Rounder, either installed on your
  machine or with `make llm-up`

## Getting started

```bash
cp .env.example .env    # optional: every setting has a default
make install            # backend and frontend dependencies
make dev                # Postgres + migrations + backend (:8000) + frontend (:5173)
```

Open <http://localhost:5173>. The badge in the top right shows whether the database and the
local LLM are reachable. To use the LLM features, run `ollama serve` and
`ollama pull llama3.1:8b` (or `make llm-up` to run Ollama in Docker instead).

## Common commands

Run `make help` for the full list.

| Command         | What it does                                                  |
| --------------- | ------------------------------------------------------------- |
| `make dev`      | Start everything for development, with auto-reload            |
| `make migrate`  | Apply database migrations                                     |
| `make check`    | Lint, type check and run the tests (what CI runs, except E2E) |
| `make e2e`      | Run the browser tests against the real backend and frontend   |
| `make format`   | Format all code                                               |

The backend tests need the `bane_test` database, which Docker Compose creates. To use another
database, set `TEST_DATABASE_URL`; the tests drop and recreate its schema.

## Layout

```
backend/    FastAPI app (app/core = shared platform; one package per sub-app), Alembic migrations
frontend/   React + Vite app (src/features = one folder per sub-app)
specs/      Requirements, design and tasks for each part
```
