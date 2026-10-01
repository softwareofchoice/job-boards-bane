# 02 — Web Job Scraper: Requirements

> **Source (`REQUIREMENTS.md`):**
> "Scrape Google for jobs within a specified time frame, title, location, and experience
> — Use a form to take in relevant inputs
> — Inputs include, number of jobs pulled, number of jobs to be selected, days since
>   posting, job title, relevant skills, years of experience, job level
> — search options can be saved as a .yaml file and exported
> Use Local LLM to score the top X jobs against the form inputs, scoring higher for
> matching the job inputs
> Output into a CSV as well as display in the web app as a list"

## User stories

### SCR-1 — Describe the search

*As a job seeker, I want to describe the jobs I'm looking for in a form, so
that the scraper finds and ranks postings that fit me.*

- **SCR-1.1** THE SYSTEM SHALL provide a search form with these fields:
  | Field                      | Required | Rules                                                                           |
  | -------------------------- | -------- | ------------------------------------------------------------------------------- |
  | Job title                  | Yes      | 1–200 characters                                                                |
  | Location                   | No       | Free text, e.g. "Austin, TX" or "Remote". **Note:** the opening line of the requirement lists location but the inputs list doesn't; it's included here. |
  | Days since posting         | Yes      | Whole number 1–60                                                               |
  | Relevant skills            | Yes      | 1–30 tags, each 1–50 characters                                                 |
  | Years of experience        | Yes      | Whole number 0–50                                                               |
  | Job level                  | Yes      | One of: Internship, Entry, Mid, Senior, Staff/Principal, Manager, Director+     |
  | Number of jobs pulled (N)  | Yes      | Whole number 1–100                                                              |
  | Number of jobs selected (X)| Yes      | Whole number 1–N **[assumption, Q-5]**                                          |
- **SCR-1.2** IF X is greater than N THEN THE SYSTEM SHALL reject the form
  with the error "Jobs selected can't be more than jobs pulled".

### SCR-2 — Save and reuse search options

*As a job seeker, I want to export my search options to a YAML file and load
them again, so that I can repeat searches without retyping.*

- **SCR-2.1** WHEN the user clicks "Export" THE SYSTEM SHALL download the
  current form values as a `.yaml` file in the format defined in `design.md`.
- **SCR-2.2** WHEN the user imports a `.yaml` file THE SYSTEM SHALL fill in the
  form from it. **[assumption]** — "saved … and exported" is only useful if the
  file can be loaded back.
- **SCR-2.3** IF an imported file isn't valid YAML, has an unsupported
  `version`, or fails the field rules in SCR-1.1 THEN THE SYSTEM SHALL leave
  the form unchanged and list every problem.
- **SCR-2.4** THE SYSTEM SHALL ignore unknown keys in an imported file and say
  which keys it ignored.

### SCR-3 — Collect job postings

- **SCR-3.1** WHEN the user starts a search THE SYSTEM SHALL collect up to N
  job postings from Google's job search that match the title and location and
  were posted within the chosen number of days.
- **SCR-3.2** For each posting THE SYSTEM SHALL capture: title, company,
  location, posted date (or "unknown"), source/apply URL, the site it was
  posted on (e.g. LinkedIn, company site), salary text if shown, and the full
  description.
- **SCR-3.3** THE SYSTEM SHALL remove duplicate postings (same title, company
  and location) before scoring.
- **SCR-3.4** IF fewer than N postings are found THEN THE SYSTEM SHALL continue
  with the ones it found and tell the user how many it got.
- **SCR-3.5** IF Google blocks the request (CAPTCHA, HTTP 429) or the page
  layout can't be read THEN THE SYSTEM SHALL stop collecting, keep what it has,
  and show which of these happened.
- **SCR-3.6** THE SYSTEM SHALL wait between page loads (at least 2 seconds by
  default) and SHALL NOT run more than one search at a time.

### SCR-4 — Score and select the best jobs with the local LLM

*As a job seeker, I want each job scored against what I'm looking for, so that
I only review the best matches.*

- **SCR-4.1** THE SYSTEM SHALL use the local LLM to score every collected
  posting against the search inputs (title, skills, years of experience, job
  level, location).
- **SCR-4.2** THE SYSTEM SHALL give each posting an overall score from 0 to 100,
  plus a sub-score for each input and a short explanation (≤ 2 sentences), so
  the ranking can be understood.
- **SCR-4.3** Postings that match more of the inputs SHALL score higher; in
  particular a posting matching more of the listed skills SHALL NOT get a lower
  skills sub-score than one matching fewer, all else equal.
- **SCR-4.4** THE SYSTEM SHALL select the X highest-scoring postings, breaking
  ties by most recent posting date.
- **SCR-4.5** WHILE a search is running THE SYSTEM SHALL show its stage
  (collecting / scoring / done) and progress (e.g. "Scoring 12 of 40").
- **SCR-4.6** IF the LLM fails on a posting after retries THEN THE SYSTEM SHALL
  mark that posting "not scored", leave it out of the top X, and finish the run.
- **SCR-4.7** WHEN scoring a posting THE SYSTEM SHALL list which of the user's
  skills the posting mentions and which it doesn't.

### SCR-5 — See and export results

- **SCR-5.1** WHEN a run finishes THE SYSTEM SHALL show the X selected postings
  as a list ordered by score, each with title, company, location, posted date,
  score, explanation, matched skills and a link to the posting.
- **SCR-5.2** WHEN the user expands a posting THE SYSTEM SHALL show its full
  description and sub-scores.
- **SCR-5.3** THE SYSTEM SHALL let the user download the selected postings as a
  CSV with the columns defined in `design.md`.
- **SCR-5.4** THE SYSTEM SHALL let the user see all N collected postings (not
  just the top X) with a "show all" toggle. **[assumption]**
- **SCR-5.5** THE SYSTEM SHALL save each run with its inputs and results and
  list past runs so they can be reopened and re-exported. **[assumption, Q-6]**

## Out of scope (v1)

- Job boards other than Google's job search (the `JobSource` interface allows adding them later).
- Scheduled or recurring searches and email alerts.
- Applying to jobs automatically.
- Sending a selected job to the Tracker or Resume Rounder with one click (Q-10).

## Risks

- **Google terms of service and anti-bot measures.** Automated scraping of
  Google is against its terms and may be blocked with CAPTCHAs. The design
  isolates the scraper behind `JobSource` so a licensed API (e.g. SerpAPI's
  `google_jobs` engine) can replace it by changing a setting. Decide which
  source to use before release (Q-4).
- **Page layout changes** break the scraper without warning. The HTML-parsing
  tests run against saved pages, and a live "canary" test can be run by hand.
- **Small local models score inconsistently.** The design reduces this with
  temperature 0, a fixed rubric, and computing the overall score in code from
  the sub-scores.
