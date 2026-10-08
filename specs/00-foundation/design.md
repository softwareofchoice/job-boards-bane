# 00 — Foundation: Design

## Architecture

```
┌──────────────────────────┐      HTTP/JSON       ┌───────────────────────────────┐
│  Frontend (React + Vite)  │ ───────────────────▶ │  Backend (FastAPI)            │
│  /tracker                 │                      │  /api/tracker/...             │
│  /scraper                 │                      │  /api/scraper/...             │
│  /resume-rounder          │                      │  /api/rounder/...             │
└──────────────────────────┘                      │  /api/health                  │
                                                  │                               │
                                                  │  core/  db · files · llm · jobs│
                                                  └──┬──────────┬──────────┬──────┘
                                                     │          │          │
                                              ┌──────▼───┐ ┌────▼─────┐ ┌──▼──────────┐
                                              │ Postgres │ │ data dir │ │ Ollama      │
                                              │ (Docker) │ │ (files)  │ │ (local LLM) │
                                              └──────────┘ └──────────┘ └─────────────┘
```

The backend is a **modular monolith**: one FastAPI process with one Python
package per sub-app. Sub-apps share only `core/` and never import from each
other. This keeps the boundaries clear without the overhead of separate
services.

## Repository layout

```
backend/
  pyproject.toml
  alembic/                     # migrations (FND-2.2)
  app/
    main.py                    # FastAPI app, router registration, error handlers
    config.py                  # Settings (pydantic-settings) (FND-4.2)
    core/
      db.py                    # engine, session dependency
      files.py                 # FileStore: save/open/delete under DATA_DIR (FND-2.3)
      llm.py                   # LLMClient (FND-3)
      jobs.py                  # background job runner + job status table
      errors.py                # error types and handlers (FND-5)
    tracker/                   # spec 01
    scraper/                   # spec 02
    rounder/                   # spec 03
  tests/
frontend/
  src/
    app/                       # shell, routes, nav (FND-1)
    features/tracker/
    features/scraper/
    features/rounder/
    lib/api.ts                 # fetch wrapper, error mapping (FND-5.1)
docker-compose.yml             # postgres (+ optional ollama)
Makefile
.env.example
```

Each feature package has the same shape: `models.py` (SQLAlchemy), `schemas.py`
(Pydantic), `service.py` (business logic, no HTTP), `router.py` (HTTP only).

## Configuration (FND-4.2)

| Variable            | Default                                                 |
| ------------------- | ------------------------------------------------------- |
| `DATABASE_URL`      | `postgresql+psycopg://bane:bane@localhost:5432/bane`    |
| `DATA_DIR`          | `./data`                                                |
| `LLM_BASE_URL`      | `http://localhost:11434`                                |
| `LLM_MODEL`         | `llama3.1:8b`                                           |
| `LLM_TIMEOUT_S`     | `120`                                                   |
| `LLM_MAX_RETRIES`   | `2`                                                     |
| `MAX_UPLOAD_MB`     | `10`                                                    |

## Shared components

### FileStore (FND-2.3)

- `save(category: str, filename: str, data: bytes) -> StoredFile` writes to
  `DATA_DIR/<category>/<uuid>/<sanitized filename>` and returns
  `{path, original_name, content_type, size_bytes, sha256}`.
- Paths in the database are **relative** to `DATA_DIR` so the data directory
  can be moved.
- Content type is checked from file contents (magic bytes), not just the
  extension.
- Files are served through `GET /api/files/{file_id}`, never by exposing the
  directory directly.

A shared `stored_files` table holds file metadata; feature tables reference it
by foreign key.

```
stored_files
  id              uuid pk
  category        text        -- 'screenshot' | 'resume' | 'export' | ...
  relative_path   text unique
  original_name   text
  content_type    text
  size_bytes      bigint
  sha256          text
  created_at      timestamptz default now()
```

### LLMClient (FND-3)

```python
class LLMClient:
    async def complete(self, prompt: str, *, system: str | None = None) -> str: ...
    async def complete_json(self, prompt: str, schema: type[BaseModel],
                            *, system: str | None = None) -> BaseModel: ...
```

- Talks to Ollama's `/api/chat`. `complete_json` passes the Pydantic model's
  JSON schema in Ollama's `format` field, validates the reply, and on a
  validation error re-prompts with the error message, up to `LLM_MAX_RETRIES`.
- `temperature` defaults to `0` for scoring and extraction so results can be
  repeated.
- Connection errors → `LLMUnavailableError` ("Start Ollama with `ollama serve`");
  404 model → `LLMModelMissingError` ("Run `ollama pull <model>`") (FND-3.4).
- Tests use a `FakeLLMClient` that returns canned responses. No test needs a
  real model.

