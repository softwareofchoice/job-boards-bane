# 03 — Resume Rounder: Tasks

Requires the foundation tasks F-1 to F-10. LibreOffice must be installed for
R-8 (add it to the dev setup docs and the CI image). Resolve Q-7, Q-8 and Q-9
before R-4.

- [ ] **R-1 Skills migration, model and API**
  `skills` table with the case-insensitive unique index; CRUD endpoints; role
  suggestions.
  _Criteria:_ RND-1.1–RND-1.4
  _Verify:_ integration tests for create, duplicate → 409 with `existing_id`, edit, delete.

- [ ] **R-2 Skills pages (frontend)**
  _Criteria:_ RND-1.1, RND-1.3, RND-1.4
  _Verify:_ Vitest: duplicate error offers "Edit existing"; list is grouped by role.

- [ ] **R-3 Fixture resumes**
  Create the `.docx` fixtures listed in `design.md` (no real personal data).
  _Criteria:_ supports RND-2.5, RND-3.5, RND-3.6
  _Verify:_ they open in LibreOffice and look right.

- [ ] **R-4 Template reader (`resume_doc.py`)**
  Find the experience heading and section end, split headers from bullets,
  tables, override with a chosen heading.
  _Criteria:_ RND-2.5
  _Verify:_ unit tests on each fixture give the expected entries and bullets.

- [ ] **R-5 Document writer + "nothing else changed" check**
  Replace / add / remove bullets keeping formatting; paragraph hash comparison.
  _Criteria:_ RND-3.5, RND-3.6
  _Verify:_ unit tests: formatting kept; changing a non-bullet paragraph on purpose makes the check fail.

- [ ] **R-6 Posting fetch**
  httpx + trafilatura, Playwright fallback, minimum length check.
  _Criteria:_ RND-2.3, RND-2.4
  _Verify:_ fixture-based tests; unreachable host → `PostingUnavailable`.

- [ ] **R-7 Skill extraction and matching**
  `PostingSkills` prompt, alias table (shared with spec 02 — move it to
  `core/skills_aliases.py`), LLM synonym pairing with discarding of invalid
  pairs, role fuzzy matching, relevance weights.
  _Criteria:_ RND-3.1–RND-3.3
  _Verify:_ unit tests with `FakeLLMClient`, including a reply that names a skill in neither list.

- [ ] **R-8 Rewriter, space budget and length loop**
  Budget sharing, per-entry prompt, `RewrittenEntry`, made-up facts check,
  render with LibreOffice and count pages, up to 3 shortening attempts.
  _Criteria:_ RND-3.4, RND-3.7–RND-3.9
  _Verify:_ integration tests from `design.md` (fits target; overflow reported after 3 tries; made-up employer → original kept).

- [ ] **R-9 Generation job, preflight and API**
  Migration for `resume_generations`; preflight endpoint; background job with
  progress steps; report; downloads.
  _Criteria:_ RND-2.1–RND-2.6, RND-4.1–RND-4.4
  _Verify:_ integration test: preflight errors for both/neither posting inputs, no experience section, no saved skills; full run gives `.docx` + `.pdf`.

- [ ] **R-10 Generate and report pages (frontend)**
  _Criteria:_ RND-2.1, RND-2.2, RND-2.5, RND-2.6, RND-4.1–RND-4.4
  _Verify:_ Vitest component tests; E2E scenario from `design.md`.

- [ ] **R-11 Quality check script**
  `make rounder-eval` against the real model.
  _Criteria:_ RND-3.4, RND-3.7 (checked by a person)
  _Verify:_ run it once by hand and read the reports before calling the feature done.
