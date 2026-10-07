# 01 — Job Application Tracker: Tasks

Requires the foundation tasks F-1 to F-6 and F-10.

> **Status:** all tasks done. Notes on where the code differs from the design are under
> *Implementation notes* in [`design.md`](design.md#implementation-notes).

- [x] **T-1 Migration and model**
  `applications` table with indexes; enable the `pg_trgm` extension; SQLAlchemy model.
  _Criteria:_ TRK-1.2, TRK-1.3
  _Verify:_ migration test passes upgrading and downgrading; inserting without `created_at` fills it in.

- [x] **T-2 FileStore transaction helper**
  `file_store.transaction()` context manager that deletes the files it wrote if
  the block raises.
  _Criteria:_ TRK-1.5
  _Verify:_ unit test: save 2 files, raise inside the block → both files gone.

- [x] **T-3 Create endpoint**
  `POST /applications`: field validation, file type and size checks, single
  transaction.
  _Criteria:_ TRK-1.1–TRK-1.5
  _Verify:_ the create-flow integration tests in `design.md` pass.

- [x] **T-4 Duplicate URL check**
  URL normalisation function and `GET /applications/check-url`.
  _Criteria:_ TRK-1.7
  _Verify:_ unit tests for normalisation; integration test for a duplicate and a non-duplicate.

- [x] **T-5 List, detail and delete endpoints**
  _Criteria:_ TRK-2.1–TRK-2.4, TRK-3.1
  _Verify:_ integration tests: newest first, `q` matches title or company, page size 25, delete removes files.

- [x] **T-6 Form page `/tracker/new`**
  Fields, client-side validation that mirrors the server, server errors shown
  per field, screenshot preview, duplicate warning, success message and form reset.
  _Criteria:_ TRK-1.1, TRK-1.4, TRK-1.6, TRK-1.7
  _Verify:_ Vitest component tests for validation messages and keeping entered values after a 422.

- [x] **T-7 List and detail pages**
  _Criteria:_ TRK-2.1–TRK-2.4, TRK-3.1
  _Verify:_ Vitest tests for list rendering and the delete confirmation.

- [x] **T-8 E2E test**
  The end-to-end scenario from `design.md`.
  _Criteria:_ TRK-1.2, TRK-2.1, TRK-2.4
  _Verify:_ passes in CI.
