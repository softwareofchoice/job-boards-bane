import type { GenerationDetail, Preflight, Report, Skill } from "./api";

export function makeSkill(overrides: Partial<Skill> = {}): Skill {
  return {
    id: "s1",
    skill_name: "PostgreSQL",
    role: "Software Engineer at Acme",
    summary: "Designed the reporting schema.",
    created_at: "2026-10-01T12:00:00Z",
    updated_at: "2026-10-01T12:00:00Z",
    ...overrides,
  };
}

export function makePreflight(overrides: Partial<Preflight> = {}): Preflight {
  return {
    template_pages: 0.8,
    suggested_target: "1",
    experience_found: true,
    experience_heading_idx: 4,
    experience_entries: [
      { header: "Software Engineer, Acme", bullets: 4 },
      { header: "Developer, Globex", bullets: 3 },
    ],
    headings: [
      { index: 2, text: "Summary" },
      { index: 4, text: "Experience" },
    ],
    posting_chars: 1234,
    skills_count: 3,
    warnings: [],
    ...overrides,
  };
}

export function makeReport(overrides: Partial<Report> = {}): Report {
  return {
    posting_skills: [
      { skill: "PostgreSQL", kind: "required", covered_by: "Postgres" },
      { skill: "Kubernetes", kind: "required", covered_by: null },
      { skill: "FastAPI", kind: "preferred", covered_by: "FastAPI" },
    ],
    unmatched_roles: ["Freelance"],
    entries: [
      {
        header: "Software Engineer, Acme · 2021 – Present",
        role: "Software Engineer at Acme",
        before: ["Built APIs.", "Fixed bugs."],
        after: ["Designed the Postgres schema.", "Built APIs."],
        skills_used: ["Postgres"],
        kept_original_reason: null,
      },
      {
        header: "Developer, Globex · 2018 – 2021",
        role: null,
        before: ["Maintained the store."],
        after: ["Maintained the store."],
        skills_used: [],
        kept_original_reason: "No saved skills matched this role.",
      },
    ],
    pages: { target: 1, template: 0.8, final: 0.9, attempts: 1, overflow: null },
    warnings: [],
    ...overrides,
  };
}

export function makeGeneration(overrides: Partial<GenerationDetail> = {}): GenerationDetail {
  return {
    id: "g1",
    job_id: "j1",
    job_title: "Backend Engineer",
    company_name: "Initech",
    posting_url: null,
    target_pages: "1.0",
    final_pages: 1,
    status: "succeeded",
    created_at: "2026-10-01T12:00:00Z",
    progress: { step: "done" },
    error: null,
    model: "llama3.1:8b",
    report: makeReport(),
    docx: {
      url: "/api/rounder/generations/g1/resume.docx",
      filename: "Initech-Backend-Engineer-resume.docx",
    },
    pdf: {
      url: "/api/rounder/generations/g1/resume.pdf",
      filename: "Initech-Backend-Engineer-resume.pdf",
    },
    ...overrides,
  };
}
