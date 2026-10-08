# 02 — Web Job Scraper: Design

## Pipeline

```
SearchOptions ──▶ JobSource.search() ──▶ normalise + dedupe ──▶ score each (LLM) ──▶ rank, top X ──▶ save ──▶ list / CSV
   (form/YAML)      (Playwright)          (SCR-3.2, 3.3)        (SCR-4.1–4.3)        (SCR-4.4)
```

Runs as a background job (`jobs.kind = 'scrape'`, see foundation design) and
records progress after each stage and each posting scored (SCR-4.5). A
module-level lock allows only one run at a time (SCR-3.6); starting a second
run returns `409` with "A search is already running".

## Search options and YAML format (SCR-1, SCR-2)

```python
class JobLevel(StrEnum):
    INTERNSHIP = "internship"; ENTRY = "entry"; MID = "mid"; SENIOR = "senior"
    STAFF_PRINCIPAL = "staff_principal"; MANAGER = "manager"; DIRECTOR_PLUS = "director_plus"

class SearchOptions(BaseModel):
    job_title: str            = Field(min_length=1, max_length=200)
    location: str | None      = Field(default=None, max_length=200)
    days_since_posting: int   = Field(ge=1, le=60)
    skills: list[str]         = Field(min_length=1, max_length=30)
    years_experience: int     = Field(ge=0, le=50)
    job_level: JobLevel
    jobs_pulled: int          = Field(ge=1, le=100)
    jobs_selected: int        = Field(ge=1)
    # model_validator: jobs_selected <= jobs_pulled  (SCR-1.2)
```

The same model validates the form, the YAML import and the stored run, so the
rules exist in one place.

Exported file (`job-search-<title-slug>-<yyyymmdd>.yaml`):

```yaml
# Job Board's Bane — job search options
version: 1
search:
  job_title: Backend Engineer
  location: Austin, TX
  days_since_posting: 7
  skills: [Python, PostgreSQL, FastAPI, AWS]
  years_experience: 5
  job_level: senior
results:
  jobs_pulled: 40
  jobs_selected: 10
```

- Export and import happen in the browser (`js-yaml`); import is checked with
  the same rules (the frontend has a Zod schema generated from the backend's
  OpenAPI schema), and the backend checks again when a run starts.
- `version` lets the format change later; only `1` is accepted for now (SCR-2.3).
- Load with a safe loader (no custom tags); reject files over 64 KB.

## Job sources (SCR-3)

```python
class RawPosting(BaseModel):
    title: str; company: str; location: str | None
    posted_at: date | None; posted_text: str | None   # e.g. "3 days ago"
    url: str; via: str | None; salary_text: str | None
    description: str

class JobSource(Protocol):
    async def search(self, opts: SearchOptions, limit: int,
                     on_progress: Callable[[int], None]) -> SourceResult: ...
    # SourceResult = {postings: list[RawPosting], stopped_reason: None | 'blocked' | 'layout_changed' | 'exhausted'}
```

Selected with the `JOB_SOURCE` setting (`google_playwright` by default, or `serpapi`).

### `GooglePlaywrightSource`

1. Build the query `"<job_title>" jobs` + ` near <location>` when a location is
   given, and open Google's jobs view (`https://www.google.com/search?q=…&ibp=htl;jobs`).
2. Apply the "date posted" filter that best fits `days_since_posting` (today /
   3 days / week / month), then filter exactly on the parsed `posted_at`
   afterwards.
