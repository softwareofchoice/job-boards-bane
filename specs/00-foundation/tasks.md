# 00 — Foundation: Tasks

Each task lists the acceptance criteria it satisfies and how to check it's done.

> **Status:** all tasks implemented. One check is still open: F-2 (`make dev` from a fresh
> clone with Docker). CI (F-11) went green on the pull request that added it. Notes on where the code differs from the
> design are under *Implementation notes* in [`design.md`](design.md#implementation-notes).

- [x] **F-1 Repository scaffold**
  Create `backend/` (uv project, FastAPI, Ruff, mypy, pytest) and `frontend/`
  (Vite React-TS, ESLint, Prettier, Vitest), `Makefile`, `.env.example`, `.gitignore`
  (including `data/`).
  _Criteria:_ FND-4.2
  _Verify:_ `make lint` and `make test` pass on the empty project.

- [ ] **F-2 Docker Compose + `make dev`**
  Postgres 16 service with a named volume; optional `ollama` profile. `make dev`
  starts Postgres, the backend (uvicorn with reload) and the frontend (Vite)
  together.
  _Criteria:_ FND-4.1, FND-2.1
  _Verify:_ from a fresh clone, `make dev` serves the frontend on :5173 and the API on :8000.

- [x] **F-3 Settings and database session**
  `config.py` with pydantic-settings; `core/db.py` engine and session dependency;
  check the connection at startup.
  _Criteria:_ FND-2.4, FND-4.2
  _Verify:_ with Postgres stopped, the backend exits and prints the URL with the password hidden.

- [x] **F-4 Alembic + base migration**
  Set up Alembic; the first migration creates `stored_files` and `jobs`.
  `make migrate` applies migrations.
  _Criteria:_ FND-2.2
  _Verify:_ the integration test applies all migrations to an empty database, then downgrades them.

- [x] **F-5 Error handling and request IDs**
  `AppError` hierarchy, exception handlers, request-ID middleware, structured logging.
  _Criteria:_ FND-5.1, FND-5.2
  _Verify:_ tests check the error body shape for 422, 404 and 500.

- [x] **F-6 FileStore + file download endpoint**
  Save/open/delete, filename sanitising, type sniffing, size limit,
  `GET /api/files/{id}`.
  _Criteria:_ FND-2.3, FND-5.3
  _Verify:_ unit tests for path traversal (`../../etc/passwd`), oversized upload and wrong content type.

- [x] **F-7 LLMClient**
  `complete`, `complete_json` with schema validation and retries, error mapping,
  `FakeLLMClient` for tests.
  _Criteria:_ FND-3.1–FND-3.4
  _Verify:_ unit tests with a mocked transport: invalid JSON then valid JSON → success after one retry; connection refused → `LLMUnavailableError`.

- [x] **F-8 Background job runner**
  `jobs` service (create, update progress, finish, fail), `GET /api/jobs/{id}`,
  mark interrupted jobs as failed at startup.
  _Criteria:_ supports SCR-4 and RND-4
  _Verify:_ integration test runs a dummy job to `succeeded`, and one that raises to `failed` with an error.

- [x] **F-9 Health endpoint**
  `GET /api/health` checks the DB and LLM.
  _Criteria:_ FND-3.5
  _Verify:_ tests cover all four up/down combinations.

- [x] **F-10 Frontend shell**
  Router, nav, home page, placeholder pages for the 3 sub-apps, health badge,
  `lib/api.ts`, shared form components.
  _Criteria:_ FND-1.1–FND-1.4, FND-5.1
  _Verify:_ Playwright smoke test clicks every nav link.

- [x] **F-11 CI**
  GitHub Actions workflow: lint, type check, backend tests (with a Postgres
  service), frontend tests and build.
  _Criteria:_ FND-4.3
  _Verify:_ the workflow is green on the PR that adds it.
