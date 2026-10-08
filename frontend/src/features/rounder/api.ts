import { api } from "../../lib/api";

export interface Skill {
  id: string;
  skill_name: string;
  role: string;
  summary: string;
  created_at: string;
  updated_at: string;
}

export interface SkillInput {
  skill_name: string;
  role: string;
  summary: string;
}

export interface Heading {
  index: number;
  text: string;
}

export interface Preflight {
  template_pages: number;
  suggested_target: string;
  experience_found: boolean;
  experience_heading_idx: number | null;
  experience_entries: { header: string; bullets: number }[];
  headings: Heading[];
  posting_chars: number;
  skills_count: number;
  warnings: string[];
}

export type GenerationStatus = "queued" | "running" | "succeeded" | "failed";

export interface GenerationSummary {
  id: string;
  job_id: string;
  job_title: string;
  company_name: string;
  posting_url: string | null;
  target_pages: string;
  final_pages: number | null;
  status: GenerationStatus;
  created_at: string;
}

export type GenerationStep =
  "reading_posting" | "finding_skills" | "rewriting" | "checking_length" | "done";

export interface GenerationProgress {
  step?: GenerationStep;
  done?: number;
  total?: number;
  attempt?: number;
  max_attempts?: number;
}

export interface EntryReport {
  header: string;
  role: string | null;
  before: string[];
  after: string[];
  skills_used: string[];
  kept_original_reason: string | null;
}

export interface Report {
  posting_skills: { skill: string; kind: "required" | "preferred"; covered_by: string | null }[];
  unmatched_roles: string[];
  entries: EntryReport[];
  pages: {
    target: number;
    template: number;
    final: number;
    attempts: number;
    overflow: number | null;
  };
  warnings: string[];
}

export interface FileLink {
  url: string;
  filename: string;
}

export interface GenerationDetail extends GenerationSummary {
  progress: GenerationProgress;
  error: string | null;
  model: string;
  report: Report | null;
  docx: FileLink | null;
  pdf: FileLink | null;
}

export interface GenerationRequest {
  template: File;
  job_title: string;
  company_name: string;
  posting_url: string;
  posting_text: string;
  target_pages?: string;
  experience_heading_idx?: number | null;
}

const BASE = "/api/rounder";

export const rounderKeys = {
  all: ["rounder"] as const,
  skills: ["rounder", "skills"] as const,
  roles: ["rounder", "roles"] as const,
  generations: ["rounder", "generations"] as const,
  generation: (id: string) => ["rounder", "generation", id] as const,
};

export function listSkills(): Promise<Skill[]> {
  return api<Skill[]>(`${BASE}/skills`);
}

export function listRoles(): Promise<string[]> {
  return api<string[]>(`${BASE}/skills/roles`);
}

export function createSkill(input: SkillInput): Promise<Skill> {
  return api<Skill>(`${BASE}/skills`, { method: "POST", body: input });
}

export function updateSkill(id: string, input: SkillInput): Promise<Skill> {
  return api<Skill>(`${BASE}/skills/${encodeURIComponent(id)}`, { method: "PUT", body: input });
}

export function deleteSkill(id: string): Promise<void> {
  return api<void>(`${BASE}/skills/${encodeURIComponent(id)}`, { method: "DELETE" });
}

function toForm(input: GenerationRequest): FormData {
  const form = new FormData();
  form.set("template", input.template);
  form.set("job_title", input.job_title);
  form.set("company_name", input.company_name);
  form.set("posting_url", input.posting_url);
  form.set("posting_text", input.posting_text);
  if (input.target_pages !== undefined) form.set("target_pages", input.target_pages);
  if (input.experience_heading_idx != null) {
    form.set("experience_heading_idx", String(input.experience_heading_idx));
  }
  return form;
}

export function preflight(input: GenerationRequest): Promise<Preflight> {
  return api<Preflight>(`${BASE}/generations/preflight`, { method: "POST", body: toForm(input) });
}

export function startGeneration(
  input: GenerationRequest,
): Promise<{ generation_id: string; job_id: string }> {
  return api(`${BASE}/generations`, { method: "POST", body: toForm(input) });
}

export function listGenerations(): Promise<GenerationSummary[]> {
  return api<GenerationSummary[]>(`${BASE}/generations`);
}

export function getGeneration(id: string): Promise<GenerationDetail> {
  return api<GenerationDetail>(`${BASE}/generations/${encodeURIComponent(id)}`);
}

export function isActive(status: GenerationStatus): boolean {
  return status === "queued" || status === "running";
}

export const TARGET_OPTIONS = [
  ["1", "1 page"],
  ["1.5", "1½ pages"],
  ["2", "2 pages"],
  ["3", "3 pages"],
] as const;