### Background jobs

Scraping a batch of jobs and generating a resume can each take minutes, so
they run outside the request cycle.

- v1 uses FastAPI `BackgroundTasks` plus a `jobs` table holding status, so
  there's no extra infrastructure. The UI polls `GET /api/jobs/{id}`.
- If a job is still `running` when the server restarts, it is marked `failed`
  with the reason "interrupted" at startup.

```
jobs
  id          uuid pk
  kind        text            -- 'scrape' | 'resume_generation'
  status      text            -- 'queued' | 'running' | 'succeeded' | 'failed'
  progress    jsonb           -- e.g. {"step": "scoring", "done": 12, "total": 40}
  error       text null
  created_at  timestamptz
  finished_at timestamptz null
```

### Errors (FND-5)

- Validation errors: FastAPI's default 422 body, mapped in `lib/api.ts` to a
  `{field: message}` object for forms.
- Domain errors (`NotFound`, `LLMUnavailableError`, `UploadTooLarge`, …) inherit
  from `AppError(status_code, code, message)` and are returned as
  `{"error": {"code", "message", "request_id"}}`.
- Middleware gives every request an `X-Request-ID` and adds it to every log line.

### Health (FND-3.5)

`GET /api/health` → `{"db": "ok"|"error", "llm": "ok"|"error", "model": "<name>"}`.
The frontend shows a small status badge in the header and a warning banner on
LLM-dependent pages when `llm` isn't `ok`.

## Frontend shell (FND-1)

- Top navigation: Home · Tracker · Job Scraper · Resume Rounder, plus the
  health badge.
- Routes are lazy-loaded per feature.
- Shared form components (`TextField`, `UrlField`, `FileField`, `NumberField`,
  `TagInput`) show server-side errors under each field.

## Decisions

| #   | Decision                                     | Why                                                                                                       | Alternatives considered                     |
| --- | -------------------------------------------- | --------------------------------------------------------------------------------------------------------- | ------------------------------------------- |
| D-1 | Python/FastAPI backend                       | Best libraries for scraping (Playwright), LLM work and `.docx` editing.                                   | Node/Next.js full-stack: weaker `.docx` editing. |
| D-2 | Separate React SPA                           | Clear split from the API; the scraper and resume screens need interactive progress and result views.      | Server-rendered templates (HTMX): fine too, simpler, less interactive. |
| D-3 | Ollama for the local LLM                     | Simplest way to run local models, with structured (JSON) output support.                                   | llama.cpp server, LM Studio, vLLM: all can sit behind `LLMClient`. |
| D-4 | Files on disk, metadata in Postgres          | Keeps the database small and files easy to inspect.                                                       | `bytea` columns: simpler backups, but a bloated database. |
| D-5 | In-process background jobs                   | Single user, low volume; no Redis or worker process needed.                                                 | Celery/RQ/Arq: add if jobs need to run in parallel or survive restarts. |
| D-6 | Modular monolith                             | One process to run; sub-apps stay separate packages.                                                        | One service per sub-app: unnecessary for a local single-user tool. |

## Implementation notes

Where the code differs from the plan above, and why:

- **Test database:** tests use a real Postgres given by `TEST_DATABASE_URL` (default
  `bane_test` on localhost; Docker Compose creates it) instead of testcontainers, so the tests
  also run where Docker isn't available. The tests drop and recreate that database's schema.
- **Health response** also has `llm_message`: the reason the LLM can't be used, shown in the
  badge tooltip and the warning banner.
- **Unexpected errors** are caught in the request-ID middleware rather than an exception
  handler, so the log line and the response both carry the request ID.
- **`FakeLLMClient`** lives in `app/core/llm_fake.py` (not under `tests/`) so later E2E runs can
  start the backend with it.
- **Context window.** Every request sends `num_ctx` (`LLM_NUM_CTX`, default 8192), because
  Ollama's default depends on its version and can be small enough to cut long prompts short.
  `make llm-check` (`app/llm_check.py`) runs the real scoring prompt against the configured model
  and reports validity, timing, prompt size against the window, repeatability and GPU share.
- **A model/migration drift test** (`test_models_match_migrations`) fails if a model changes
  without a migration.
- **File downloads** are inline only for images (other types download) and send
  `X-Content-Type-Options: nosniff`.

## Test strategy

- **Unit:** `FileStore` (path sanitising, type sniffing), `LLMClient` (retry on
  invalid JSON, error mapping) using a mocked HTTP transport.
- **Integration:** migrations apply cleanly to an empty Postgres
  (testcontainers); `/api/health` with the DB up/down and the LLM up/down.
- **E2E smoke:** the home page loads and every nav link renders its page.
