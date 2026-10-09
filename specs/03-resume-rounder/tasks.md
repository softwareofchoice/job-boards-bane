# 03 — Resume Rounder: Tasks

Requires the foundation tasks F-1 to F-10. LibreOffice must be installed for
R-8 (add it to the dev setup docs and the CI image). Resolve Q-7, Q-8 and Q-9
before R-4.

> **Status:** implemented with the assumptions in `specs/README.md` for Q-7 (a skill's role is a
> job in the resume's experience section), Q-8 (`.docx` in, `.docx` and PDF out) and Q-9 (target
> length in pages, measured by rendering with LibreOffice). One check is open: **R-11** needs
> `make rounder-eval` run against a real local model and its reports read by a person. See
> *Implementation notes* in [`design.md`](design.md#implementation-notes) for where the code
> differs from the plan.

- [x] **R-1 Skills migration, model and API**
  `skills` table with the case-insensitive unique index; CRUD endpoints; role
  suggestions.
  _Criteria:_ RND-1.1–RND-1.4
  _Verify:_ integration tests for create, duplicate → 409 with `existing_id`, edit, delete.

- [x] **R-2 Skills pages (frontend)**
  _Criteria:_ RND-1.1, RND-1.3, RND-1.4
  _Verify:_ Vitest: duplicate error offers "Edit existing"; list is grouped by role.

- [x] **R-3 Fixture resumes**
  Create the `.docx` fixtures listed in `design.md` (no real personal data).
  _Built in code by `app/rounder/sample_resumes.py` rather than kept as files; checked by
  rendering each one with LibreOffice._
  _Criteria:_ supports RND-2.5, RND-3.5, RND-3.6
  _Verify:_ they open in LibreOffice and look right.

- [x] **R-4 Template reader (`resume_doc.py`)**
  Find the experience heading and section end, split headers from bullets,
  tables, override with a chosen heading.
  _Criteria:_ RND-2.5
  _Verify:_ unit tests on each fixture give the expected entries and bullets.

- [x] **R-5 Document writer + "nothing else changed" check**
  Replace / add / remove bullets keeping formatting; paragraph hash comparison.
  _Criteria:_ RND-3.5, RND-3.6
  _Verify:_ unit tests: formatting kept; changing a non-bullet paragraph on purpose makes the check fail.

- [x] **R-6 Posting fetch**
  httpx + trafilatura, Playwright fallback, minimum length check.
  _Criteria:_ RND-2.3, RND-2.4
  _Verify:_ fixture-based tests; unreachable host → `PostingUnavailable`.

- [x] **R-7 Skill extraction and matching**
  `PostingSkills` prompt, alias table (shared with spec 02, in `core/skills.py`), LLM synonym pairing with discarding of invalid
  pairs, role fuzzy matching, relevance weights.
  _Criteria:_ RND-3.1–RND-3.3
  _Verify:_ unit tests with `FakeLLMClient`, including a reply that names a skill in neither list.

- [x] **R-8 Rewriter, space budget and length loop**
  Budget sharing, per-entry prompt, `RewrittenEntry`, made-up facts check,
  render with LibreOffice and count pages, up to 3 shortening attempts.
  _Criteria:_ RND-3.4, RND-3.7–RND-3.9
  _Verify:_ integration tests from `design.md` (fits target; overflow reported after 3 tries; made-up employer → original kept).

- [x] **R-9 Generation job, preflight and API**
  Migration for `resume_generations`; preflight endpoint; background job with
  progress steps; report; downloads.
  _Criteria:_ RND-2.1–RND-2.6, RND-4.1–RND-4.4
  _Verify:_ integration test: preflight errors for both/neither posting inputs, no experience section, no saved skills; full run gives `.docx` + `.pdf`.

- [x] **R-10 Generate and report pages (frontend)**
  _Criteria:_ RND-2.1, RND-2.2, RND-2.5, RND-2.6, RND-4.1–RND-4.4
  _Verify:_ Vitest component tests; E2E scenario from `design.md`.

- [ ] **R-11 Quality check script**
  `make rounder-eval` against the real model.
  _Criteria:_ RND-3.4, RND-3.7 (checked by a person)
  _Verify:_ run it once by hand and read the reports before calling the feature done.
  _Status:_ built and tested with canned replies; **not yet run against a real model** (no
  Ollama in the environment this was built in).
