# job-boards-bane

A web app of tools for the job search: a Job Application Tracker, a Web Job
Scraper and a Resume Rounder. See [`REQUIREMENTS.md`](REQUIREMENTS.md) for the
original requirements and [`specs/`](specs/README.md) for the specs to build from.

Everything runs on your machine: data is kept in a local Postgres database and
files under `data/`, and the LLM features use a local model through
[Ollama](https://ollama.com).

## Requirements

- [Docker](https://docs.docker.com/get-docker/) (for Postgres, and optionally Ollama)
- [uv](https://docs.astral.sh/uv/) 0.12 or newer (`uv self update`). Python 3.12 is installed by
  uv if needed.
- Node.js 22 with npm 10 (the npm that comes with Node 22). With nvm or fnm, run `nvm use` /
  `fnm use` in `frontend/` to pick it up from `.nvmrc`.
- [Ollama](https://ollama.com) for the scraper and Resume Rounder, either installed on your
  machine or with `make llm-up`

These versions are pinned in the repo (`backend/.python-version`, `required-version` in
`backend/pyproject.toml`, `frontend/.nvmrc`, `engines` in `frontend/package.json`), and CI reads
the same files. With the wrong version, uv and `npm ci` stop with a message saying what's needed.

## Getting started

```bash
cp .env.example .env    # optional: every setting has a default
make dev                # installs dependencies, then starts Postgres, runs migrations,
                        # and serves the backend (:8000) and frontend (:5173)
```

Open <http://localhost:5173>. The badge in the top right shows whether the database and the
local LLM are reachable. To use the LLM features, run `ollama serve` and
`ollama pull llama3.1:8b` (or `make llm-up` to run Ollama in Docker instead).

## Common commands

Run `make help` for the full list.

| Command         | What it does                                                  |
| --------------- | ------------------------------------------------------------- |
| `make dev`      | Start everything for development, with auto-reload            |
| `make install`  | Reinstall dependencies (other commands install them as needed) |
| `make migrate`  | Apply database migrations                                     |
| `make check`    | Lint, type check and run the tests (what CI runs, except E2E) |
| `make e2e`      | Run the browser tests against the real backend and frontend   |
| `make format`   | Format all code                                               |

### Web Job Scraper

By default the scraper drives Google's jobs search in a browser. Run `make scraper-browser`
once to download it, and `make scraper-canary` to check it can still read Google's page.
Automated Google searches are against Google's terms of service and may be blocked; set
`JOB_SOURCE=serpapi` and `SERPAPI_KEY` to use SerpAPI instead. To try the app without either,
set `JOB_SOURCE=fake` (canned postings) and `LLM_FAKE=true` (canned LLM replies).

### Dependencies

Install exactly what the lockfiles say: the `make` commands run `uv sync --locked` and `npm ci`
for you. To change dependencies, use `uv add` / `uv remove` in `backend/` and `npm install <pkg>`
/ `npm uninstall <pkg>` in `frontend/`, and commit the lockfile with the manifest. Dependabot
opens weekly PRs for Python, npm and GitHub Actions updates.

The backend tests need the `bane_test` database, which Docker Compose creates. To use another
database, set `TEST_DATABASE_URL`; the tests drop and recreate its schema.

## Layout

```
backend/    FastAPI app (app/core = shared platform; one package per sub-app), Alembic migrations
frontend/   React + Vite app (src/features = one folder per sub-app)
specs/      Requirements, design and tasks for each part
```
