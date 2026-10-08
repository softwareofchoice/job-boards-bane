# 03 — Resume Rounder: Design

## Data model

`REQUIREMENTS.md` names the table "SKILLS"; it is created as `skills`.

```
skills
  id            uuid pk
  skill_name    varchar(100)  not null
  role          varchar(200)  not null
  summary       varchar(1000) not null
  created_at    timestamptz   not null default now()
  updated_at    timestamptz   not null default now()
  unique (lower(skill_name), lower(role))          -- RND-1.3

resume_generations
  id                  uuid pk
  job_id              uuid fk -> jobs(id)
  template_file_id    uuid fk -> stored_files(id)
  output_docx_file_id uuid null fk -> stored_files(id)
  output_pdf_file_id  uuid null fk -> stored_files(id)
  job_title           varchar(200) not null
  company_name        varchar(200) not null
  posting_url         varchar(2048) null
  posting_text        text not null           -- downloaded or pasted
  target_pages        numeric(2,1) not null
  final_pages         int null
  report              jsonb null              -- see "Generation report"
  model               text not null
  created_at          timestamptz default now()
```

## Pipeline (background job `resume_generation`)

```
1. Read template ─▶ 2. Get posting text ─▶ 3. Extract posting skills (LLM)
                                                     │
6. Check length ◀─ 5. Rewrite entries (LLM) ◀─ 4. Match skills & roles
   │  over? shorten & retry (max 3)
   ▼
7. Write .docx + .pdf ─▶ 8. Check nothing outside experience changed ─▶ save + report
```

Steps 1 and 2 also run **synchronously** in a `POST /generations/preflight`
call when the form is submitted, so problems (RND-2.4, RND-2.5) show up before
the job starts.

### 1. Read the template (`resume_doc.py`)

Use `python-docx` to turn the document into a model:

```python
class ExperienceEntry(BaseModel):
    header_paragraph_idxs: list[int]   # role / company / dates lines — never edited
    header_text: str
    bullet_paragraph_idxs: list[int]   # the only paragraphs that will be rewritten
    bullets: list[str]

class ResumeModel(BaseModel):
    experience_heading_idx: int
    experience_end_idx: int            # index of the next section heading
    entries: list[ExperienceEntry]
```

- **Finding the experience heading:** a paragraph with a Heading style, or a
  short, bold or all-caps paragraph, whose text matches
  `^(professional |work |relevant )?experience|employment( history)?$`
  (ignoring case). If none matches → `ExperienceSectionNotFound`, with the list
  of headings found so the UI can ask the user to pick one (RND-2.5).
- **Section end:** the next paragraph that looks like a heading in the same way.
- **Bullets:** paragraphs in the section with a numbering/list style (`w:numPr`)
  or starting with a bullet character. All other paragraphs in the section are
  entry headers.
- Tables inside the section are read cell by cell with the same rules. Text
  boxes aren't supported in v1 (shown as a warning).

### 2. Get the posting text (RND-2.3, RND-2.4)

`httpx` GET (15 s timeout, normal browser User-Agent) → `trafilatura`
extracts the main text. If the result is under 200 characters, try again
rendering with Playwright (many job sites build the page with JavaScript).
Still under 200 → `PostingUnavailable`, and the UI asks for pasted text.

### 3. Extract posting skills (RND-3.1)

```python
class PostingSkills(BaseModel):
    required: list[str]     # skills/technologies/competencies, as written
    preferred: list[str]
```

Prompt: *"List the skills, technologies and competencies this job posting asks
for. Separate required from preferred. Use the posting's own wording. Don't
include soft skills unless they are stated as requirements."*

### 4. Match skills and roles (RND-3.2, RND-3.3)

- **Skill matching:** first match names after normalising them (lower case,
  punctuation removed, shared alias table with spec 02). Then one LLM call with
  the posting skills that weren't matched and the saved skill names that weren't
  matched, asking only for pairs that mean the same thing (`[{posting_skill, saved_skill}]`).
  Pairs naming a skill not in either list are discarded.
