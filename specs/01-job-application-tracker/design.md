# 01 — Job Application Tracker: Design

## Data model

`REQUIREMENTS.md` names the table "Applications"; it is created as
`applications` (lower-case, Postgres convention).

```
applications
  id                     uuid          pk default gen_random_uuid()
  job_title              varchar(200)  not null
  company_name           varchar(200)  not null
  posting_url            varchar(2048) not null
  posting_url_normalized varchar(2048) not null   -- for the duplicate warning (TRK-1.7)
  screenshot_file_id     uuid          null  fk -> stored_files(id)
  resume_file_id         uuid          not null fk -> stored_files(id)
  created_at             timestamptz   not null default now()   -- TRK-1.3

  index (created_at desc)
  index (posting_url_normalized)
  index using gin ((job_title || ' ' || company_name) gin_trgm_ops)   -- TRK-2.2
```

### Status (TRK-4)

```
applications
  ...
  status                 varchar(20)   not null default 'applied'
                         check (status in ('applied', 'interviewing', 'offer', 'rejected'))
  index (status)

application_status_changes                      -- TRK-4.4: one row per change
  id              uuid        pk
  application_id  uuid        not null fk -> applications(id) on delete cascade
  from_status     varchar(20) null              -- null for the initial "applied"
  to_status       varchar(20) not null
  changed_at      timestamptz not null default now()
  index (application_id, changed_at)
```

`applications.status` is the current status, kept in step with the last row of
its history in the same transaction, so the list can filter and show it without
a join. The migration gives every existing application an initial `applied`
row dated with its `created_at`.

Allowed changes (TRK-4.2) are one table in `app/tracker/status.py`, used by the
service and returned to the frontend so the buttons and the rule can't drift:

```python
TRANSITIONS = {
    "applied": ("interviewing", "rejected"),
    "interviewing": ("offer", "rejected"),
    "offer": (),
    "rejected": (),
}
```

Each change locks the application row (`SELECT … FOR UPDATE`) so two clicks
can't both apply. Undo (TRK-4.6) deletes the latest change row and sets the
status back to its `from_status`.

URL normalisation for the duplicate check: lower-case the scheme and host,
remove the fragment, remove `utm_*` parameters, remove a trailing `/`.

## API

All routes are under `/api/tracker`.

| Method | Path                       | Body / query                                                                                   | Response                              | Criteria          |
| ------ | -------------------------- | ---------------------------------------------------------------------------------------------- | ------------------------------------- | ----------------- |
| POST   | `/applications`            | `multipart/form-data`: `job_title`, `company_name`, `posting_url`, `resume` (file), `screenshot` (file, optional) | `201` `Application`                   | TRK-1.1–1.5       |
| GET    | `/applications/check-url`  | `?url=`                                                                                        | `{duplicate: bool, previous_created_at?}` | TRK-1.7       |
| GET    | `/applications`            | `?q=&page=1&page_size=25`                                                                      | `{items: Application[], total, page}` | TRK-2.1–2.3       |
| GET    | `/applications/{id}`       | —                                                                                              | `Application`                         | TRK-2.4           |
| DELETE | `/applications/{id}`       | —                                                                                              | `204`                                 | TRK-3.1           |
| POST   | `/applications/{id}/status` | `{"status": "interviewing"}`                                                                 | `200` `Application`; `409 invalid_status_change` with `allowed` | TRK-4.2–4.4 |
| DELETE | `/applications/{id}/status/latest` | —                                                                                     | `200` `Application`; `409` if only the initial status is left | TRK-4.6 |
| GET    | `/status-flow`             | —                                                                                              | `{total, paths: [{statuses: [s1, s2, s3], count}]}` | TRK-5.1 |

`GET /applications` also takes `?status=`. `Application` gains `status`,
`allowed_next` (from the transitions table) and `status_history`
(`[{from_status, to_status, changed_at}]`, oldest first).

`/status-flow` turns each application's history into a three-stage path,
carrying the last status forward when a path stops early (Applied → Rejected
becomes `applied, rejected, rejected`; a fresh application is `applied,
applied, applied`), and counts identical paths. Histories can't be longer than
three, so nothing is cut.

```jsonc
// Application
{
  "id": "uuid",
  "job_title": "Senior Backend Engineer",
  "company_name": "Acme",
  "posting_url": "https://...",
  "screenshot": { "id": "uuid", "url": "/api/files/uuid", "original_name": "..." } | null,
  "resume":     { "id": "uuid", "url": "/api/files/uuid", "original_name": "resume.pdf" },
  "created_at": "2026-10-01T14:03:00Z"
}
```

## Create flow (TRK-1.2, TRK-1.5)

