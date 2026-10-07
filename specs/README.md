# Job Board's Bane — Specs

This directory turns [`REQUIREMENTS.md`](../REQUIREMENTS.md) into specs that can be
built from. Every sub-application gets three documents, written in this order:

| Document          | Answers                    | Contents                                                                 |
| ----------------- | -------------------------- | ------------------------------------------------------------------------ |
| `requirements.md` | *What* must it do?         | User stories, numbered acceptance criteria (EARS syntax), out of scope.  |
| `design.md`       | *How* will it do it?       | Components, data model, API, LLM prompts, error handling, test strategy. |
| `tasks.md`        | *In what order* do we build it? | Small tasks, each linked to the acceptance criteria it satisfies and a way to check it. |

## Specs

| #  | Spec                                                         | Source in `REQUIREMENTS.md`        | Depends on |
| -- | ------------------------------------------------------------ | ---------------------------------- | ---------- |
| 00 | [Foundation](00-foundation/requirements.md)                  | Overview ("web application that has sub applications") | — |
| 01 | [Job Application Tracker](01-job-application-tracker/requirements.md) | `### Job Application Tracker` | 00 |
| 02 | [Web Job Scraper](02-web-job-scraper/requirements.md)        | `### Web Job Scraper`              | 00 |
| 03 | [Resume Rounder](03-resume-rounder/requirements.md)          | `### Resume Rounder`               | 00 |

Build order: **00 → 01 → (02 and 03 in either order or in parallel)**. 01 is
built first because it is the simplest feature and sets up the patterns
(form → API → table → list view) that the other two reuse. 02 and 03 don't
depend on each other.

## Conventions

### Requirement IDs

Each spec has a prefix: `FND` (foundation), `TRK` (tracker), `SCR` (scraper),
`RND` (resume rounder). Acceptance criteria are numbered `<PREFIX>-<story>.<criterion>`,
e.g. `TRK-1.3`. Tasks, tests and commit messages refer to these IDs.

### EARS acceptance criteria

Acceptance criteria use the EARS patterns:

- **Ubiquitous:** `THE SYSTEM SHALL <response>`
- **Event-driven:** `WHEN <trigger> THE SYSTEM SHALL <response>`
- **State-driven:** `WHILE <state> THE SYSTEM SHALL <response>`
- **Unwanted behaviour:** `IF <condition> THEN THE SYSTEM SHALL <response>`
- **Optional feature:** `WHERE <feature is enabled> THE SYSTEM SHALL <response>`

Each criterion should be testable by one automated or manual test.

### Traceability

Every story in a `requirements.md` quotes the line(s) of `REQUIREMENTS.md` it
comes from. Anything a spec adds that isn't in `REQUIREMENTS.md` is marked
**[assumption]** and listed in [Open questions](#open-questions) until someone confirms it.

## Workflow

1. **Specify.** Write or update `requirements.md`. Resolve or explicitly accept
   every open question that affects the feature.
2. **Design.** Write `design.md` to cover every acceptance criterion. Record
   decisions and their trade-offs in its *Decisions* section.
3. **Plan.** Break the design into tasks in `tasks.md`. A task should be done in
   one sitting (one PR or less) and list the criteria it satisfies.
4. **Implement.** Work through the tasks in order. Each task is done when its
   *Verify* step passes. Tick it off in `tasks.md` in the same PR.
5. **Change.** If a requirement changes, update `requirements.md` first, then
   `design.md` and `tasks.md`, then the code. The spec is the source of truth.

## Default technology choices

`REQUIREMENTS.md` only fixes **Postgres** and a **local LLM**. Everything else
below is a default chosen to fit the work (scraping, LLM calls and document
manipulation are best supported in Python). See
[Foundation design](00-foundation/design.md#decisions) for the reasoning; change it
there before implementation starts if you want something else.

| Concern         | Default                                                              |
| --------------- | -------------------------------------------------------------------- |
| Backend         | Python 3.12, FastAPI, SQLAlchemy 2.x, Alembic, Pydantic v2           |
| Database        | PostgreSQL 16 (local, via Docker Compose)                            |
| Local LLM       | Ollama (default model `llama3.1:8b`, configurable)                   |
| Frontend        | React + TypeScript + Vite, React Router, TanStack Query              |
| Scraping        | Playwright (Chromium)                                                |
| Documents       | `python-docx` for `.docx`; LibreOffice headless to export to PDF and count pages |
| Tests           | pytest (against a local test database), Vitest, Playwright for E2E   |
| Tooling         | `uv`, Ruff, mypy, ESLint, Prettier, `make` targets                   |

## Open questions

These are gaps or ambiguities in `REQUIREMENTS.md`. Each spec states the
assumption it makes for now; confirm or correct them before building the
feature.

| ID   | Question                                                                                     | Assumption used                                                                                  | Affects |
| ---- | -------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------ | ------- |
| Q-1  | Is this a single-user app running locally, or does it need accounts and login?              | Single user, runs on localhost, no authentication.                                               | All     |
| Q-2  | In the tracker, is "resume used to apply" a file upload or a choice from saved resumes?     | A file upload (PDF or DOCX) stored with the application.                                         | TRK     |
| Q-3  | Should the tracker also support viewing, editing, deleting and a status (applied, interview, rejected…)? | View and delete are in scope; edit and status are out of scope for v1.                      | TRK     |
| Q-4  | How should Google be searched? Scraping Google results directly is fragile and against Google's terms of service. | Search goes through a swappable `JobSource` interface. The first implementation drives Google's jobs search with Playwright; a SerpAPI-backed source is a drop-in alternative. | SCR |
| Q-5  | What is the difference between "number of jobs pulled" and "number of jobs to be selected"? | Pull *N* postings, have the LLM score all of them, keep the top *X* (X ≤ N).                     | SCR     |
| Q-6  | Should scraper results be saved in the database, or only exported to CSV and shown?        | Each run and its results are saved in Postgres so past runs can be reopened; CSV is generated from the saved results. | SCR |
| Q-7  | In the `SKILLS` table, what does "role" mean?                                                | The job/position on the resume where the skill was used. This links each skill to an entry in the experience section. | RND |
| Q-8  | What resume file formats are supported?                                                      | `.docx` input and `.docx` output (plus a PDF export). PDF input isn't supported because PDFs can't be edited reliably. | RND |
| Q-9  | What unit is the "variable length" of the resume measured in?                                | A target page count (e.g. 1 or 2 pages), checked by rendering to PDF.                            | RND     |
| Q-10 | Should the sub-apps link up (e.g. a scraped job opens in Resume Rounder; a generated resume is logged in the tracker)? | Not in v1. A later follow-up is listed in each spec's *Out of scope*.                           | All     |