- **Role matching:** fuzzy-match each distinct `skills.role` against each
  `ExperienceEntry.header_text` (`rapidfuzz.token_set_ratio ≥ 80`). Roles below
  the threshold are listed as unmatched in the report; their skills aren't used.
- **Relevance:** each matched skill entry gets `required` (weight 2) or
  `preferred` (weight 1). Each experience entry gets a relevance total that's
  used to share out space in step 5.

### 5. Rewrite experience entries (RND-3.4, RND-3.7)

**Space budget.** Count the template's bullet lines and characters. Scale by
`target_pages / template_pages` to get a total bullet-character budget for the
whole experience section. Share it out across entries in proportion to
`(original share) × (1 + relevance)`, with a minimum of 1 bullet per entry.

One LLM call per entry:

System:
> You rewrite resume bullet points. You may only use facts that appear in the
> ORIGINAL BULLETS or the SKILL NOTES. Never invent employers, numbers, dates,
> tools or results. Use strong past-tense verbs (present tense if the role is
> current). Reply only with JSON.

User:
```
ROLE: {header_text}
TARGET JOB: {job_title} at {company_name}
SKILLS THE POSTING WANTS (most important first): {posting skills matched to this role}

ORIGINAL BULLETS:
- ...

SKILL NOTES (from the candidate):
- {skill_name}: {summary}

Write {n_min}-{n_max} bullets, about {chars_per_bullet} characters each, at most
{char_budget} characters in total. Lead with the skills the posting wants.
Keep strong original bullets that still fit.
```

```python
class RewrittenEntry(BaseModel):
    bullets: list[str]
    skills_used: list[str]   # must be a subset of the skill names given
```

**Made-up facts check (RND-3.7):** after each reply, find every number and
every capitalised term or known tech word in the new bullets that doesn't
appear in the original bullets, the skill notes, or the posting skills. If any
are found, re-prompt once naming them; if they're still there, keep the
original bullets for that entry and note it in the report.

### 6. Check length (RND-3.8, RND-3.9)

Write the `.docx` (step 7), convert it with
`soffice --headless --convert-to pdf`, and count pages with `pypdf`. For
fractional targets (1.5), check that the last page's text ends above the halfway
point (using `pdfplumber` positions).

If it's over the target: cut the budget by 15% (or by the measured overflow,
whichever is more), taking from the least relevant entries first, and
re-run step 5 only for entries whose budget changed. At most 3 attempts; then
return the shortest attempt and record the overflow (RND-3.9).

### 7. Write the document (RND-3.5, RND-3.6)

Edit a copy of the template only by **replacing the text of bullet paragraphs**:

- Replace in place: keep the paragraph and its `pPr` (style, numbering,
  spacing). Keep the first run's `rPr` (font, size, colour), put the new text in
  that run, remove the other runs.
- More bullets than before: deep-copy the entry's last bullet paragraph XML and
  insert it after the last one, then set its text.
- Fewer bullets: remove the extra bullet paragraphs.
- Header paragraphs and anything outside `[experience_heading_idx, experience_end_idx)`
  are never touched.

### 8. Check nothing else changed (RND-3.5)

Before saving, compare a hash of each paragraph's XML outside the bullet
paragraphs (plus headers, footers and section properties) in the template and
the output. Any difference → the job fails with an internal error (this is a
bug, not a user error). This check also runs in every test.

### Generation report (RND-4.2)

```jsonc
{
  "posting_skills": [{"skill": "Kubernetes", "kind": "required", "covered_by": "K8s"} , {"skill": "Go", "kind": "preferred", "covered_by": null}],
  "unmatched_roles": ["Freelance"],
  "entries": [{"header": "Software Engineer, Acme · 2021–2024",
               "before": ["..."], "after": ["..."], "skills_used": ["PostgreSQL", "FastAPI"],
               "kept_original_reason": null}],
  "pages": {"target": 1, "final": 1, "attempts": 2, "overflow": null},
  "warnings": ["Result is more than half a page under the target length."]
}
```