3. Scroll the results list until `limit` postings are loaded or no more appear.
4. Click each posting to read the detail pane: description (expand "Show full
   description"), apply links, salary, "via" text.
5. Wait `SCRAPER_DELAY_S` (default 2 s, plus random jitter) between actions.
6. If a CAPTCHA/"unusual traffic" page appears, stop with `blocked`; if the
   expected elements are missing, stop with `layout_changed` (SCR-3.5).

All CSS selectors live in one `selectors.py` so a Google layout change only
needs one file updated. Parsing is kept separate from browsing (`parse_list(html)`,
`parse_detail(html)`), so it can be tested on saved HTML fixtures.

Relative dates like "3 days ago" / "30+ days ago" are turned into `posted_at`
using the run's start time; text that can't be parsed gives `posted_at = None`
(shown as "unknown"; kept, not filtered out).

### `SerpApiSource`

Calls the `google_jobs` engine with `SERPAPI_KEY`. Maps its response straight
to `RawPosting`. Note: this sends search terms (not resumes) to a third party.

### Normalising and de-duplicating (SCR-3.3)

Key = lower-cased, whitespace-collapsed `title|company|location`. When there are
duplicates, keep the one with the longest description.

## Scoring (SCR-4)

### Rubric

The LLM scores each input on a 0–10 scale; the overall score is computed **in
code** so it's consistent and the weights can be changed without changing the prompt.

| Criterion        | Weight | What the LLM is asked                                                                  |
| ---------------- | ------ | -------------------------------------------------------------------------------------- |
| Title / role fit | 30     | How closely the role matches the wanted job title.                                     |
| Skills           | 30     | Share of the user's skills the posting asks for or mentions (also returns the lists).  |
| Experience       | 15     | Fit between the user's years of experience and the years the posting asks for.        |
| Level            | 15     | Fit between the wanted level and the posting's seniority.                              |
| Location         | 10     | Fit with the wanted location (remote counts as a match if the user asked for remote). |

`overall = round(sum(weight_i * sub_i / 10))` → 0–100. Weights are in settings.

To make SCR-4.3 hold regardless of the model, the **skills sub-score is also
checked deterministically**: matched skills are found by case-insensitive search
(with a small alias table, e.g. `postgres`↔`postgresql`, `js`↔`javascript`) and
`skills = round(10 * matched / total)`. The LLM's skill lists are merged in
only to add synonyms the alias table missed.

### Prompt

System prompt:

> You are a recruiting assistant. Rate how well a job posting matches a
> candidate's search. Be strict and consistent. Reply only with JSON matching
> the schema.

User prompt (template):

```
CANDIDATE SEARCH
- Desired title: {job_title}
- Location: {location or "any"}
- Years of experience: {years_experience}
- Desired level: {job_level}
- Skills: {skills, comma-separated}

JOB POSTING
Title: {title}
Company: {company}
Location: {location}
Description (truncated to {max_chars} chars):
{description}

Score each criterion 0-10: title_fit, skills, experience, level, location.
List matched_skills and missing_skills (from the candidate's skills only).
Give a rationale of at most 2 sentences.
```

Response schema (`LLMClient.complete_json`):

```python
class ScoreResponse(BaseModel):
    title_fit: int = Field(ge=0, le=10)
    skills: int = Field(ge=0, le=10)
    experience: int = Field(ge=0, le=10)
    level: int = Field(ge=0, le=10)
    location: int = Field(ge=0, le=10)
    matched_skills: list[str]
    missing_skills: list[str]
    rationale: str = Field(max_length=400)
```

Descriptions are truncated to `SCORER_MAX_CHARS` (default 6000) to fit the
context window. Postings are scored one at a time (temperature 0).

Ranking: sort by `overall` descending, then `posted_at` descending (unknown
dates last); mark the first X as `selected` (SCR-4.4). Postings that failed
scoring have `score = null` and are never selected (SCR-4.6).

## Data model (SCR-5.5)

```
scrape_runs
  id               uuid pk
  job_id           uuid fk -> jobs(id)
  options          jsonb not null          -- SearchOptions
  source           text not null           -- 'google_playwright' | 'serpapi'
  stopped_reason   text null
  pulled_count     int  not null default 0
  model            text not null           -- LLM model used, for reproducibility
  created_at       timestamptz default now()

scraped_postings
  id               uuid pk
  run_id           uuid fk -> scrape_runs(id) on delete cascade
  title, company, location, url, via, salary_text, posted_text  text
  posted_at        date null
  description      text
  score            int null                -- 0-100, null = not scored
  sub_scores       jsonb null              -- {title_fit, skills, experience, level, location}
  matched_skills   text[] default '{}'
  missing_skills   text[] default '{}'
  rationale        text null
  score_error      text null
  rank             int null
  selected         bool not null default false
  index (run_id, rank)
```

## API

All routes are under `/api/scraper`.

| Method | Path                         | Notes                                                                 | Criteria        |
| ------ | ---------------------------- | --------------------------------------------------------------------- | --------------- |
| POST   | `/runs`                      | Body: `SearchOptions`. Returns `202 {run_id, job_id}`; `409` if one is running. | SCR-1, SCR-3.6 |
| GET    | `/runs`                      | Past runs: options summary, created_at, counts, status.               | SCR-5.5         |
| GET    | `/runs/{id}`                 | Run, job status/progress, postings (`?all=true` for all N).           | SCR-4.5, SCR-5  |
| GET    | `/runs/{id}/export.csv`      | Selected postings as CSV (`?all=true` for all).                       | SCR-5.3         |
| DELETE | `/runs/{id}`                 | Delete a run and its postings.                                         | —               |

### CSV columns (SCR-5.3)

`rank, score, title, company, location, posted_date, url, via, salary, matched_skills, missing_skills, title_fit, skills_score, experience_score, level_score, location_score, rationale`

UTF-8 with a BOM (opens cleanly in Excel); lists joined with `; `. Filename:
`jobs-<title-slug>-<yyyymmdd-hhmm>.csv`. Cells starting with `=`, `+`, `-` or
`@` get a leading `'` so they can't run as spreadsheet formulas (CSV injection).

## Frontend

- **`/scraper`** — search form (tag input for skills, level dropdown, N and X
  number fields), Import YAML / Export YAML buttons, "Run search" button, and
  the past-runs list below.
- **`/scraper/runs/:id`** — progress bar while running (polls every 2 s);
  then the results list: score badge (colour by range), title (links to the
  posting), company, location, posted date, matched-skill chips, rationale;
  each row expands to show sub-scores and the description. Buttons: Download
  CSV, Show all N, Export these options to YAML. Warning banner if
  `stopped_reason` is set or fewer than N were found.

## Decisions

| #    | Decision                                          | Why                                                                                  |
| ---- | ------------------------------------------------- | ------------------------------------------------------------------------------------ |
| S-D1 | Score in code from LLM sub-scores                 | More consistent and explainable than asking a small model for one number.            |
| S-D2 | Skills sub-score checked deterministically        | Guarantees SCR-4.3 whatever the model does.                                          |
| S-D3 | Score all N, then pick top X                      | Matches the reading of Q-5; N ≤ 100 keeps it to minutes on a local model.            |
| S-D4 | Swappable `JobSource`                             | Lowers the Google scraping risk; adds other sources without touching scoring.        |
| S-D5 | YAML handled in the browser                       | Nothing to store server-side; works offline; the server still checks inputs.         |

## Implementation notes

Where the code differs from the plan above, and why:

- **Google layout is unverified.** Google wasn't reachable from the environment this was built
  in, so `google_selectors.py` follows Google's long-standing jobs layout and the fixtures in
  `backend/tests/scraper/fixtures/` are hand-made to match. The parsing and browser logic are
  tested (including a real Chromium clicking through an interactive fixture page), but whether
  Google still uses this markup is not. Run `make scraper-canary` (and `SAVE=1` to keep the
  page) on a machine that can reach Google, then update the selectors and fixtures if needed.
- **Google failures are clear errors.** If the page can't load at all, or no browser is
  installed, the run fails with a message saying what to do (`make scraper-browser`).
- **SerpAPI** is implemented and tested against recorded-style responses, not the live API (no
  key was available). It doesn't pass a date filter to SerpAPI; postings are filtered on the
  parsed date like the Google source.
- **Demo mode.** `JOB_SOURCE=fake` returns canned postings and `LLM_FAKE=true` answers prompts
  with canned replies (`app/demo.py`). The E2E tests use both, so the whole flow is tested
  without Google or Ollama, and they let someone try the app before setting either up.
- **Frontend validation** is hand-written to mirror `SearchOptions` (as in the tracker) rather
  than a Zod schema generated from OpenAPI; the server validates again either way.
- **Shared skill matching.** The alias table and matching live in `app/core/skills.py` so
  Resume Rounder (spec 03, task R-7) can reuse them.
- **De-duplication** keeps the duplicate with the longest description, including its own
  spelling of the title.
- **One search at a time** is an in-process lock, released when the run's background task ends
  however it ends. It holds for the single-process server this app runs as; it would not hold
  across several server processes.
- **Extras:** a "Search again" button on a run fills the form with that run's options, and the
  past-searches list refreshes itself while a search is running.
- **CI runs the browser tests**: the backend job installs Chromium and sets `REQUIRE_BROWSER=1`,
  so a missing browser fails the build instead of skipping the tests.

## Test strategy

- **Unit:** `SearchOptions` validation (X > N, ranges); YAML round trip
  (export → import gives the same values) and the error cases; relative date
  parsing; de-duplication; skill matching with aliases; overall score
  calculation and tie-breaking; CSV escaping including formula injection.
- **Parser tests:** `parse_list`/`parse_detail` against saved Google HTML
  fixtures, including a CAPTCHA page and a page with missing selectors.
- **Pipeline integration:** `FakeJobSource` + `FakeLLMClient` → run finishes,
  top X selected correctly, one posting forced to fail scoring is excluded
  (SCR-4.6), progress updated, CSV matches the saved rows.
- **Manual canary:** `make scraper-canary` runs one live search with N=5 to
  find out early when Google's layout has changed. Not run in CI.
