import type { Posting, RunDetail } from "./api";
import type { SearchOptions } from "./options";

export const OPTIONS: SearchOptions = {
  job_title: "Python Developer",
  location: "Austin, TX",
  days_since_posting: 7,
  skills: ["Python", "PostgreSQL"],
  years_experience: 5,
  job_level: "senior",
  jobs_pulled: 10,
  jobs_selected: 3,
};

export function makePosting(overrides: Partial<Posting> = {}): Posting {
  return {
    id: "p1",
    title: "Python Developer",
    company: "Acme",
    location: "Austin, TX",
    url: "https://jobs.example.test/1",
    via: "LinkedIn",
    salary_text: "$120K a year",
    posted_text: "2 days ago",
    posted_at: "2026-10-06",
    description: "Python and PostgreSQL.",
    score: 82,
    sub_scores: { title_fit: 9, skills: 10, experience: 7, level: 6, location: 10 },
    matched_skills: ["Python", "PostgreSQL"],
    missing_skills: [],
    rationale: "Strong match.",
    score_error: null,
    rank: 1,
    selected: true,
    ...overrides,
  };
}

export function makeRun(overrides: Partial<RunDetail> = {}): RunDetail {
  return {
    id: "r1",
    job_id: "j1",
    options: OPTIONS,
    source: "fake",
    status: "succeeded",
    stopped_reason: null,
    pulled_count: 10,
    selected_count: 1,
    created_at: "2026-10-08T10:00:00Z",
    progress: { step: "done", done: 10, total: 10 },
    error: null,
    model: "llama3.1:8b",
    postings: [makePosting()],
    ...overrides,
  };
}