## API

All routes are under `/api/rounder`.

| Method | Path                         | Notes                                                                                  | Criteria        |
| ------ | ---------------------------- | -------------------------------------------------------------------------------------- | --------------- |
| POST   | `/skills`                    | `{skill_name, role, summary}` → `201`; `409` with `existing_id` if duplicate           | RND-1.1–1.3     |
| GET    | `/skills`                    | `?role=` filter; grouped by role in the UI                                             | RND-1.4         |
| GET    | `/skills/roles`              | Distinct roles, for suggestions                                                         | RND-1.1         |
| PUT    | `/skills/{id}`, DELETE `/skills/{id}` |                                                                                | RND-1.4         |
| POST   | `/generations/preflight`     | multipart: template, posting_url \| posting_text, … → `{template_pages, experience_entries, headings?, posting_chars}` or errors | RND-2.2–2.6 |
| POST   | `/generations`               | multipart, same fields + `target_pages`, optional `experience_heading_idx` → `202 {generation_id, job_id}` | RND-3   |
| GET    | `/generations`, `/generations/{id}` | List; detail with job progress and report                                       | RND-4.1, 4.2, 4.4 |
| GET    | `/generations/{id}/resume.docx`, `/resume.pdf` | Downloads, named `<Company>-<JobTitle>-resume.docx`              | RND-4.3         |

## Frontend

- **`/resume-rounder/skills`** — skill form (role field suggests existing roles);
  list grouped by role with edit/delete.
- **`/resume-rounder`** — generate form: template upload, URL/text toggle,
  title, company, target-length dropdown (default filled in after preflight).
  Shows preflight results ("Found 4 roles in your experience section, 3 pages")
  and lets the user pick the experience heading if it wasn't found.
- **`/resume-rounder/generations/:id`** — progress steps, then the report:
  posting skills coverage (covered / missing), unmatched roles with a link to
  edit them, before/after per entry, page count, warnings, download buttons.

## Decisions

| #    | Decision                                       | Why                                                                                         |
| ---- | ---------------------------------------------- | ------------------------------------------------------------------------------------------- |
| R-D1 | `.docx` only, edited in place                  | "A resume to use as a format" means keeping the user's layout; only `.docx` can be edited reliably. |
| R-D2 | Role links skills to experience entries        | Turns "swap in the saved skills" into a precise, checkable operation per entry.              |
| R-D3 | Rewrite one entry at a time                    | Small prompts suit small local models; only changed entries are redone when shortening.     |
| R-D4 | Measure length by rendering to PDF             | Page count is what the user sees; estimating from word counts misses fonts and margins.     |
| R-D5 | Made-up facts check + "nothing else changed" check | The biggest risks of LLM-written resumes are made-up claims and broken layout.        |

## Implementation notes

Where the code differs from the plan above, and why:

- **Modules.** `resume_doc.py` (read, write, check), `posting.py` (fetch), `matching.py`,
  `rewrite.py` (budget, facts check, one entry), `generate.py` (steps 3–8, no database, shared
  with `make rounder-eval`), `generation_service.py` (the job) and `pages.py` (LibreOffice).
- **Paragraphs are counted in reading order including table cells**, so entries in a table are
  read and rewritten like any other; the report warns that the layout should be checked. Text
  boxes are skipped with a warning.
- **Section end.** For a Word heading style, the section ends at the next heading of the same or
  a higher level, so roles written as "Heading 2" stay inside "Heading 1 Experience". Otherwise
  it ends at the next heading-like paragraph formatted exactly like the experience heading
  (style, bold, caps, size). Typed bullet characters ("•", "-") are kept when the text is
  replaced.