```
validate fields (Pydantic) ── invalid ──▶ 422, nothing written
        │
validate files (type sniffing, size) ── invalid ──▶ 422, nothing written
        │
BEGIN transaction
  FileStore.save(resume)        ─┐ remember paths written
  FileStore.save(screenshot?)   ─┘
  INSERT stored_files, INSERT applications
COMMIT ── on any exception ──▶ ROLLBACK + delete files written in this request
        │
201 Application
```

The cleanup-on-failure step lives in `FileStore` as a context manager
(`with file_store.transaction() as tx:`), so spec 03 can reuse it.

Delete (TRK-3.1): delete the row and its `stored_files` rows in one transaction,
then delete the files from disk after commit. A failure to delete a file is
logged, not shown to the user; a missing file isn't an error.

## Frontend

- **`/tracker`** — the list page: search box (debounced 300 ms), table, pagination,
  "Log application" button.
- **`/tracker/new`** — the form. When the URL field loses focus, call `check-url`
  and show the duplicate warning if needed. Show an image preview after a
  screenshot is chosen. The submit button is disabled while sending.
- **`/tracker/:id`** — detail page: fields, screenshot image (click to enlarge),
  resume download link, delete button with a confirmation dialog. Also the
  status (TRK-4.5): a badge, one button per allowed next status, "Undo last
  change", and the history as a timeline.
- **Status flow plot (TRK-5)** on the list page, above the table: a hand-built
  SVG parallel sets plot (no chart library). Three axes; at each axis the
  categories are stacked bars sized by count and labelled with name and count;
  ribbons connect them, coloured by outcome with the validated categorical
  slots 1–3 (Offer blue, Rejected orange, still open aqua; all-pairs checked in
  light and dark mode). Hover or keyboard focus on a ribbon shows a tooltip
  with the path and count; a "Show as table" toggle lists every path. Hidden
  when there are no applications.

## Decisions

| #    | Decision                                     | Why                                                                                       |
| ---- | -------------------------------------------- | ----------------------------------------------------------------------------------------- |
| T-D1 | Duplicate URL is a warning, not a constraint | Re-applying to a reposted job is legitimate.                                               |
| T-D2 | One multipart request for fields and files   | One step for the user, and lets the save be all-or-nothing (TRK-1.5).                       |
| T-D3 | Trigram index for search                     | Fast, typo-tolerant `ILIKE` search on title and company without a search engine.           |

## Implementation notes

Where the code differs from the plan above, and why:

- **All field errors in one response (TRK-1.4).** The create endpoint takes the form fields as
  plain strings and checks the text fields and both files together, so a single 422 lists every
  problem. Wrong file types and oversized files are reported as field errors (422) rather than
  the 415/413 the shared `FileStore` raises, so the form can show them next to the field. The
  helper for this is `app/core/validation.py` (`FieldErrors`), for reuse by the other sub-apps.
- **Empty file parts.** Browsers send an empty, unnamed part for a file input left blank; it's
  treated as "no file".
- **Search index.** The trigram index uses the expression `(job_title || ' ') || company_name`,
  declared once in `app/tracker/models.py` (`search_expression()`) and used by both the model's
  index and the search query, so the planner can use the index. A test checks the query plan.
- **Model registry.** `app/all_models.py` imports every feature's models for Alembic and the
  tests; new features add their models there.
- **Client upload limit.** The form checks files against 10 MB (the backend default) before
  uploading; the server's `MAX_UPLOAD_MB` setting is still what's enforced.
- **Delete confirmation** is an inline "Yes, delete / Cancel" prompt rather than a modal.
- **Status flow labels.** The first axis has one category, so its count is in the axis title.
  The middle axis's labels sit in the gap above each bar (ribbons cross on both sides of it);
  the last axis's labels sit to its right. Bars and labels pass pointer events through, so
  hovering anywhere on a ribbon shows its tooltip.
- **Status filter and the plot.** The plot always shows every application (TRK-5.4); the
  status filter and search apply to the table only.

## Test strategy

Status (TRK-4, TRK-5): unit tests for the transitions table and the path
building; API tests for every allowed and refused change, the history,
undo, the status filter, cascade on delete and the flow counts; Vitest tests
for the buttons, undo, the plot's ribbons and table; the E2E test moves an
application to Interviewing and back with undo.


- **Unit:** URL normalisation cases; Pydantic validation (lengths, URL scheme).
- **Integration (API + Postgres):**
  - valid create with and without a screenshot → row saved, files on disk, `created_at` set by the server even if the client sends one;
  - each required field missing → 422 naming that field;
  - `.exe` renamed to `.pdf` → 422;
  - forced DB failure after files are written → no row, no files left (TRK-1.5);
  - list ordering, search and pagination; delete removes files.
- **E2E:** fill in the form with fixture files, submit, see the new entry first in the list, open it and download the resume.
