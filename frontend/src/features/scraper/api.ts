import { api } from "../../lib/api";
import type { SearchOptions } from "./options";

export type RunStatus = "queued" | "running" | "succeeded" | "failed";
export type StopReason = "blocked" | "layout_changed" | "exhausted" | null;

export interface SubScores {
  title_fit: number;
  skills: number;
  experience: number;
  level: number;
  location: number;
}

export interface Posting {
  id: string;
  title: string;
  company: string;
  location: string | null;
  url: string;
  via: string | null;
  salary_text: string | null;
  posted_text: string | null;
  posted_at: string | null;
  description: string;
  score: number | null;
  sub_scores: SubScores | null;
  matched_skills: string[];
  missing_skills: string[];
  rationale: string | null;
  score_error: string | null;
  rank: number | null;
  selected: boolean;
}

export interface RunSummary {
  id: string;
  job_id: string;
  options: SearchOptions;
  source: string;
  status: RunStatus;
  stopped_reason: StopReason;
  pulled_count: number;
  selected_count: number;
  created_at: string;
}

export interface RunProgress {
  step?: "collecting" | "scoring" | "done";
  done?: number;
  total?: number;
}

export interface RunDetail extends RunSummary {
  progress: RunProgress;
  error: string | null;
  model: string;
  postings: Posting[];
}

const BASE = "/api/scraper/runs";

export const scraperKeys = {
  all: ["scraper"] as const,
  runs: ["scraper", "runs"] as const,
  run: (id: string, all: boolean) => ["scraper", "run", id, all] as const,
};

export function startRun(options: SearchOptions): Promise<{ run_id: string; job_id: string }> {
  return api(BASE, { method: "POST", body: options });
}

export function listRuns(): Promise<RunSummary[]> {
  return api<RunSummary[]>(BASE);
}

export function getRun(id: string, all: boolean): Promise<RunDetail> {
  return api<RunDetail>(`${BASE}/${encodeURIComponent(id)}${all ? "?all=true" : ""}`);
}

export function deleteRun(id: string): Promise<void> {
  return api<void>(`${BASE}/${encodeURIComponent(id)}`, { method: "DELETE" });
}

export function csvUrl(id: string, all: boolean): string {
  return `${BASE}/${encodeURIComponent(id)}/export.csv${all ? "?all=true" : ""}`;
}

export function isActive(status: RunStatus): boolean {
  return status === "queued" || status === "running";
}