- **Length** is measured as a fraction (`pages - 1 + how far down the last page the text
  reaches`, from `pdfplumber`), so 1.5-page targets work and the suggested target is the
  smallest allowed length the template already fits. Text in the bottom margin (a footer with
  page numbers) is ignored so it doesn't make every last page look full. `pypdf` isn't needed.
- **Attempts.** "At most 3 attempts" counts renders: the first try plus up to two shortenings.
  Shortening stops early when no entry can be cut further, and the closest attempt is returned
  with the overflow (RND-3.9).
- **Space budget.** When the target is longer than the template, every entry keeps its length
  and the extra goes to entries with matched skills. When it's shorter, entries share the total
  by original length boosted by relevance (up to 1.5× for the most relevant), so one entry
  can't take over. The scale is capped between 0.3× and 1.25× the original bullets, and an
  entry keeps at least one bullet (80 characters). Entries with no matched skills keep their
  bullets unchanged unless their budget shrinks. A reply more than 15% over its budget loses
  trailing bullets.
- **Stricter made-up facts check.** Allowed sources are the entry's original bullets and header
  and the matched skill notes, **not** the posting's skills: otherwise a skill the candidate
  doesn't have could be written in (RND-3.7). Checked: numbers, capitalised words that don't
  start the bullet or a sentence (a singular or plural of a known word is fine), and technology names from the alias table written in lower
  case (except groups with everyday words such as "go" or "rest").
- **Skill matching** also counts a posting phrase that mentions a saved skill ("experience with
  Kubernetes in production") as a match without asking the LLM.
- **Preflight** returns the experience entries, the headings to choose from and any warnings;
  a missing experience section is a normal result (not an error) so the UI can ask for the
  heading. `POST /generations` re-checks everything and also needs a chosen heading if none was
  found. The posting URL is fetched again by the job, which saves the text it used.
- **`resume_generations.experience_heading_idx`** (not in the data model above) records the
  experience heading used, chosen or found, so a generation can be reproduced.
- **Errors carry details.** A duplicate skill's 409 has `existing_id` next to `code` and
  `message`; the frontend's `ApiError.details` exposes such fields.
- **Settings:** `SOFFICE_PATH`, `SOFFICE_TIMEOUT_S`, `POSTING_BROWSER_FALLBACK` (the browser
  fallback reuses `SCRAPER_CHROMIUM_PATH`).
- **Demo mode.** `LLM_FAKE=true` answers the rounder's prompts too (skills from the alias table
  and tech-looking words; rewrites from the skill notes), so the E2E test runs the real pipeline,
  including LibreOffice, without Ollama.
- **CI** installs `libreoffice-writer-nogui` in the backend and E2E jobs and sets
  `REQUIRE_SOFFICE=1`, so the LibreOffice test fails instead of skipping.
- **Also added:** `make rounder-samples` writes the sample resumes to `data/samples/` for trying
  the app.

## Test strategy

- **Fixture resumes** (`tests/fixtures/resumes/`): headings as Word styles;
  bold all-caps headings; experience in a table; no experience section; 1-page
  and 2-page versions.
- **Unit:** experience section detection on each fixture; bullet replace / add /
  remove keeps `pPr`/`rPr`; space budget sharing; made-up facts detector
  (catches a new "40%", allows a number from a skill note); role fuzzy matching.
- **Integration with `FakeLLMClient`:** full pipeline on each fixture → the
  "nothing else changed" check passes, page count ≤ target, report complete; a
  fake that always returns too much text → 3 attempts then overflow reported;
  a fake that adds a new employer → the original bullets are kept for that entry.
- **Posting fetch:** recorded HTML fixtures for trafilatura; network failure →
  `PostingUnavailable`.
- **E2E:** add 3 skills, generate from a fixture resume with pasted text
  (backend on `FakeLLMClient`), see the report, download the `.docx`.
- **Manual quality check:** `make rounder-eval` runs 3 real postings × 2
  fixture resumes against the real local model and writes the reports to
  `data/eval/` for a person to read. Not run in CI.
