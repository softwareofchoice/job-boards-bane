# 02 — Web Job Scraper: Tasks

Requires the foundation tasks F-1 to F-10. Resolve Q-4 (Google scraping vs
SerpAPI) and Q-5 before S-4.

> **Status:** implemented with the assumptions in `specs/README.md` for Q-4 (both sources,
> Google by default) and Q-5 (pull N, score all, keep the top X). One check is open: **S-6**
> needs `make scraper-canary` run against the live Google site, which couldn't be reached from
> the environment this was built in. The Google selectors and fixtures are therefore
> unverified (see *Implementation notes* in [`design.md`](design.md#implementation-notes)).

- [x] **S-1 `SearchOptions` model**
  Pydantic model, `JobLevel` enum, X ≤ N check; export the OpenAPI schema for the frontend.
  _Criteria:_ SCR-1.1, SCR-1.2
  _Verify:_ unit tests for every field rule.

- [x] **S-2 Search form + YAML import/export (frontend)**
  Form, skill tag input, Zod schema, `js-yaml` export/import, list of import
  errors, note of ignored keys.
  _Criteria:_ SCR-1.1, SCR-1.2, SCR-2.1–SCR-2.4
  _Verify:_ Vitest: export → import gives the same values; bad YAML, `version: 2` and X > N each leave the form unchanged and show the errors.

- [x] **S-3 Migrations and models**
  `scrape_runs`, `scraped_postings`.
  _Criteria:_ SCR-5.5
  _Verify:_ migration test upgrades and downgrades.

- [x] **S-4 `JobSource` interface, `FakeJobSource`, normalising and de-duplicating**
  _Criteria:_ SCR-3.2, SCR-3.3
  _Verify:_ unit tests for de-duplication and relative date parsing.

- [x] **S-5 Google parsers + HTML fixtures**
  Save fixture pages (list, detail, CAPTCHA). `selectors.py`, `parse_list`,
  `parse_detail`, block/layout detection.
  _Criteria:_ SCR-3.2, SCR-3.5
  _Verify:_ parser tests pass on the fixtures.

- [ ] **S-6 `GooglePlaywrightSource`**
  Query building, date filter, scrolling, opening each detail pane, delay with
  jitter, stop reasons, progress callback.
  _Criteria:_ SCR-3.1, SCR-3.4–SCR-3.6
  _Verify:_ `make scraper-canary` returns 5 postings with descriptions (manual).
  _Status:_ built and tested against local fixture pages with a real browser; **not yet run
  against Google**.

- [x] **S-7 `SerpApiSource`** *(optional, depends on Q-4)*
  _Criteria:_ SCR-3.1, SCR-3.2
  _Verify:_ unit test that maps a recorded API response.

- [x] **S-8 Scorer**
  Prompt template, `ScoreResponse`, skill matching with aliases, weighted
  overall score, failure handling.
  _Criteria:_ SCR-4.1–SCR-4.3, SCR-4.6, SCR-4.7
  _Verify:_ unit tests with `FakeLLMClient`; property test: adding a matched skill never lowers the skills sub-score.

- [x] **S-9 Run pipeline + background job + API**
  `POST/GET/DELETE /runs`, the one-run-at-a-time lock, progress updates,
  ranking and selection.
  _Criteria:_ SCR-3.6, SCR-4.4, SCR-4.5, SCR-5.5
  _Verify:_ pipeline integration test from `design.md`; a second start returns 409.

- [x] **S-10 CSV export**
  _Criteria:_ SCR-5.3
  _Verify:_ unit test for columns, BOM and formula escaping; integration test that the download matches the saved rows.

- [x] **S-11 Run page (frontend)**
  Progress view, results list, expandable rows, show-all toggle, CSV download,
  warning banners, past-runs list.
  _Criteria:_ SCR-4.5, SCR-5.1–SCR-5.5
  _Verify:_ Vitest component tests; E2E test with the backend set to `FakeJobSource` + `FakeLLMClient`.
